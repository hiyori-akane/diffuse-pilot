"""
Discord Bot

画像生成のための Discord インターフェース
"""

import asyncio
from pathlib import Path

import discord
from discord import app_commands
from sqlalchemy import select

from src.config.logging import get_logger, get_logger_with_context
from src.config.settings import get_settings
from src.database.connection import get_session_maker
from src.models.generation import GeneratedImage, GenerationMetadata, GenerationRequest
from src.services.error_handler import ApplicationError
from src.services.queue_manager import QueueManager

logger = get_logger(__name__)


class DiffusePilotBot(discord.Client):
    """Diffuse Pilot Discord Bot"""

    def __init__(self):
        intents = discord.Intents.default()
        # message_content intent is not needed for slash commands only
        super().__init__(intents=intents)

        self.tree = app_commands.CommandTree(self)
        self.settings = get_settings()
        self.session_maker = get_session_maker()
        self.queue_manager = QueueManager()

    async def setup_hook(self):
        """Bot セットアップ"""
        # コマンド登録
        await self.tree.sync()
        logger.info("Commands synced")

        # キューマネージャー開始
        await self.queue_manager.start()
        logger.info("Queue manager started")

    async def close(self):
        """Bot クローズ"""
        # キューマネージャー停止
        await self.queue_manager.stop()
        logger.info("Queue manager stopped")

        await super().close()

    async def on_ready(self):
        """Bot 準備完了"""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")


# Bot インスタンス
bot = DiffusePilotBot()


@bot.tree.command(name="generate", description="画像を生成します")
@app_commands.describe(
    instruction="生成したい画像の説明（日本語OK）",
    web_research="Webからベストプラクティスをリサーチして反映（デフォルト: False）",
)
async def generate_command(
    interaction: discord.Interaction, instruction: str, web_research: bool = False
):
    """画像生成コマンド

    Args:
        interaction: Discord インタラクション
        instruction: ユーザーの指示
        web_research: Webリサーチを実施するか
    """
    cmd_logger = get_logger_with_context(
        __name__,
        guild_id=str(interaction.guild_id),
        user_id=str(interaction.user.id),
    )

    try:
        cmd_logger.info(
            f"Generate command received: {instruction[:100]}...",
            extra={"instruction_length": len(instruction), "web_research": web_research},
        )

        # まずは応答（3秒以内に応答が必要）
        # 最初のメッセージを送信
        research_status = "（Webリサーチ有効）" if web_research else ""
        await interaction.response.send_message(
            f"🎨 画像生成を開始します...{research_status}\n指示: {instruction[:100]}{'...' if len(instruction) > 100 else ''}"
        )

        # メッセージからスレッドを作成（message_idを指定）
        # これによりBotが作成したメッセージから確実にスレッドを作成できる
        message = await interaction.original_response()
        thread = await interaction.channel.create_thread(
            name=f"生成: {instruction[:50]}",
            message=message,
            auto_archive_duration=1440,  # 24時間
        )

        # GenerationRequest を作成
        async with bot.session_maker() as session:
            request = GenerationRequest(
                guild_id=str(interaction.guild_id),
                user_id=str(interaction.user.id),
                thread_id=str(thread.id),
                original_instruction=instruction,
                web_research=web_research,
            )
            session.add(request)
            await session.commit()
            await session.refresh(request)

            cmd_logger.info(
                f"Generation request created: {request.id}",
                extra={"thread_id": thread.id},
            )

            # キューに追加
            await bot.queue_manager.enqueue_generation(request.id)

            await thread.send(
                f"✅ リクエストをキューに追加しました\n"
                f"リクエストID: `{request.id}`\n"
                f"画像生成中... お待ちください ☕"
            )

        # バックグラウンドで結果を監視して投稿
        asyncio.create_task(_monitor_and_post_results(request.id, thread))

    except Exception as e:
        cmd_logger.exception(f"Error in generate command: {str(e)}")
        error_msg = "エラーが発生しました。もう一度お試しください。"
        if isinstance(e, ApplicationError):
            error_msg = f"エラー: {e.message}"

        try:
            await interaction.followup.send(f"❌ {error_msg}", ephemeral=True)
        except Exception:
            pass


