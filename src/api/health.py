"""
ヘルスチェックエンドポイント
"""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    """ヘルスチェックレスポンス"""

    status: str
    timestamp: datetime
    version: str = "0.1.0"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """ヘルスチェック

    Returns:
        HealthResponse: ヘルスチェック結果
    """
    return HealthResponse(status="healthy", timestamp=datetime.utcnow())


@router.get("/")
async def root() -> dict[str, str]:
    """ルートエンドポイント

    Returns:
        dict: API情報
    """
    return {"name": "Diffuse Pilot API", "version": "0.1.0"}
