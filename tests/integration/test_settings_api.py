"""Integration tests for settings API"""
import pytest
from fastapi.testclient import TestClient
from src.main import create_app


@pytest.fixture
def client():
    """Test client for FastAPI app"""
    app = create_app()
    return TestClient(app)


def test_get_settings_not_found(client):
    """設定が存在しない場合の GET テスト"""
    response = client.get("/api/v1/settings", params={"guild_id": "test_guild_123"})
    assert response.status_code == 404


def test_create_and_get_settings(client):
    """設定の作成と取得テスト"""
    # 設定を作成
    create_data = {
        "guild_id": "test_guild_456",
        "user_id": "test_user_789",
        "default_model": "sdxl",
        "default_prompt_suffix": "masterpiece, best quality",
        "default_sd_params": {
            "steps": 30,
            "cfg_scale": 7.5,
        },
    }
    
    create_response = client.put("/api/v1/settings", json=create_data)
    assert create_response.status_code == 200
    
    created = create_response.json()
    assert created["guild_id"] == "test_guild_456"
    assert created["user_id"] == "test_user_789"
    assert created["default_model"] == "sdxl"
    assert created["default_prompt_suffix"] == "masterpiece, best quality"
    assert created["default_sd_params"]["steps"] == 30
    
    # 設定を取得
    get_response = client.get(
        "/api/v1/settings",
        params={"guild_id": "test_guild_456", "user_id": "test_user_789"}
    )
    assert get_response.status_code == 200
    
    retrieved = get_response.json()
    assert retrieved["settings_id"] == created["settings_id"]
    assert retrieved["default_model"] == "sdxl"


def test_update_settings(client):
    """設定の更新テスト"""
    # 最初の設定を作成
    create_data = {
        "guild_id": "test_guild_update",
        "user_id": None,
        "default_model": "sd15",
    }
    
    create_response = client.put("/api/v1/settings", json=create_data)
    assert create_response.status_code == 200
    settings_id = create_response.json()["settings_id"]
    
    # 設定を更新
    update_data = {
        "guild_id": "test_guild_update",
        "user_id": None,
        "default_model": "sdxl",
        "default_prompt_suffix": "updated suffix",
    }
    
    update_response = client.put("/api/v1/settings", json=update_data)
    assert update_response.status_code == 200
    
    updated = update_response.json()
    assert updated["settings_id"] == settings_id  # 同じ ID
    assert updated["default_model"] == "sdxl"  # 更新された
    assert updated["default_prompt_suffix"] == "updated suffix"


def test_validation_invalid_steps(client):
    """無効なステップ数のバリデーションテスト"""
    create_data = {
        "guild_id": "test_guild_validation",
        "default_sd_params": {
            "steps": 200,  # 150 を超える
        },
    }
    
    response = client.put("/api/v1/settings", json=create_data)
    assert response.status_code == 400
    assert "ステップ数" in response.json()["detail"]


def test_validation_invalid_model(client):
    """無効なモデル名のバリデーションテスト"""
    create_data = {
        "guild_id": "test_guild_validation2",
        "default_model": "",  # 空文字列
    }

    response = client.put("/api/v1/settings", json=create_data)
    assert response.status_code == 400
    assert "モデル名" in response.json()["detail"]


def test_new_settings_fields(client):
    """新しい設定フィールドのテスト"""
    create_data = {
        "guild_id": "test_guild_new_fields",
        "user_id": "test_user_new",
        "seed": 42,
        "batch_size": 2,
        "batch_count": 4,
        "hires_upscaler": "R-ESRGAN 4x+ Anime6B",
        "hires_steps": 50,
        "denoising_strength": 0.7,
        "upscale_by": 2.0,
        "refiner_checkpoint": "sd_xl_refiner_1.0",
        "refiner_switch_at": 0.8,
    }

    response = client.put("/api/v1/settings", json=create_data)
    assert response.status_code == 200

    created = response.json()
    assert created["seed"] == 42
    assert created["batch_size"] == 2
    assert created["batch_count"] == 4
    assert created["hires_upscaler"] == "R-ESRGAN 4x+ Anime6B"
    assert created["hires_steps"] == 50
    assert created["denoising_strength"] == 0.7
    assert created["upscale_by"] == 2.0
    assert created["refiner_checkpoint"] == "sd_xl_refiner_1.0"
    assert created["refiner_switch_at"] == 0.8


def test_validation_invalid_seed(client):
    """無効なシード値のバリデーションテスト"""
    create_data = {
        "guild_id": "test_guild_seed_validation",
        "seed": -2,  # -1 未満は無効
    }

    response = client.put("/api/v1/settings", json=create_data)
    assert response.status_code == 400
    assert "シード値" in response.json()["detail"]


def test_validation_invalid_batch_size(client):
    """無効なバッチサイズのバリデーションテスト"""
    create_data = {
        "guild_id": "test_guild_batch_validation",
        "batch_size": 10,  # 8 を超える
    }

    response = client.put("/api/v1/settings", json=create_data)
    assert response.status_code == 400
    assert "バッチサイズ" in response.json()["detail"]


def test_validation_invalid_denoising_strength(client):
    """無効な Denoising strength のバリデーションテスト"""
    create_data = {
        "guild_id": "test_guild_denoising_validation",
        "denoising_strength": 1.5,  # 1.0 を超える
    }

    response = client.put("/api/v1/settings", json=create_data)
    assert response.status_code == 400
    assert "Denoising strength" in response.json()["detail"]