@bot.tree.command(name="generate_gemini", description="Gemini APIで画像を生成します")
@app_commands.describe(instruction="生成したい画像の説明（日本語OK）")
async def generate_gemini_command(interaction: discord.Interaction, instruction: str):
    """Gemini APIを使用した画像生成コマンド

    Args:
        interaction: Discord インタラクション
        instruction: ユーザーの指示
    """
    cmd_logger = get_logger_with_context(
        __name__,
        guild_id=str(interaction.guild_id),
        user_id=str(interaction.user.id),
    )

    try:
        cmd_logger.info(
            f"Generate Gemini command received: {instruction[:100]}...",
            extra={"instruction_length": len(instruction)},
        )

        # まずは応答（3秒以内に応答が必要）
        await interaction.response.send_message(
            f"✨ Gemini APIで画像生成を開始します...\n指示: {instruction[:100]}{'...' if len(instruction) > 100 else ''}"
        )

        # メッセージからスレッドを作成
        message = await interaction.original_response()
        thread = await interaction.channel.create_thread(
            name=f"Gemini生成: {instruction[:50]}",
            message=message,
            auto_archive_duration=1440,  # 24時間
        )

        # GenerationRequest を作成（Geminiモードフラグを追加）
        async with bot.session_maker() as session:
            request = GenerationRequest(
                guild_id=str(interaction.guild_id),
                user_id=str(interaction.user.id),
                thread_id=str(thread.id),
                original_instruction=instruction,
            )
            session.add(request)
            await session.commit()
            await session.refresh(request)

            cmd_logger.info(
                f"Gemini generation request created: {request.id}",
                extra={"thread_id": thread.id},
            )

            # Geminiモード専用のキューに追加
            await bot.queue_manager.enqueue_gemini_generation(request.id)

            await thread.send(
                f"✅ Geminiリクエストをキューに追加しました\n"
                f"リクエストID: `{request.id}`\n"
                f"🧠 Gemini APIで画像生成中... お待ちください ☕"
            )

        # バックグラウンドで結果を監視して投稿
        asyncio.create_task(_monitor_and_post_results(request.id, thread))

    except Exception as e:
        cmd_logger.exception(f"Error in generate gemini command: {str(e)}")
        error_msg = "エラーが発生しました。もう一度お試しください。"
        if isinstance(e, ApplicationError):
            error_msg = f"エラー: {e.message}"

        try:
            await interaction.followup.send(f"❌ {error_msg}", ephemeral=True)
        except Exception:
            pass


@bot.tree.command(name="generate_xai", description="xAI API（Grok）で画像を生成します")
@app_commands.describe(instruction="生成したい画像の説明（日本語OK）")
async def generate_xai_command(interaction: discord.Interaction, instruction: str):
    """xAI APIを使用した画像生成コマンド

    Args:
        interaction: Discord インタラクション
        instruction: ユーザーの指示
    """
    cmd_logger = get_logger_with_context(
        __name__,
        guild_id=str(interaction.guild_id),
        user_id=str(interaction.user.id),
    )

    try:
        cmd_logger.info(
            f"Generate xAI command received: {instruction[:100]}...",
            extra={"instruction_length": len(instruction)},
        )

        # まずは応答（3秒以内に応答が必要）
        await interaction.response.send_message(
            f"🤖 xAI API（Grok）で画像生成を開始します...\n指示: {instruction[:100]}{'...' if len(instruction) > 100 else ''}"
        )

        # メッセージからスレッドを作成
        message = await interaction.original_response()
        thread = await interaction.channel.create_thread(
            name=f"xAI生成: {instruction[:50]}",
            message=message,
            auto_archive_duration=1440,  # 24時間
        )

        # GenerationRequest を作成（xAIモード）
        async with bot.session_maker() as session:
            request = GenerationRequest(
                guild_id=str(interaction.guild_id),
                user_id=str(interaction.user.id),
                thread_id=str(thread.id),
                original_instruction=instruction,
            )
            session.add(request)
            await session.commit()
            await session.refresh(request)

            cmd_logger.info(
                f"xAI generation request created: {request.id}",
                extra={"thread_id": thread.id},
            )

            # xAIモード専用のキューに追加
            await bot.queue_manager.enqueue_xai_generation(request.id)

            await thread.send(
                f"✅ xAIリクエストをキューに追加しました\n"
                f"リクエストID: `{request.id}`\n"
                f"🤖 xAI API（Grok-2-Image）で画像生成中... お待ちください ☕"
            )

        # バックグラウンドで結果を監視して投稿
        asyncio.create_task(_monitor_and_post_results(request.id, thread))

    except Exception as e:
        cmd_logger.exception(f"Error in generate xai command: {str(e)}")
        error_msg = "エラーが発生しました。もう一度お試しください。"
        if isinstance(e, ApplicationError):
            error_msg = f"エラー: {e.message}"

        try:
            await interaction.followup.send(f"❌ {error_msg}", ephemeral=True)
        except Exception:
            pass


