"""
Stable Diffusion オプション取得 API エンドポイント
"""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.config.logging import get_logger
from src.services.error_handler import StableDiffusionAPIError
from src.services.sd_client import StableDiffusionClient

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/sd", tags=["SD Options"])


class ModelsResponse(BaseModel):
    """モデル一覧レスポンス"""

    models: list[str] = Field(description="利用可能なモデル名のリスト")


class LoRAsResponse(BaseModel):
    """LoRA一覧レスポンス"""

    loras: list[dict[str, Any]] = Field(description="利用可能なLoRA情報のリスト")


class SamplersResponse(BaseModel):
    """サンプラー一覧レスポンス"""

    samplers: list[str] = Field(description="利用可能なサンプラー名のリスト")


class SchedulersResponse(BaseModel):
    """スケジューラ一覧レスポンス"""

    schedulers: list[str] = Field(description="利用可能なスケジューラ名のリスト")


class UpscalersResponse(BaseModel):
    """アップスケーラー一覧レスポンス"""

    upscalers: list[str] = Field(description="利用可能なアップスケーラー名のリスト")


@router.get("/models", response_model=ModelsResponse)
async def get_models():
    """利用可能なモデルの一覧を取得

    Returns:
        利用可能なモデル名のリスト

    Raises:
        HTTPException: API エラー
    """
    try:
        logger.info("GET /sd/models")
        client = StableDiffusionClient()
        try:
            models = await client.get_models()
            return ModelsResponse(models=models)
        finally:
            await client.close()

    except StableDiffusionAPIError as e:
        logger.error(f"SD API error: {e.message}")
        raise HTTPException(status_code=500, detail=e.user_message) from e
    except Exception as e:
        logger.exception(f"Error getting models: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/loras", response_model=LoRAsResponse)
async def get_loras():
    """利用可能なLoRAの一覧を取得

    Returns:
        利用可能なLoRA情報のリスト

    Raises:
        HTTPException: API エラー
    """
    try:
        logger.info("GET /sd/loras")
        client = StableDiffusionClient()
        try:
            loras = await client.get_loras()
            return LoRAsResponse(loras=loras)
        finally:
            await client.close()

    except StableDiffusionAPIError as e:
        logger.error(f"SD API error: {e.message}")
        raise HTTPException(status_code=500, detail=e.user_message) from e
    except Exception as e:
        logger.exception(f"Error getting LoRAs: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/samplers", response_model=SamplersResponse)
async def get_samplers():
    """利用可能なサンプラーの一覧を取得

    Returns:
        利用可能なサンプラー名のリスト

    Raises:
        HTTPException: API エラー
    """
    try:
        logger.info("GET /sd/samplers")
        client = StableDiffusionClient()
        try:
            samplers = await client.get_samplers()
            return SamplersResponse(samplers=samplers)
        finally:
            await client.close()

    except StableDiffusionAPIError as e:
        logger.error(f"SD API error: {e.message}")
        raise HTTPException(status_code=500, detail=e.user_message) from e
    except Exception as e:
        logger.exception(f"Error getting samplers: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/schedulers", response_model=SchedulersResponse)
async def get_schedulers():
    """利用可能なスケジューラの一覧を取得

    Returns:
        利用可能なスケジューラ名のリスト

    Raises:
        HTTPException: API エラー
    """
    try:
        logger.info("GET /sd/schedulers")
        client = StableDiffusionClient()
        try:
            schedulers = await client.get_schedulers()
            return SchedulersResponse(schedulers=schedulers)
        finally:
            await client.close()

    except StableDiffusionAPIError as e:
        logger.error(f"SD API error: {e.message}")
        raise HTTPException(status_code=500, detail=e.user_message) from e
    except Exception as e:
        logger.exception(f"Error getting schedulers: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/upscalers", response_model=UpscalersResponse)
async def get_upscalers():
    """利用可能なアップスケーラーの一覧を取得

    Returns:
        利用可能なアップスケーラー名のリスト

    Raises:
        HTTPException: API エラー
    """
    try:
        logger.info("GET /sd/upscalers")
        client = StableDiffusionClient()
        try:
            upscalers = await client.get_upscalers()
            return UpscalersResponse(upscalers=upscalers)
        finally:
            await client.close()

    except StableDiffusionAPIError as e:
        logger.error(f"SD API error: {e.message}")
        raise HTTPException(status_code=500, detail=e.user_message) from e
    except Exception as e:
        logger.exception(f"Error getting upscalers: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
