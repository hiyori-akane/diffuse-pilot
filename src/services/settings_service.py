"""
グローバル設定サービス

GlobalSettings の CRUD 操作を提供
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import get_logger
from src.models.settings import GlobalSettings
from src.services.error_handler import ApplicationError, ErrorCode

logger = get_logger(__name__)


class SettingsService:
    """グローバル設定サービス"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_settings(
        self, guild_id: str, user_id: str | None = None
    ) -> GlobalSettings | None:
        """グローバル設定を取得

        Args:
            guild_id: Discord サーバー（guild）ID
            user_id: Discord ユーザー ID（省略時はサーバーデフォルト）

        Returns:
            グローバル設定（存在しない場合は None）
        """
        stmt = select(GlobalSettings).where(
            GlobalSettings.guild_id == guild_id, GlobalSettings.user_id == user_id
        )
        result = await self.session.execute(stmt)
        settings = result.scalar_one_or_none()

        logger.info(f"Get settings: guild={guild_id}, user={user_id}, found={settings is not None}")

        return settings

    async def create_settings(
        self,
        guild_id: str,
        user_id: str | None = None,
        default_model: str | None = None,
        default_lora_list: dict | None = None,
        default_prompt_suffix: str | None = None,
        default_sd_params: dict | None = None,
        seed: int | None = None,
        batch_size: int | None = None,
        batch_count: int | None = None,
        hires_upscaler: str | None = None,
        hires_steps: int | None = None,
        denoising_strength: float | None = None,
        upscale_by: float | None = None,
        refiner_checkpoint: str | None = None,
        refiner_switch_at: float | None = None,
    ) -> GlobalSettings:
        """グローバル設定を作成

        Args:
            guild_id: Discord サーバー（guild）ID
            user_id: Discord ユーザー ID（省略時はサーバーデフォルト）
            default_model: デフォルトモデル
            default_lora_list: デフォルト LoRA リスト
            default_prompt_suffix: デフォルトプロンプト suffix
            default_sd_params: デフォルト SD パラメータ
            seed: シード値
            batch_size: バッチサイズ
            batch_count: バッチカウント
            hires_upscaler: Hires. fix Upscaler
            hires_steps: Hires. fix ステップ数
            denoising_strength: Denoising strength
            upscale_by: Upscale by
            refiner_checkpoint: Refiner checkpoint
            refiner_switch_at: Refiner switch at

        Returns:
            作成されたグローバル設定

        Raises:
            ApplicationError: 既に設定が存在する場合
        """
        # 既存チェック
        existing = await self.get_settings(guild_id, user_id)
        if existing:
            raise ApplicationError(
                ErrorCode.VALIDATION_ERROR,
                "設定が既に存在します",
                details={"guild_id": guild_id, "user_id": user_id},
            )

        # バリデーション
        self._validate_settings(
            default_model,
            default_lora_list,
            default_sd_params,
            seed,
            batch_size,
            batch_count,
            hires_upscaler,
            hires_steps,
            denoising_strength,
            upscale_by,
            refiner_checkpoint,
            refiner_switch_at,
        )

        # 作成
        settings = GlobalSettings(
            guild_id=guild_id,
            user_id=user_id,
            default_model=default_model,
            default_lora_list=default_lora_list,
            default_prompt_suffix=default_prompt_suffix,
            default_sd_params=default_sd_params,
            seed=seed,
            batch_size=batch_size,
            batch_count=batch_count,
            hires_upscaler=hires_upscaler,
            hires_steps=hires_steps,
            denoising_strength=denoising_strength,
            upscale_by=upscale_by,
            refiner_checkpoint=refiner_checkpoint,
            refiner_switch_at=refiner_switch_at,
        )

        self.session.add(settings)
        await self.session.commit()
        await self.session.refresh(settings)

        logger.info(f"Created settings: {settings.id} for guild={guild_id}, user={user_id}")

        return settings

    async def update_settings(
        self,
        guild_id: str,
        user_id: str | None = None,
        default_model: str | None = None,
        default_lora_list: dict | None = None,
        default_prompt_suffix: str | None = None,
        default_sd_params: dict | None = None,
        seed: int | None = None,
        batch_size: int | None = None,
        batch_count: int | None = None,
        hires_upscaler: str | None = None,
        hires_steps: int | None = None,
        denoising_strength: float | None = None,
        upscale_by: float | None = None,
        refiner_checkpoint: str | None = None,
        refiner_switch_at: float | None = None,
    ) -> GlobalSettings:
        """グローバル設定を更新（存在しない場合は作成）

        Args:
            guild_id: Discord サーバー（guild）ID
            user_id: Discord ユーザー ID（省略時はサーバーデフォルト）
            default_model: デフォルトモデル
            default_lora_list: デフォルト LoRA リスト
            default_prompt_suffix: デフォルトプロンプト suffix
            default_sd_params: デフォルト SD パラメータ
            seed: シード値
            batch_size: バッチサイズ
            batch_count: バッチカウント
            hires_upscaler: Hires. fix Upscaler
            hires_steps: Hires. fix ステップ数
            denoising_strength: Denoising strength
            upscale_by: Upscale by
            refiner_checkpoint: Refiner checkpoint
            refiner_switch_at: Refiner switch at

        Returns:
            更新されたグローバル設定
        """
        # バリデーション
        self._validate_settings(
            default_model,
            default_lora_list,
            default_sd_params,
            seed,
            batch_size,
            batch_count,
            hires_upscaler,
            hires_steps,
            denoising_strength,
            upscale_by,
            refiner_checkpoint,
            refiner_switch_at,
        )

        # 既存設定を取得
        settings = await self.get_settings(guild_id, user_id)

        if settings:
            # 更新
            if default_model is not None:
                settings.default_model = default_model
            if default_lora_list is not None:
                settings.default_lora_list = default_lora_list
            if default_prompt_suffix is not None:
                settings.default_prompt_suffix = default_prompt_suffix
            if default_sd_params is not None:
                settings.default_sd_params = default_sd_params
            if seed is not None:
                settings.seed = seed
            if batch_size is not None:
                settings.batch_size = batch_size
            if batch_count is not None:
                settings.batch_count = batch_count
            if hires_upscaler is not None:
                settings.hires_upscaler = hires_upscaler
            if hires_steps is not None:
                settings.hires_steps = hires_steps
            if denoising_strength is not None:
                settings.denoising_strength = denoising_strength
            if upscale_by is not None:
                settings.upscale_by = upscale_by
            if refiner_checkpoint is not None:
                settings.refiner_checkpoint = refiner_checkpoint
            if refiner_switch_at is not None:
                settings.refiner_switch_at = refiner_switch_at

            await self.session.commit()
            await self.session.refresh(settings)

            logger.info(f"Updated settings: {settings.id} for guild={guild_id}, user={user_id}")
        else:
            # 作成
            settings = await self.create_settings(
                guild_id=guild_id,
                user_id=user_id,
                default_model=default_model,
                default_lora_list=default_lora_list,
                default_prompt_suffix=default_prompt_suffix,
                default_sd_params=default_sd_params,
                seed=seed,
                batch_size=batch_size,
                batch_count=batch_count,
                hires_upscaler=hires_upscaler,
                hires_steps=hires_steps,
                denoising_strength=denoising_strength,
                upscale_by=upscale_by,
                refiner_checkpoint=refiner_checkpoint,
                refiner_switch_at=refiner_switch_at,
            )

        return settings

    async def delete_settings(self, guild_id: str, user_id: str | None = None) -> bool:
        """グローバル設定を削除

        Args:
            guild_id: Discord サーバー（guild）ID
            user_id: Discord ユーザー ID（省略時はサーバーデフォルト）

        Returns:
            削除成功した場合 True、設定が存在しない場合 False
        """
        settings = await self.get_settings(guild_id, user_id)

        if not settings:
            logger.info(f"Settings not found for deletion: guild={guild_id}, user={user_id}")
            return False

        await self.session.delete(settings)
        await self.session.commit()

        logger.info(f"Deleted settings: {settings.id} for guild={guild_id}, user={user_id}")

        return True

    def _validate_settings(
        self,
        default_model: str | None,
        default_lora_list: dict | None,
        default_sd_params: dict | None,
        seed: int | None,
        batch_size: int | None,
        batch_count: int | None,
        hires_upscaler: str | None,
        hires_steps: int | None,
        denoising_strength: float | None,
        upscale_by: float | None,
        refiner_checkpoint: str | None,
        refiner_switch_at: float | None,
    ) -> None:
        """設定のバリデーション

        Args:
            default_model: デフォルトモデル
            default_lora_list: デフォルト LoRA リスト
            default_sd_params: デフォルト SD パラメータ
            seed: シード値
            batch_size: バッチサイズ
            batch_count: バッチカウント
            hires_upscaler: Hires. fix Upscaler
            hires_steps: Hires. fix ステップ数
            denoising_strength: Denoising strength
            upscale_by: Upscale by
            refiner_checkpoint: Refiner checkpoint
            refiner_switch_at: Refiner switch at

        Raises:
            ApplicationError: バリデーションエラー
        """
        # default_model のバリデーション
        if default_model is not None:
            if not isinstance(default_model, str) or len(default_model.strip()) == 0:
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "デフォルトモデル名が無効です",
                )

        # default_lora_list のバリデーション
        if default_lora_list is not None:
            if not isinstance(default_lora_list, (dict, list)):
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "デフォルト LoRA リストの形式が無効です",
                )

            # リスト形式の場合、各要素を検証
            items = (
                default_lora_list if isinstance(default_lora_list, list) else [default_lora_list]
            )
            for item in items:
                if isinstance(item, dict):
                    if "name" not in item:
                        raise ApplicationError(
                            ErrorCode.VALIDATION_ERROR,
                            "LoRA の name フィールドが必要です",
                        )
                    if "weight" in item and not isinstance(item["weight"], (int, float)):
                        raise ApplicationError(
                            ErrorCode.VALIDATION_ERROR,
                            "LoRA の weight は数値である必要があります",
                        )

        # default_sd_params のバリデーション
        if default_sd_params is not None:
            if not isinstance(default_sd_params, dict):
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "デフォルト SD パラメータは辞書形式である必要があります",
                )

            # steps のバリデーション
            if "steps" in default_sd_params:
                steps = default_sd_params["steps"]
                if not isinstance(steps, int) or steps < 1 or steps > 150:
                    raise ApplicationError(
                        ErrorCode.VALIDATION_ERROR,
                        "ステップ数は 1 から 150 の整数である必要があります",
                    )

            # cfg_scale のバリデーション
            if "cfg_scale" in default_sd_params:
                cfg = default_sd_params["cfg_scale"]
                if not isinstance(cfg, (int, float)) or cfg < 1.0 or cfg > 30.0:
                    raise ApplicationError(
                        ErrorCode.VALIDATION_ERROR,
                        "CFG スケールは 1.0 から 30.0 の数値である必要があります",
                    )

            # sampler / scheduler のバリデーション（文字列チェックのみ、存在確認は送信時）
            if "sampler" in default_sd_params:
                sampler = default_sd_params["sampler"]
                if not isinstance(sampler, str) or len(sampler.strip()) == 0:
                    raise ApplicationError(
                        ErrorCode.VALIDATION_ERROR,
                        "sampler は空でない文字列である必要があります",
                    )

            if "scheduler" in default_sd_params:
                scheduler = default_sd_params["scheduler"]
                if not isinstance(scheduler, str) or len(scheduler.strip()) == 0:
                    raise ApplicationError(
                        ErrorCode.VALIDATION_ERROR,
                        "scheduler は空でない文字列である必要があります",
                    )

            # width, height のバリデーション
            for dim in ["width", "height"]:
                if dim in default_sd_params:
                    val = default_sd_params[dim]
                    if not isinstance(val, int) or val < 64 or val > 2048:
                        raise ApplicationError(
                            f"Invalid {dim}: must be integer between 64 and 2048",
                            f"{dim} は 64 から 2048 の整数である必要があります",
                        )

        # seed のバリデーション
        if seed is not None:
            if not isinstance(seed, int) or seed < -1:
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "シード値は -1 以上の整数である必要があります",
                )

        # batch_size のバリデーション
        if batch_size is not None:
            if not isinstance(batch_size, int) or batch_size < 1 or batch_size > 8:
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "バッチサイズは 1 から 8 の整数である必要があります",
                )

        # batch_count のバリデーション
        if batch_count is not None:
            if not isinstance(batch_count, int) or batch_count < 1 or batch_count > 100:
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "バッチカウントは 1 から 100 の整数である必要があります",
                )

        # hires_upscaler のバリデーション
        if hires_upscaler is not None:
            if not isinstance(hires_upscaler, str) or len(hires_upscaler.strip()) == 0:
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "Hires. fix Upscaler 名が無効です",
                )

        # hires_steps のバリデーション
        if hires_steps is not None:
            if not isinstance(hires_steps, int) or hires_steps < 1 or hires_steps > 150:
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "Hires. fix ステップ数は 1 から 150 の整数である必要があります",
                )

        # denoising_strength のバリデーション
        if denoising_strength is not None:
            if (
                not isinstance(denoising_strength, (int, float))
                or denoising_strength < 0.0
                or denoising_strength > 1.0
            ):
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "Denoising strength は 0.0 から 1.0 の数値である必要があります",
                )

        # upscale_by のバリデーション
        if upscale_by is not None:
            if not isinstance(upscale_by, (int, float)) or upscale_by < 1.0 or upscale_by > 4.0:
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "Upscale by は 1.0 から 4.0 の数値である必要があります",
                )

        # refiner_checkpoint のバリデーション
        if refiner_checkpoint is not None:
            if not isinstance(refiner_checkpoint, str) or len(refiner_checkpoint.strip()) == 0:
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "Refiner checkpoint 名が無効です",
                )

        # refiner_switch_at のバリデーション
        if refiner_switch_at is not None:
            if (
                not isinstance(refiner_switch_at, (int, float))
                or refiner_switch_at < 0.0
                or refiner_switch_at > 1.0
            ):
                raise ApplicationError(
                    ErrorCode.VALIDATION_ERROR,
                    "Refiner switch at は 0.0 から 1.0 の数値である必要があります",
                )