async def _monitor_and_post_results(request_id: str, thread: discord.Thread):
    """リクエストの完了を監視して結果を投稿

    Args:
        request_id: リクエスト ID
        thread: Discord スレッド
    """
    monitor_logger = get_logger_with_context(__name__, request_id=request_id)

    try:
        # リクエストが完了するまで待機（最大30分）
        for _ in range(180):  # 10秒 x 180 = 30分
            await asyncio.sleep(10)

            async with bot.session_maker() as session:
                # リクエスト状態を確認
                stmt = select(GenerationRequest).where(GenerationRequest.id == request_id)
                result = await session.execute(stmt)
                request = result.scalar_one_or_none()

                if not request:
                    monitor_logger.error("Request not found")
                    await thread.send("❌ エラー: リクエストが見つかりません")
                    return

                if request.status == "completed":
                    # 完了: 画像を投稿
                    monitor_logger.info("Request completed, posting images")

                    # 画像を取得
                    stmt = select(GeneratedImage).where(GeneratedImage.request_id == request_id)
                    result = await session.execute(stmt)
                    images = result.scalars().all()

                    if not images:
                        await thread.send("❌ エラー: 画像が生成されませんでした")
                        return

                    # メタデータ情報を取得（eager loading）
                    stmt = select(GenerationMetadata).where(
                        GenerationMetadata.request_id == request_id
                    )
                    result = await session.execute(stmt)
                    metadata = result.scalar_one_or_none()

                    if metadata:
                        # 基本パラメータ
                        param_lines = [
                            f"• モデル: {metadata.model_name}",
                            f"• サイズ: {metadata.width}x{metadata.height}",
                            f"• ステップ数: {metadata.steps}",
                            f"• CFG Scale: {metadata.cfg_scale}",
                            f"• サンプラー: {metadata.sampler}",
                            f"• Seed: {metadata.seed}",
                        ]

                        # スケジューラー
                        if metadata.scheduler:
                            param_lines.append(f"• スケジューラー: {metadata.scheduler}")

                        # LoRA
                        if metadata.lora_list:
                            lora_names = ", ".join(
                                [lora.get("name", "unknown") for lora in metadata.lora_list]
                            )
                            param_lines.append(f"• LoRA: {lora_names}")

                        # Negative prompt（長い場合は省略）
                        if metadata.negative_prompt:
                            neg_prompt_display = metadata.negative_prompt[:100]
                            if len(metadata.negative_prompt) > 100:
                                neg_prompt_display += "..."
                            param_lines.append(f"• ネガティブプロンプト: {neg_prompt_display}")

                        # raw_paramsから追加パラメータを取得
                        if metadata.raw_params:
                            raw = metadata.raw_params

                            # バッチ設定
                            if raw.get("batch_size") and raw["batch_size"] > 1:
                                param_lines.append(f"• バッチサイズ: {raw['batch_size']}")
                            if raw.get("batch_count") and raw["batch_count"] > 1:
                                param_lines.append(f"• バッチカウント: {raw['batch_count']}")

                            # Hires. fix設定
                            if raw.get("enable_hr"):
                                param_lines.append("• Hires. fix: 有効")
                                if raw.get("hr_scale"):
                                    param_lines.append(f"  - Upscale by: {raw['hr_scale']}")
                                if raw.get("hr_upscaler"):
                                    param_lines.append(f"  - Upscaler: {raw['hr_upscaler']}")
                                if raw.get("hr_second_pass_steps"):
                                    param_lines.append(
                                        f"  - ステップ数: {raw['hr_second_pass_steps']}"
                                    )
                                if raw.get("denoising_strength"):
                                    param_lines.append(
                                        f"  - Denoising strength: {raw['denoising_strength']}"
                                    )

                            # 古いパラメータ名もサポート（互換性のため）
                            elif raw.get("upscale_by"):
                                param_lines.append(f"• Upscale by: {raw['upscale_by']}")
                                if raw.get("hires_upscaler"):
                                    param_lines.append(
                                        f"• Hires. fix Upscaler: {raw['hires_upscaler']}"
                                    )
                                if raw.get("hires_steps"):
                                    param_lines.append(
                                        f"• Hires. fix ステップ数: {raw['hires_steps']}"
                                    )
                                if raw.get("denoising_strength"):
                                    param_lines.append(
                                        f"• Denoising strength: {raw['denoising_strength']}"
                                    )

                            # Refiner設定
                            if raw.get("refiner_checkpoint"):
                                param_lines.append(
                                    f"• Refiner checkpoint: {raw['refiner_checkpoint']}"
                                )
                                if raw.get("refiner_switch_at"):
                                    param_lines.append(f"  - Switch at: {raw['refiner_switch_at']}")

                            # その他のSD APIパラメータ（主要なもののみ表示）
                            extra_params_to_display = [
                                ("restore_faces", "顔修復"),
                                ("tiling", "タイリング"),
                                ("subseed", "Subseed"),
                                ("subseed_strength", "Subseed strength"),
                                ("clip_skip", "CLIP skip"),
                            ]
                            for param_key, param_label in extra_params_to_display:
                                if param_key in raw and raw[param_key] is not None:
                                    param_lines.append(f"• {param_label}: {raw[param_key]}")

                        info_text = f"🎉 画像生成が完了しました！ ({len(images)}枚)\n\n"

                        # Webリサーチ結果を表示
                        if metadata.raw_params and metadata.raw_params.get("web_research"):
                            research = metadata.raw_params["web_research"]
                            info_text += "**📚 Webリサーチサマリー:**\n"
                            if research.get("summary"):
                                info_text += f"{research['summary']}\n\n"
                            if research.get("prompt_techniques"):
                                techniques = ", ".join(
                                    research["prompt_techniques"][:3]
                                )  # 最初の3つだけ表示
                                info_text += f"💡 推奨テクニック: {techniques}\n"
                            if research.get("sources"):
                                # 最初の2つのソースだけ表示
                                sources = research["sources"][:2]
                                info_text += f"📖 参照元: {', '.join(sources)}\n\n"

                        info_text += (
                            f"**プロンプト:**\n```\n{metadata.prompt[:500]}\n```\n"
                            f"**パラメータ:**\n" + "\n".join(param_lines)
                        )
                        await thread.send(info_text)

                    # 画像を投稿
                    for i, img in enumerate(images):
                        file_path = Path(img.file_path)
                        if file_path.exists():
                            discord_file = discord.File(file_path, filename=file_path.name)
                            await thread.send(f"画像 {i + 1}/{len(images)}", file=discord_file)
                        else:
                            monitor_logger.error(f"Image file not found: {file_path}")

                    await thread.send(
                        "✨ 生成完了！追加の指示があればこのスレッドに返信してください。"
                    )
                    return

                elif request.status == "failed":
                    # 失敗
                    monitor_logger.error(f"Request failed: {request.error_message}")
                    await thread.send(
                        f"❌ 画像生成に失敗しました\n"
                        f"エラー: {request.error_message or '不明なエラー'}"
                    )
                    return

        # タイムアウト
        monitor_logger.warning("Request monitoring timeout")
        await thread.send("⚠️ タイムアウト: 生成に時間がかかっています...")

    except Exception as e:
        monitor_logger.exception(f"Error monitoring request: {str(e)}")
        try:
            await thread.send(f"❌ エラーが発生しました: {str(e)}")
        except Exception:
            pass


