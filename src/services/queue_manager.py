"""
タスクキューマネージャー

asyncio.Queue ベースの軽量タスクキューシステム
"""

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import get_logger, get_logger_with_context
from src.config.settings import get_settings
from src.database.connection import get_session_maker
from src.models.generation import (
    GeneratedImage,
    GenerationMetadata,
    GenerationRequest,
    RequestStatus,
)
from src.services.error_handler import ApplicationError, DatabaseError, ErrorCode
from src.services.prompt_agent import PromptAgent
from src.services.sd_client import SDGenerationParams, StableDiffusionClient

logger = get_logger(__name__)


@dataclass(order=True)
class QueuedTask:
    """キューイングされたタスク（メモリ内）"""

    priority: int = 0  # 優先度（PriorityQueueで使用）
    request_id: str = ""
    use_gemini: bool = False
    use_xai: bool = False


class QueueManager:
    """タスクキューマネージャー（asyncio.Queue ベース）"""

    # グローバル設定のパラメータ名リスト
    _EXTRA_SETTINGS_PARAMS = [
        "batch_size",
        "batch_count",
        "hires_upscaler",
        "hires_steps",
        "denoising_strength",
        "upscale_by",
        "refiner_checkpoint",
        "refiner_switch_at",
    ]

    def __init__(self):
        self.settings = get_settings()
        self.session_maker = get_session_maker()
        self.is_running = False
        self.worker_task: asyncio.Task | None = None

        # 優先度付きキュー（priority, request_id のタプル）
        self.queue: asyncio.PriorityQueue = asyncio.PriorityQueue()

        # サービスクライアント
        self.prompt_agent = PromptAgent()
        self.sd_client = StableDiffusionClient()

    async def start(self):
        """キューワーカーを開始"""
        if self.is_running:
            logger.warning("Queue worker already running")
            return

        self.is_running = True

        # DB から未完了のリクエストを復元
        await self._restore_pending_requests()

        # ワーカー起動
        self.worker_task = asyncio.create_task(self._worker_loop())
        logger.info("Queue worker started")

    async def _restore_pending_requests(self):
        """起動時に未完了のリクエストをキューに復元"""
        async with self.session_maker() as session:
            # PENDING または PROCESSING 状態のリクエストを取得
            stmt = select(GenerationRequest).where(
                GenerationRequest.status.in_([RequestStatus.PENDING, RequestStatus.PROCESSING])
            )
            result = await session.execute(stmt)
            pending_requests = result.scalars().all()

            for request in pending_requests:
                # ステータスを PENDING に戻す
                request.status = RequestStatus.PENDING
                # キューに追加（優先度は0、通常モード）
                task = QueuedTask(priority=0, request_id=request.id, use_gemini=False)
                await self.queue.put(task)

            if pending_requests:
                await session.commit()
                logger.info(f"Restored {len(pending_requests)} pending requests to queue")

    async def stop(self):
        """キューワーカーを停止"""
        if not self.is_running:
            return

        self.is_running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass

        # クライアントを閉じる
        await self.prompt_agent.close()
        await self.sd_client.close()

        logger.info("Queue worker stopped")

    async def enqueue_generation(self, request_id: str, priority: int = 0) -> None:
        """画像生成タスクをキューに追加

        Args:
            request_id: GenerationRequest の ID
            priority: 優先度（高いほど優先）
        """
        # PriorityQueue は小さい値が優先されるため、負の値にする
        task = QueuedTask(priority=-priority, request_id=request_id, use_gemini=False)
        await self.queue.put(task)

        logger.info(
            f"Task enqueued: {request_id}",
            extra={"request_id": request_id, "priority": priority},
        )

    async def enqueue_gemini_generation(self, request_id: str, priority: int = 0) -> None:
        """Gemini APIを使用した画像生成タスクをキューに追加

        Args:
            request_id: GenerationRequest の ID
            priority: 優先度（高いほど優先）
        """
        # PriorityQueue は小さい値が優先されるため、負の値にする
        task = QueuedTask(priority=-priority, request_id=request_id, use_gemini=True)
        await self.queue.put(task)

        logger.info(
            f"Gemini task enqueued: {request_id}",
            extra={"request_id": request_id, "priority": priority, "mode": "gemini"},
        )

    async def enqueue_xai_generation(self, request_id: str, priority: int = 0) -> None:
        """xAI APIを使用した画像生成タスクをキューに追加

        Args:
            request_id: GenerationRequest の ID
            priority: 優先度（高いほど優先）
        """
        # PriorityQueue は小さい値が優先されるため、負の値にする
        task = QueuedTask(priority=-priority, request_id=request_id, use_xai=True)
        await self.queue.put(task)

        logger.info(
            f"xAI task enqueued: {request_id}",
            extra={"request_id": request_id, "priority": priority, "mode": "xai"},
        )

    async def _worker_loop(self):
        """ワーカーループ（イベント駆動）"""
        logger.info("Worker loop started")

        while self.is_running:
            try:
                # キューからタスクを取得（ブロッキング、タスクがあるまで待機）
                task: QueuedTask = await self.queue.get()

                # タスクを処理
                if task.use_gemini:
                    await self._process_gemini_generation(task.request_id)
                elif task.use_xai:
                    await self._process_xai_generation(task.request_id)
                else:
                    await self._process_image_generation(task.request_id)

                # タスク完了を通知
                self.queue.task_done()

            except asyncio.CancelledError:
                logger.info("Worker loop cancelled")
                break
            except Exception as e:
                logger.exception(f"Error in worker loop: {str(e)}")
                # エラーが発生しても続行
                await asyncio.sleep(self.settings.queue_error_retry_interval)

        logger.info("Worker loop ended")

    async def _process_image_generation(self, request_id: str):
        """画像生成タスクを処理

        Args:
            request_id: GenerationRequest の ID
        """
        task_logger = get_logger_with_context(__name__, request_id=request_id)

        async with self.session_maker() as session:
            # リクエストを取得
            request = await self._get_request(session, request_id)
            if not request:
                raise DatabaseError(f"Request not found: {request_id}")

            task_logger.info(
                f"Processing image generation for request: {request_id}",
                extra={
                    "guild_id": request.guild_id,
                    "user_id": request.user_id,
                    "instruction": request.original_instruction[:100],
                },
            )

            try:
                # ステータスを PROCESSING に更新
                request.status = RequestStatus.PROCESSING
                await session.commit()

                # グローバル設定をロード
                task_logger.info("Loading global settings...")
                from src.services.settings_service import SettingsService

                settings_service = SettingsService(session)
                user_settings = await settings_service.get_settings(
                    request.guild_id, request.user_id
                )
                server_settings = await settings_service.get_settings(request.guild_id, None)

                # ユーザー設定がある場合はそれを優先、なければサーバー設定
                global_settings = None
                if user_settings:
                    global_settings = self._extract_global_settings(user_settings)
                    task_logger.info("Using user settings")
                elif server_settings:
                    global_settings = self._extract_global_settings(server_settings)
                    task_logger.info("Using server default settings")

                # プロンプト生成
                task_logger.info("Generating prompt...")
                prompt_result = await self.prompt_agent.generate_prompt(
                    request.original_instruction,
                    global_settings=global_settings,
                    web_research=request.web_research,
                )

                # GenerationMetadata を作成
                # デフォルトモデルを設定から取得（設定がなければ "default"）
                model_name = "default"
                if global_settings and global_settings.get("default_model"):
                    model_name = global_settings["default_model"]
                elif "model_name" in prompt_result:
                    model_name = prompt_result["model_name"]

                # デフォルト LoRA を設定から取得
                lora_list = prompt_result.get("lora_list")
                if global_settings and global_settings.get("default_lora_list"):
                    lora_list = global_settings["default_lora_list"]

                # raw_paramsにグローバル設定のパラメータも含める
                raw_params = dict(prompt_result)
                self._apply_global_settings_to_dict(global_settings, raw_params)

                metadata = GenerationMetadata(
                    request_id=request.id,
                    prompt=prompt_result["prompt"],
                    negative_prompt=prompt_result.get("negative_prompt", ""),
                    model_name=model_name,
                    lora_list=lora_list,
                    steps=prompt_result["steps"],
                    cfg_scale=prompt_result["cfg_scale"],
                    sampler=prompt_result["sampler"],
                    scheduler=prompt_result.get("scheduler"),
                    seed=prompt_result["seed"],
                    width=prompt_result["width"],
                    height=prompt_result["height"],
                    raw_params=raw_params,
                )
                session.add(metadata)
                await session.commit()
                await session.refresh(metadata)

                task_logger.info(
                    f"Prompt generated: {len(metadata.prompt)} chars",
                    extra={"metadata_id": metadata.id},
                )

                # 画像生成
                task_logger.info("Generating images with SD API...")

                # batch_sizeを設定から取得（グローバル設定 > デフォルト値）
                batch_size = self.settings.default_image_count
                if global_settings and global_settings.get("batch_size") is not None:
                    batch_size = global_settings["batch_size"]

                # SD APIパラメータを構築
                sd_params_kwargs = {
                    "prompt": metadata.prompt,
                    "negative_prompt": metadata.negative_prompt,
                    "steps": metadata.steps,
                    "cfg_scale": metadata.cfg_scale,
                    "sampler": metadata.sampler,
                    "seed": metadata.seed,
                    "width": metadata.width,
                    "height": metadata.height,
                    "batch_size": batch_size,
                }

                # グローバル設定から追加パラメータを適用
                self._apply_global_settings_to_sd_params(global_settings, sd_params_kwargs)

                sd_params = SDGenerationParams(**sd_params_kwargs)

                images = await self.sd_client.txt2img(sd_params)
                task_logger.info(f"Generated {len(images)} images")

                # 画像を保存
                task_logger.info("Saving images to storage...")
                for i, img in enumerate(images):
                    # ファイル名生成
                    image_id = str(uuid.uuid4())
                    filename = f"{image_id}.png"
                    file_path = self.settings.image_storage_path / filename

                    # 画像を保存
                    img.save(file_path, format="PNG")
                    file_size = file_path.stat().st_size

                    # DB に保存
                    generated_image = GeneratedImage(
                        request_id=request.id,
                        metadata_id=metadata.id,
                        file_path=str(file_path),
                        file_size_bytes=file_size,
                    )
                    session.add(generated_image)

                    task_logger.info(
                        f"Saved image {i + 1}/{len(images)}: {filename}",
                        extra={"file_size": file_size},
                    )

                await session.commit()

                # リクエストを COMPLETED に更新
                request.status = RequestStatus.COMPLETED
                await session.commit()

                task_logger.info(f"Image generation completed for request: {request_id}")

            except ApplicationError as e:
                # アプリケーションエラー
                request.status = RequestStatus.FAILED
                request.error_message = e.message
                await session.commit()
                raise

            except Exception as e:
                # 予期しないエラー
                request.status = RequestStatus.FAILED
                request.error_message = str(e)
                await session.commit()
                raise

    async def _get_request(
        self, session: AsyncSession, request_id: str
    ) -> GenerationRequest | None:
        """GenerationRequest を取得"""
        stmt = select(GenerationRequest).where(GenerationRequest.id == request_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    def _extract_global_settings(self, settings) -> dict:
        """GlobalSettingsオブジェクトから設定辞書を抽出

        Args:
            settings: GlobalSettingsオブジェクト

        Returns:
            グローバル設定の辞書
        """
        global_settings = {
            "default_model": settings.default_model,
            "default_lora_list": settings.default_lora_list,
            "default_prompt_suffix": settings.default_prompt_suffix,
            "default_sd_params": settings.default_sd_params,
            "seed": settings.seed,
        }
        # 追加パラメータをループで設定
        for param_name in self._EXTRA_SETTINGS_PARAMS:
            global_settings[param_name] = getattr(settings, param_name, None)

        return global_settings

    def _apply_global_settings_to_dict(
        self, global_settings: dict | None, target_dict: dict
    ) -> None:
        """グローバル設定を辞書に適用

        Args:
            global_settings: グローバル設定
            target_dict: 適用先の辞書
        """
        if not global_settings:
            return

        # クラス定数のパラメータリストを使用
        for param_name in self._EXTRA_SETTINGS_PARAMS:
            value = global_settings.get(param_name)
            if value is not None:
                target_dict[param_name] = value

    def _apply_global_settings_to_sd_params(
        self, global_settings: dict | None, sd_params_kwargs: dict
    ) -> None:
        """グローバル設定をSD APIパラメータに適用

        Args:
            global_settings: グローバル設定
            sd_params_kwargs: SD APIパラメータ辞書
        """
        if not global_settings:
            return

        # Hires. fix設定
        if global_settings.get("hires_upscaler"):
            sd_params_kwargs["hr_upscaler"] = global_settings["hires_upscaler"]
        if global_settings.get("hires_steps") is not None:
            sd_params_kwargs["hr_second_pass_steps"] = global_settings["hires_steps"]
        if global_settings.get("denoising_strength") is not None:
            sd_params_kwargs["denoising_strength"] = global_settings["denoising_strength"]
        if global_settings.get("upscale_by") is not None:
            sd_params_kwargs["hr_scale"] = global_settings["upscale_by"]
            # upscale_byが設定されている場合はenable_hrをTrueに
            sd_params_kwargs["enable_hr"] = True

        # Refiner設定
        if global_settings.get("refiner_checkpoint"):
            sd_params_kwargs["refiner_checkpoint"] = global_settings["refiner_checkpoint"]
        if global_settings.get("refiner_switch_at") is not None:
            sd_params_kwargs["refiner_switch_at"] = global_settings["refiner_switch_at"]

    async def _process_gemini_generation(self, request_id: str):
        """Gemini APIで直接画像を生成するタスクを処理

        Args:
            request_id: GenerationRequest の ID
        """
        task_logger = get_logger_with_context(__name__, request_id=request_id)

        async with self.session_maker() as session:
            # リクエストを取得
            request = await self._get_request(session, request_id)
            if not request:
                raise DatabaseError(f"Request not found: {request_id}")

            task_logger.info(
                f"Processing Gemini direct image generation for request: {request_id}",
                extra={
                    "guild_id": request.guild_id,
                    "user_id": request.user_id,
                    "instruction": request.original_instruction[:100],
                },
            )

            try:
                # ステータスを PROCESSING に更新
                request.status = RequestStatus.PROCESSING
                await session.commit()

                # Gemini APIで直接画像を生成
                task_logger.info("Generating images with Gemini API...")
                from src.services.gemini_client import GeminiClient

                gemini_client = GeminiClient()

                # Geminiで画像生成（最高品質設定）
                gemini_result = await gemini_client.generate_images(
                    instruction=request.original_instruction,
                    reference_image=None,  # 初回生成では参照画像なし
                    previous_thought_signatures=None,  # 初回生成ではsignaturesなし
                )

                images = gemini_result.get("images", [])
                thought_signatures = gemini_result.get("thought_signatures", [])
                description = gemini_result.get("description", "")

                task_logger.info(
                    f"Gemini generated {len(images)} images",
                    extra={
                        "thought_signatures_count": len(thought_signatures),
                        "description_length": len(description),
                    },
                )

                if not images:
                    raise ApplicationError(
                        code=ErrorCode.LLM_GENERATION_ERROR,
                        message="Gemini APIから画像が生成されませんでした",
                    )

                # GenerationMetadata を作成
                metadata = GenerationMetadata(
                    request_id=request.id,
                    prompt=request.original_instruction,  # オリジナルの指示を保存
                    negative_prompt="",  # Geminiは自動処理
                    model_name="gemini-3-pro-image-preview",
                    lora_list=None,
                    steps=0,  # Geminiでは不要
                    cfg_scale=0.0,  # Geminiでは不要
                    sampler="Gemini",
                    scheduler=None,
                    seed=-1,
                    width=0,  # 画像サイズは生成後に取得
                    height=0,
                    raw_params={
                        "original_instruction": request.original_instruction,
                        "description": description,
                        "thought_signatures": thought_signatures,
                        "gemini_model": "gemini-3-pro-image-preview",
                    },
                )
                session.add(metadata)
                await session.commit()
                await session.refresh(metadata)

                task_logger.info(
                    "Metadata created for Gemini generation",
                    extra={"metadata_id": metadata.id},
                )

                # 画像を保存
                task_logger.info("Saving images to storage...")
                for i, img in enumerate(images):
                    # ファイル名生成
                    image_id = str(uuid.uuid4())
                    filename = f"{image_id}.png"
                    file_path = self.settings.image_storage_path / filename

                    # 画像を保存
                    img.save(file_path, format="PNG")
                    file_size = file_path.stat().st_size

                    # DB に保存
                    generated_image = GeneratedImage(
                        request_id=request.id,
                        metadata_id=metadata.id,
                        file_path=str(file_path),
                        file_size_bytes=file_size,
                    )
                    session.add(generated_image)

                    task_logger.info(
                        f"Saved image {i + 1}/{len(images)}: {filename}",
                        extra={"file_size": file_size},
                    )

                await session.commit()

                # リクエストを COMPLETED に更新
                request.status = RequestStatus.COMPLETED
                await session.commit()

                task_logger.info(
                    f"Gemini direct image generation completed for request: {request_id}"
                )

            except ApplicationError as e:
                # アプリケーションエラー
                request.status = RequestStatus.FAILED
                request.error_message = e.message
                await session.commit()
                raise

            except Exception as e:
                # 予期しないエラー
                request.status = RequestStatus.FAILED
                request.error_message = str(e)
                await session.commit()
                raise

    async def _process_xai_generation(self, request_id: str):
        """xAI APIで直接画像を生成するタスクを処理

        Args:
            request_id: GenerationRequest の ID
        """
        task_logger = get_logger_with_context(__name__, request_id=request_id)

        async with self.session_maker() as session:
            # リクエストを取得
            request = await self._get_request(session, request_id)
            if not request:
                raise DatabaseError(f"Request not found: {request_id}")

            task_logger.info(
                f"Processing xAI direct image generation for request: {request_id}",
                extra={
                    "guild_id": request.guild_id,
                    "user_id": request.user_id,
                    "instruction": request.original_instruction[:100],
                },
            )

            try:
                # ステータスを PROCESSING に更新
                request.status = RequestStatus.PROCESSING
                await session.commit()

                # xAI APIで直接画像を生成
                task_logger.info("Generating images with xAI API...")
                from src.services.xai_client import XAIClient

                xai_client = XAIClient()

                try:
                    # xAIで画像生成
                    xai_result = await xai_client.generate_images(
                        prompt=request.original_instruction,
                        n=1,  # xAI APIは1回のリクエストで1枚が推奨
                        response_format="b64_json",
                    )

                    images = xai_result.get("images", [])

                    task_logger.info(
                        f"xAI generated {len(images)} images",
                    )

                    if not images:
                        raise ApplicationError(
                            code=ErrorCode.LLM_GENERATION_ERROR,
                            message="xAI APIから画像が生成されませんでした",
                        )

                    # GenerationMetadata を作成
                    metadata = GenerationMetadata(
                        request_id=request.id,
                        prompt=request.original_instruction,  # オリジナルの指示を保存
                        negative_prompt="",  # xAIは自動処理
                        model_name="grok-2-image",
                        lora_list=None,
                        steps=0,  # xAIでは不要
                        cfg_scale=0.0,  # xAIでは不要
                        sampler="xAI",
                        scheduler=None,
                        seed=-1,
                        width=0,  # 画像サイズは生成後に取得
                        height=0,
                        raw_params={
                            "original_instruction": request.original_instruction,
                            "xai_model": "grok-2-image",
                        },
                    )
                    session.add(metadata)
                    await session.commit()
                    await session.refresh(metadata)

                    task_logger.info(
                        "Metadata created for xAI generation",
                        extra={"metadata_id": metadata.id},
                    )

                    # 画像を保存
                    task_logger.info("Saving images to storage...")
                    for i, img in enumerate(images):
                        # ファイル名生成
                        image_id = str(uuid.uuid4())
                        filename = f"{image_id}.png"
                        file_path = self.settings.image_storage_path / filename

                        # 画像を保存
                        img.save(file_path, format="PNG")
                        file_size = file_path.stat().st_size

                        # DB に保存
                        generated_image = GeneratedImage(
                            request_id=request.id,
                            metadata_id=metadata.id,
                            file_path=str(file_path),
                            file_size_bytes=file_size,
                        )
                        session.add(generated_image)

                        task_logger.info(
                            f"Saved image {i + 1}/{len(images)}: {filename}",
                            extra={"file_size": file_size},
                        )

                    await session.commit()

                    # リクエストを COMPLETED に更新
                    request.status = RequestStatus.COMPLETED
                    await session.commit()

                    task_logger.info(
                        f"xAI direct image generation completed for request: {request_id}"
                    )

                finally:
                    await xai_client.close()

            except ApplicationError as e:
                # アプリケーションエラー
                request.status = RequestStatus.FAILED
                request.error_message = e.message
                await session.commit()
                raise

            except Exception as e:
                # 予期しないエラー
                request.status = RequestStatus.FAILED
                request.error_message = str(e)
                await session.commit()
                raise
