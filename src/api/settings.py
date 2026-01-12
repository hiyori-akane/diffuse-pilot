"""
グローバル設定 API エンドポイント
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.logging import get_logger
from src.database.connection import get_session_maker
from src.services.error_handler import ApplicationError
from src.services.settings_service import SettingsService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1", tags=["Settings"])


class GlobalSettingsInput(BaseModel):
    """グローバル設定入力スキーマ"""

    guild_id: str = Field(description="Discord サーバー（guild）ID")
    user_id: str | None = Field(
        default=None, description="Discord ユーザー ID（省略時はサーバーデフォルト）"
    )
    default_model: str | None = Field(default=None, description="デフォルトモデル")
    default_lora_list: Any | None = Field(default=None, description="デフォルト LoRA リスト")
    default_prompt_suffix: str | None = Field(
        default=None, description="デフォルトプロンプト suffix"
    )
    default_sd_params: dict[str, Any] | None = Field(
        default=None, description="デフォルト SD パラメータ"
    )

    # 一般設定
    seed: int | None = Field(default=None, description="シード値 (-1 でランダム)")
    batch_size: int | None = Field(default=None, description="バッチサイズ")
    batch_count: int | None = Field(default=None, description="バッチカウント")

    # Hires. fix 設定
    hires_upscaler: str | None = Field(default=None, description="Hires. fix Upscaler")
    hires_steps: int | None = Field(default=None, description="Hires. fix ステップ数")
    denoising_strength: float | None = Field(default=None, description="Denoising strength")
    upscale_by: float | None = Field(default=None, description="Upscale by")

    # Refiner 設定
    refiner_checkpoint: str | None = Field(default=None, description="Refiner checkpoint")
    refiner_switch_at: float | None = Field(default=None, description="Refiner switch at")


class GlobalSettingsResponse(BaseModel):
    """グローバル設定レスポンススキーマ"""

    settings_id: str = Field(description="設定 ID")
    guild_id: str = Field(description="Discord サーバー（guild）ID")
    user_id: str | None = Field(description="Discord ユーザー ID")
    default_model: str | None = Field(description="デフォルトモデル")
    default_lora_list: Any | None = Field(description="デフォルト LoRA リスト")
    default_prompt_suffix: str | None = Field(description="デフォルトプロンプト suffix")
    default_sd_params: dict[str, Any] | None = Field(description="デフォルト SD パラメータ")

    # 一般設定
    seed: int | None = Field(description="シード値")
    batch_size: int | None = Field(description="バッチサイズ")
    batch_count: int | None = Field(description="バッチカウント")

    # Hires. fix 設定
    hires_upscaler: str | None = Field(description="Hires. fix Upscaler")
    hires_steps: int | None = Field(description="Hires. fix ステップ数")
    denoising_strength: float | None = Field(description="Denoising strength")
    upscale_by: float | None = Field(description="Upscale by")

    # Refiner 設定
    refiner_checkpoint: str | None = Field(description="Refiner checkpoint")
    refiner_switch_at: float | None = Field(description="Refiner switch at")

    created_at: str = Field(description="作成日時")
    updated_at: str = Field(description="更新日時")


async def get_db_session() -> AsyncSession:
    """データベースセッションを取得"""
    session_maker = get_session_maker()
    async with session_maker() as session:
        yield session


@router.get("/settings", response_model=GlobalSettingsResponse)
async def get_global_settings(
    guild_id: str = Query(..., description="Discord サーバー（guild）ID"),
    user_id: str | None = Query(
        None, description="Discord ユーザー ID（省略時はサーバーデフォルト）"
    ),
    session: AsyncSession = Depends(get_db_session),
):
    """グローバル設定を取得

    Args:
        guild_id: Discord サーバー（guild）ID
        user_id: Discord ユーザー ID（省略時はサーバーデフォルト）
        session: データベースセッション

    Returns:
        グローバル設定

    Raises:
        HTTPException: 設定が見つからない場合
    """
    try:
        logger.info(f"GET /settings: guild_id={guild_id}, user_id={user_id}")

        service = SettingsService(session)
        settings = await service.get_settings(guild_id, user_id)

        if not settings:
            raise HTTPException(status_code=404, detail="Settings not found")

        return GlobalSettingsResponse(
            settings_id=settings.id,
            guild_id=settings.guild_id,
            user_id=settings.user_id,
            default_model=settings.default_model,
            default_lora_list=settings.default_lora_list,
            default_prompt_suffix=settings.default_prompt_suffix,
            default_sd_params=settings.default_sd_params,
            seed=settings.seed,
            batch_size=settings.batch_size,
            batch_count=settings.batch_count,
            hires_upscaler=settings.hires_upscaler,
            hires_steps=settings.hires_steps,
            denoising_strength=settings.denoising_strength,
            upscale_by=settings.upscale_by,
            refiner_checkpoint=settings.refiner_checkpoint,
            refiner_switch_at=settings.refiner_switch_at,
            created_at=settings.created_at.isoformat(),
            updated_at=settings.updated_at.isoformat(),
        )

    except HTTPException:
        raise
    except ApplicationError as e:
        logger.error(f"Application error: {e.message}")
        raise HTTPException(status_code=400, detail=e.message) from e
    except Exception as e:
        logger.exception(f"Error getting settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.put("/settings", response_model=GlobalSettingsResponse)
async def update_global_settings(
    input_data: GlobalSettingsInput,
    session: AsyncSession = Depends(get_db_session),
):
    """グローバル設定を更新（存在しない場合は作成）

    Args:
        input_data: 設定入力データ
        session: データベースセッション

    Returns:
        更新されたグローバル設定

    Raises:
        HTTPException: バリデーションエラーまたは内部エラー
    """
    try:
        logger.info(f"PUT /settings: guild_id={input_data.guild_id}, user_id={input_data.user_id}")

        service = SettingsService(session)
        settings = await service.update_settings(
            guild_id=input_data.guild_id,
            user_id=input_data.user_id,
            default_model=input_data.default_model,
            default_lora_list=input_data.default_lora_list,
            default_prompt_suffix=input_data.default_prompt_suffix,
            default_sd_params=input_data.default_sd_params,
            seed=input_data.seed,
            batch_size=input_data.batch_size,
            batch_count=input_data.batch_count,
            hires_upscaler=input_data.hires_upscaler,
            hires_steps=input_data.hires_steps,
            denoising_strength=input_data.denoising_strength,
            upscale_by=input_data.upscale_by,
            refiner_checkpoint=input_data.refiner_checkpoint,
            refiner_switch_at=input_data.refiner_switch_at,
        )

        return GlobalSettingsResponse(
            settings_id=settings.id,
            guild_id=settings.guild_id,
            user_id=settings.user_id,
            default_model=settings.default_model,
            default_lora_list=settings.default_lora_list,
            default_prompt_suffix=settings.default_prompt_suffix,
            default_sd_params=settings.default_sd_params,
            seed=settings.seed,
            batch_size=settings.batch_size,
            batch_count=settings.batch_count,
            hires_upscaler=settings.hires_upscaler,
            hires_steps=settings.hires_steps,
            denoising_strength=settings.denoising_strength,
            upscale_by=settings.upscale_by,
            refiner_checkpoint=settings.refiner_checkpoint,
            refiner_switch_at=settings.refiner_switch_at,
            created_at=settings.created_at.isoformat(),
            updated_at=settings.updated_at.isoformat(),
        )

    except ApplicationError as e:
        logger.error(f"Application error: {e.message}")
        raise HTTPException(status_code=400, detail=e.message) from e
    except Exception as e:
        logger.exception(f"Error updating settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