# Settings コマンドグループ
settings_group = app_commands.Group(name="settings", description="グローバル設定を管理します")


@settings_group.command(name="show", description="現在の設定を表示します")
async def settings_show_command(interaction: discord.Interaction):
    """設定表示コマンド"""
    cmd_logger = get_logger_with_context(
        __name__,
        guild_id=str(interaction.guild_id),
        user_id=str(interaction.user.id),
    )

    try:
        cmd_logger.info("Settings show command received")

        async with bot.session_maker() as session:
            from src.services.settings_service import SettingsService

            service = SettingsService(session)

            # ユーザー設定を取得
            user_settings = await service.get_settings(
                str(interaction.guild_id), str(interaction.user.id)
            )

            # サーバーデフォルト設定を取得
            server_settings = await service.get_settings(str(interaction.guild_id), None)

            # 表示用のテキスト作成
            settings_parts = []

            if user_settings:
                settings_parts.append("**あなたの設定:**\n" + _format_settings(user_settings))

            if server_settings:
                settings_parts.append(
                    "**サーバーデフォルト設定:**\n" + _format_settings(server_settings)
                )

            if settings_parts:
                settings_text = "\n\n".join(settings_parts)
                if user_settings and server_settings:
                    settings_text += "\n\n※ あなたの設定が優先的に適用されます"
                elif not user_settings:
                    settings_text += "\n\n※ あなた専用の設定はまだ作成されていません"
            else:
                settings_text = (
                    "設定がまだ作成されていません。\n`/settings set` で設定を作成できます。"
                )

            await interaction.response.send_message(settings_text, ephemeral=True)

    except Exception as e:
        cmd_logger.exception(f"Error in settings show command: {str(e)}")
        error_msg = "設定の取得に失敗しました。"
        try:
            await interaction.response.send_message(f"❌ {error_msg}", ephemeral=True)
        except Exception:
            pass


