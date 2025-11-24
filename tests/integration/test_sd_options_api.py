"""Integration tests for SD options API endpoints"""
import pytest
from httpx import AsyncClient

from src.main import app


@pytest.mark.asyncio
async def test_get_models_endpoint():
    """モデル一覧取得エンドポイントのテスト"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/sd/models")

    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert isinstance(data["models"], list)


@pytest.mark.asyncio
async def test_get_loras_endpoint():
    """LoRA一覧取得エンドポイントのテスト"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/sd/loras")

    assert response.status_code == 200
    data = response.json()
    assert "loras" in data
    assert isinstance(data["loras"], list)


@pytest.mark.asyncio
async def test_get_samplers_endpoint():
    """サンプラー一覧取得エンドポイントのテスト"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/sd/samplers")

    assert response.status_code == 200
    data = response.json()
    assert "samplers" in data
    assert isinstance(data["samplers"], list)


@pytest.mark.asyncio
async def test_get_schedulers_endpoint():
    """スケジューラ一覧取得エンドポイントのテスト"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/sd/schedulers")

    assert response.status_code == 200
    data = response.json()
    assert "schedulers" in data
    assert isinstance(data["schedulers"], list)


@pytest.mark.asyncio
async def test_get_upscalers_endpoint():
    """アップスケーラー一覧取得エンドポイントのテスト"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/api/v1/sd/upscalers")

    assert response.status_code == 200
    data = response.json()
    assert "upscalers" in data
    assert isinstance(data["upscalers"], list)