@settings_group.command(name="set", description="設定を更新します")
@app_commands.describe(
    setting_type="設定の種類",
    value="設定値",
    scope="設定の適用範囲（ユーザー専用 or サーバー全体）",
)
@app_commands.choices(
    setting_type=[
        app_commands.Choice(name="デフォルトモデル", value="model"),
        app_commands.Choice(name="デフォルトプロンプト suffix", value="prompt_suffix"),
        app_commands.Choice(name="ステップ数", value="steps"),
        app_commands.Choice(name="CFG スケール", value="cfg_scale"),
        app_commands.Choice(name="サンプラー", value="sampler"),
        app_commands.Choice(name="画像幅", value="width"),
        app_commands.Choice(name="画像高さ", value="height"),
        app_commands.Choice(name="シード値", value="seed"),
        app_commands.Choice(name="バッチサイズ", value="batch_size"),
        app_commands.Choice(name="バッチカウント", value="batch_count"),
        app_commands.Choice(name="Hires. fix Upscaler", value="hires_upscaler"),
        app_commands.Choice(name="Hires. fix ステップ数", value="hires_steps"),
        app_commands.Choice(name="Denoising strength", value="denoising_strength"),
        app_commands.Choice(name="Upscale by", value="upscale_by"),
        app_commands.Choice(name="Refiner checkpoint", value="refiner_checkpoint"),
        app_commands.Choice(name="Refiner switch at", value="refiner_switch_at"),
    ],
    scope=[
        app_commands.Choice(name="ユーザー専用", value="user"),
        app_commands.Choice(name="サーバー全体", value="server"),
    ],
)
async def settings_set_command(
    interaction: discord.Interaction,
    setting_type: str,
    value: str,
    scope: str = "user",
):
    """設定更新コマンド"""
    cmd_logger = get_logger_with_context(
        __name__,
        guild_id=str(interaction.guild_id),
        user_id=str(interaction.user.id),
    )

    try:
        cmd_logger.info(f"Settings set command received: {setting_type}={value}, scope={scope}")

        async with bot.session_maker() as session:
            from src.services.settings_service import SettingsService

            service = SettingsService(session)

            # scope に応じて user_id を設定
            target_user_id = str(interaction.user.id) if scope == "user" else None

            # 現在の設定を取得
            current_settings = await service.get_settings(str(interaction.guild_id), target_user_id)

            # 設定値を準備
            update_kwargs = {
                "guild_id": str(interaction.guild_id),
                "user_id": target_user_id,
            }

            # 既存の設定値を保持
            if current_settings:
                update_kwargs["default_model"] = current_settings.default_model
                update_kwargs["default_lora_list"] = current_settings.default_lora_list
                update_kwargs["default_prompt_suffix"] = current_settings.default_prompt_suffix
                update_kwargs["seed"] = current_settings.seed
                update_kwargs["batch_size"] = current_settings.batch_size
                update_kwargs["batch_count"] = current_settings.batch_count
                update_kwargs["hires_upscaler"] = current_settings.hires_upscaler
                update_kwargs["hires_steps"] = current_settings.hires_steps
                update_kwargs["denoising_strength"] = current_settings.denoising_strength
                update_kwargs["upscale_by"] = current_settings.upscale_by
                update_kwargs["refiner_checkpoint"] = current_settings.refiner_checkpoint
                update_kwargs["refiner_switch_at"] = current_settings.refiner_switch_at
                # 既存の default_sd_params をコピー（変更を加えるため）
                if current_settings.default_sd_params:
                    update_kwargs["default_sd_params"] = dict(current_settings.default_sd_params)
                else:
                    update_kwargs["default_sd_params"] = {}
            else:
                # 新規作成の場合は空の辞書を用意
                update_kwargs["default_sd_params"] = {}

            # 新しい値を適用
            if setting_type == "model":
                update_kwargs["default_model"] = value
            elif setting_type == "prompt_suffix":
                update_kwargs["default_prompt_suffix"] = value
            elif setting_type == "seed":
                update_kwargs["seed"] = int(value)
            elif setting_type == "batch_size":
                update_kwargs["batch_size"] = int(value)
            elif setting_type == "batch_count":
                update_kwargs["batch_count"] = int(value)
            elif setting_type == "hires_upscaler":
                update_kwargs["hires_upscaler"] = value
            elif setting_type == "hires_steps":
                update_kwargs["hires_steps"] = int(value)
            elif setting_type == "denoising_strength":
                update_kwargs["denoising_strength"] = float(value)
            elif setting_type == "upscale_by":
                update_kwargs["upscale_by"] = float(value)
            elif setting_type == "refiner_checkpoint":
                update_kwargs["refiner_checkpoint"] = value
            elif setting_type == "refiner_switch_at":
                update_kwargs["refiner_switch_at"] = float(value)
            elif setting_type in ["steps", "cfg_scale", "sampler", "width", "height"]:
                # default_sd_params は既に初期化済み
                if setting_type == "steps":
                    update_kwargs["default_sd_params"]["steps"] = int(value)
                elif setting_type == "cfg_scale":
                    update_kwargs["default_sd_params"]["cfg_scale"] = float(value)
                elif setting_type == "sampler":
                    update_kwargs["default_sd_params"]["sampler"] = value
                elif setting_type == "width":
                    update_kwargs["default_sd_params"]["width"] = int(value)
                elif setting_type == "height":
                    update_kwargs["default_sd_params"]["height"] = int(value)

            # 設定を更新
            await service.update_settings(**update_kwargs)

            scope_text = "ユーザー専用" if scope == "user" else "サーバー全体"
            await interaction.response.send_message(
                f"✅ 設定を更新しました ({scope_text}): {setting_type} = {value}", ephemeral=True
            )

    except ValueError as e:
        cmd_logger.error(f"Invalid value: {str(e)}")
        await interaction.response.send_message(f"❌ 無効な値です: {value}", ephemeral=True)
    except ApplicationError as e:
        cmd_logger.error(f"Application error: {e.message}")
        await interaction.response.send_message(f"❌ エラー: {e.user_message}", ephemeral=True)
    except Exception as e:
        cmd_logger.exception(f"Error in settings set command: {str(e)}")
        await interaction.response.send_message("❌ 設定の更新に失敗しました。", ephemeral=True)


@settings_group.command(name="reset", description="設定をリセットします")
@app_commands.describe(
    scope="設定の適用範囲（ユーザー専用 or サーバー全体）",
)
@app_commands.choices(
    scope=[
        app_commands.Choice(name="ユーザー専用", value="user"),
        app_commands.Choice(name="サーバー全体", value="server"),
    ],
)
async def settings_reset_command(interaction: discord.Interaction, scope: str = "user"):
    """設定リセットコマンド"""
    cmd_logger = get_logger_with_context(
        __name__,
        guild_id=str(interaction.guild_id),
        user_id=str(interaction.user.id),
    )

    try:
        cmd_logger.info(f"Settings reset command received: scope={scope}")

        async with bot.session_maker() as session:
            from src.services.settings_service import SettingsService

            service = SettingsService(session)

            # scope に応じて user_id を設定
            target_user_id = str(interaction.user.id) if scope == "user" else None

            # 設定を削除
            deleted = await service.delete_settings(str(interaction.guild_id), target_user_id)

            scope_text = "ユーザー専用" if scope == "user" else "サーバー全体"
            if deleted:
                await interaction.response.send_message(
                    f"✅ 設定をリセットしました ({scope_text})。", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "ℹ️ 設定が見つかりませんでした。", ephemeral=True
                )

    except Exception as e:
        cmd_logger.exception(f"Error in settings reset command: {str(e)}")
        await interaction.response.send_message("❌ 設定のリセットに失敗しました。", ephemeral=True)


def _format_settings(settings) -> str:
    """設定を表示用にフォーマット"""
    lines = []

    if settings.default_model:
        lines.append(f"• デフォルトモデル: `{settings.default_model}`")

    if settings.default_lora_list:
        lora_list = settings.default_lora_list
        if isinstance(lora_list, list):
            lora_names = ", ".join([lora.get("name", "unknown") for lora in lora_list])
        else:
            lora_names = str(lora_list)
        lines.append(f"• デフォルト LoRA: `{lora_names}`")

    if settings.default_prompt_suffix:
        suffix = settings.default_prompt_suffix[:50]
        if len(settings.default_prompt_suffix) > 50:
            suffix += "..."
        lines.append(f"• プロンプト suffix: `{suffix}`")

    if settings.default_sd_params:
        params = settings.default_sd_params
        lines.append("• SD パラメータ:")
        if "steps" in params:
            lines.append(f"  - ステップ数: `{params['steps']}`")
        if "cfg_scale" in params:
            lines.append(f"  - CFG スケール: `{params['cfg_scale']}`")
        if "sampler" in params:
            lines.append(f"  - サンプラー: `{params['sampler']}`")
        if "width" in params:
            lines.append(f"  - 画像幅: `{params['width']}`")
        if "height" in params:
            lines.append(f"  - 画像高さ: `{params['height']}`")

    # 新しいパラメータを表示
    if settings.seed is not None:
        lines.append(f"• シード値: `{settings.seed}`")
    if settings.batch_size is not None:
        lines.append(f"• バッチサイズ: `{settings.batch_size}`")
    if settings.batch_count is not None:
        lines.append(f"• バッチカウント: `{settings.batch_count}`")
    if settings.hires_upscaler:
        lines.append(f"• Hires. fix Upscaler: `{settings.hires_upscaler}`")
    if settings.hires_steps is not None:
        lines.append(f"• Hires. fix ステップ数: `{settings.hires_steps}`")
    if settings.denoising_strength is not None:
        lines.append(f"• Denoising strength: `{settings.denoising_strength}`")
    if settings.upscale_by is not None:
        lines.append(f"• Upscale by: `{settings.upscale_by}`")
    if settings.refiner_checkpoint:
        lines.append(f"• Refiner checkpoint: `{settings.refiner_checkpoint}`")
    if settings.refiner_switch_at is not None:
        lines.append(f"• Refiner switch at: `{settings.refiner_switch_at}`")

    if not lines:
        return "（設定なし）"

    return "\n".join(lines)


# settings グループを bot.tree に追加
bot.tree.add_command(settings_group)


# SD Options コマンド（個別のトップレベルコマンドとして登録）
@bot.tree.command(name="models", description="利用可能なモデルの一覧を表示します")
async def sd_models_command(interaction: discord.Interaction):
    """モデル一覧取得コマンド"""
    cmd_logger = get_logger_with_context(
        __name__,
        guild_id=str(interaction.guild_id),
        user_id=str(interaction.user.id),
    )

    try:
        cmd_logger.info("SD models command received")

        # まず応答（時間がかかる可能性があるため）
        await interaction.response.defer(ephemeral=True)

        from src.services.sd_client import StableDiffusionClient

        client = StableDiffusionClient()
        try:
            models = await client.get_models()

            if not models:
                await interaction.followup.send(
                    "利用可能なモデルが見つかりませんでした。", ephemeral=True
                )
                return

            # モデルリストを整形（長すぎる場合は分割）
            model_text = "\n".join([f"• `{model}`" for model in models])

            # Discordのメッセージ長制限（2000文字）を考慮
            if len(model_text) > 1900:
                # 分割して送信
                chunks = []
                current_chunk = "**利用可能なモデル:**\n"
                for model in models:
                    line = f"• `{model}`\n"
                    if len(current_chunk) + len(line) > 1900:
                        chunks.append(current_chunk)
                        current_chunk = ""
                    current_chunk += line
                if current_chunk:
                    chunks.append(current_chunk)

                for chunk in chunks:
                    await interaction.followup.send(chunk, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"**利用可能なモデル ({len(models)}個):**\n{model_text}", ephemeral=True
                )

        finally:
            await client.close()

    except Exception as e:
        cmd_logger.exception(f"Error in sd models command: {str(e)}")
        try:
            await interaction.followup.send("❌ モデル一覧の取得に失敗しました。", ephemeral=True)
        except Exception:
            pass


@bot.tree.command(name="loras", description="利用可能な LoRA の一覧を表示します")
async def sd_loras_command(interaction: discord.Interaction):
    """LoRA一覧取得コマンド"""
    cmd_logger = get_logger_with_context(
        __name__,
        guild_id=str(interaction.guild_id),
        user_id=str(interaction.user.id),
    )

    try:
        cmd_logger.info("SD LoRAs command received")

        await interaction.response.defer(ephemeral=True)

        from src.services.sd_client import StableDiffusionClient

        client = StableDiffusionClient()
        try:
            loras = await client.get_loras()

            if not loras:
                await interaction.followup.send(
                    "利用可能な LoRA が見つかりませんでした。", ephemeral=True
                )
                return

            # LoRAリストを整形
            lora_lines = []
            for lora in loras:
                name = lora.get("name", "unknown")
                alias = lora.get("alias", "")
                if alias and alias != name:
                    lora_lines.append(f"• `{name}` (別名: {alias})")
                else:
                    lora_lines.append(f"• `{name}`")

            lora_text = "\n".join(lora_lines)

            # Discordのメッセージ長制限を考慮
            if len(lora_text) > 1900:
                chunks = []
                current_chunk = "**利用可能な LoRA:**\n"
                for line in lora_lines:
                    if len(current_chunk) + len(line) + 1 > 1900:
                        chunks.append(current_chunk)
                        current_chunk = ""
                    current_chunk += line + "\n"
                if current_chunk:
                    chunks.append(current_chunk)

                for chunk in chunks:
                    await interaction.followup.send(chunk, ephemeral=True)
            else:
                await interaction.followup.send(
                    f"**利用可能な LoRA ({len(loras)}個):**\n{lora_text}", ephemeral=True
                )

        finally:
            await client.close()

    except Exception as e:
        cmd_logger.exception(f"Error in sd loras command: {str(e)}")
        try:
            await interaction.followup.send("❌ LoRA 一覧の取得に失敗しました。", ephemeral=True)
        except Exception:
            pass


@bot.tree.command(name="samplers", description="利用可能なサンプラーの一覧を表示します")
async def sd_samplers_command(interaction: discord.Interaction):
    """サンプラー一覧取得コマンド"""
    cmd_logger = get_logger_with_context(
        __name__,
        guild_id=str(interaction.guild_id),
        user_id=str(interaction.user.id),
    )

    try:
        cmd_logger.info("SD samplers command received")

        await interaction.response.defer(ephemeral=True)

        from src.services.sd_client import StableDiffusionClient

        client = StableDiffusionClient()
        try:
            samplers = await client.get_samplers()

            if not samplers:
                await interaction.followup.send(
                    "利用可能なサンプラーが見つかりませんでした。", ephemeral=True
                )
                return

            sampler_text = "\n".join([f"• `{sampler}`" for sampler in samplers])
            await interaction.followup.send(
                f"**利用可能なサンプラー ({len(samplers)}個):**\n{sampler_text}", ephemeral=True
            )

        finally:
            await client.close()

    except Exception as e:
        cmd_logger.exception(f"Error in sd samplers command: {str(e)}")
        try:
            await interaction.followup.send(
                "❌ サンプラー一覧の取得に失敗しました。", ephemeral=True
            )
        except Exception:
            pass


@bot.tree.command(name="schedulers", description="利用可能なスケジューラの一覧を表示します")
async def sd_schedulers_command(interaction: discord.Interaction):
    """スケジューラ一覧取得コマンド"""
    cmd_logger = get_logger_with_context(
        __name__,
        guild_id=str(interaction.guild_id),
        user_id=str(interaction.user.id),
    )

    try:
        cmd_logger.info("SD schedulers command received")

        await interaction.response.defer(ephemeral=True)

        from src.services.sd_client import StableDiffusionClient

        client = StableDiffusionClient()
        try:
            schedulers = await client.get_schedulers()

            if not schedulers:
                await interaction.followup.send(
                    "利用可能なスケジューラが見つかりませんでした。", ephemeral=True
                )
                return

            scheduler_text = "\n".join([f"• `{scheduler}`" for scheduler in schedulers])
            await interaction.followup.send(
                f"**利用可能なスケジューラ ({len(schedulers)}個):**\n{scheduler_text}",
                ephemeral=True,
            )

        finally:
            await client.close()

    except Exception as e:
        cmd_logger.exception(f"Error in sd schedulers command: {str(e)}")
        try:
            await interaction.followup.send(
                "❌ スケジューラ一覧の取得に失敗しました。", ephemeral=True
            )
        except Exception:
            pass


@bot.tree.command(name="upscalers", description="利用可能なアップスケーラーの一覧を表示します")
async def sd_upscalers_command(interaction: discord.Interaction):
    """アップスケーラー一覧取得コマンド"""
    cmd_logger = get_logger_with_context(
        __name__,
        guild_id=str(interaction.guild_id),
        user_id=str(interaction.user.id),
    )

    try:
        cmd_logger.info("SD upscalers command received")

        await interaction.response.defer(ephemeral=True)

        from src.services.sd_client import StableDiffusionClient

        client = StableDiffusionClient()
        try:
            upscalers = await client.get_upscalers()

            if not upscalers:
                await interaction.followup.send(
                    "利用可能なアップスケーラーが見つかりませんでした。", ephemeral=True
                )
                return

            upscaler_text = "\n".join([f"• `{upscaler}`" for upscaler in upscalers])
            await interaction.followup.send(
                f"**利用可能なアップスケーラー ({len(upscalers)}個):**\n{upscaler_text}",
                ephemeral=True,
            )

        finally:
            await client.close()

    except Exception as e:
        cmd_logger.exception(f"Error in sd upscalers command: {str(e)}")
        try:
            await interaction.followup.send(
                "❌ アップスケーラー一覧の取得に失敗しました。", ephemeral=True
            )
        except Exception:
            pass


@bot.tree.command(name="ping", description="Bot の応答を確認します")
async def ping_command(interaction: discord.Interaction):
    """Ping コマンド"""
    await interaction.response.send_message(f"🏓 Pong! レイテンシ: {round(bot.latency * 1000)}ms")


async def run_bot():
    """Bot を起動"""
    try:
        settings = get_settings()
        await bot.start(settings.discord_bot_token)
    except Exception as e:
        logger.exception(f"Error running bot: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(run_bot())
