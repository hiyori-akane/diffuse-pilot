"""Unit tests for settings service"""
import pytest
from src.models.settings import GlobalSettings
from src.services.error_handler import ApplicationError
from src.services.settings_service import SettingsService


@pytest.mark.asyncio
async def test_get_settings_not_found(test_db):
    """設定が存在しない場合のテスト"""
    service = SettingsService(test_db)
    settings = await service.get_settings("guild123", "user456")
    assert settings is None


@pytest.mark.asyncio
async def test_create_settings(test_db):
    """設定の作成テスト"""
    service = SettingsService(test_db)
    
    settings = await service.create_settings(
        guild_id="guild123",
        user_id="user456",
        default_model="sdxl",
        default_prompt_suffix="masterpiece, best quality",
        default_sd_params={"steps": 30, "cfg_scale": 7.5},
    )
    
    assert settings.id is not None
    assert settings.guild_id == "guild123"
    assert settings.user_id == "user456"
    assert settings.default_model == "sdxl"
    assert settings.default_prompt_suffix == "masterpiece, best quality"
    assert settings.default_sd_params == {"steps": 30, "cfg_scale": 7.5}


@pytest.mark.asyncio
async def test_create_settings_duplicate(test_db):
    """重複する設定の作成エラーテスト"""
    service = SettingsService(test_db)
    
    # 最初の作成は成功
    await service.create_settings(
        guild_id="guild123",
        user_id="user456",
        default_model="sdxl",
    )
    
    # 2回目の作成はエラー
    with pytest.raises(ApplicationError):
        await service.create_settings(
            guild_id="guild123",
            user_id="user456",
            default_model="sd15",
        )


@pytest.mark.asyncio
async def test_update_settings_create_new(test_db):
    """存在しない設定の更新（新規作成）テスト"""
    service = SettingsService(test_db)
    
    settings = await service.update_settings(
        guild_id="guild123",
        user_id="user456",
        default_model="sdxl",
    )
    
    assert settings.id is not None
    assert settings.default_model == "sdxl"


@pytest.mark.asyncio
async def test_update_settings_existing(test_db):
    """既存設定の更新テスト"""
    service = SettingsService(test_db)
    
    # 設定を作成
    original = await service.create_settings(
        guild_id="guild123",
        user_id="user456",
        default_model="sdxl",
        default_prompt_suffix="original",
    )
    
    # 設定を更新
    updated = await service.update_settings(
        guild_id="guild123",
        user_id="user456",
        default_model="sd15",
        default_sd_params={"steps": 25},
    )
    
    assert updated.id == original.id
    assert updated.default_model == "sd15"
    assert updated.default_sd_params == {"steps": 25}
    # prompt_suffix は更新されていないので、元の値が保持される
    assert updated.default_prompt_suffix == "original"


@pytest.mark.asyncio
async def test_delete_settings(test_db):
    """設定の削除テスト"""
    service = SettingsService(test_db)
    
    # 設定を作成
    await service.create_settings(
        guild_id="guild123",
        user_id="user456",
        default_model="sdxl",
    )
    
    # 削除成功
    deleted = await service.delete_settings("guild123", "user456")
    assert deleted is True
    
    # 設定が削除されたことを確認
    settings = await service.get_settings("guild123", "user456")
    assert settings is None


@pytest.mark.asyncio
async def test_delete_settings_not_found(test_db):
    """存在しない設定の削除テスト"""
    service = SettingsService(test_db)
    
    # 存在しない設定の削除
    deleted = await service.delete_settings("guild123", "user456")
    assert deleted is False


@pytest.mark.asyncio
async def test_validate_invalid_model(test_db):
    """無効なモデル名のバリデーションテスト"""
    service = SettingsService(test_db)
    
    with pytest.raises(ApplicationError, match="デフォルトモデル名が無効です"):
        await service.create_settings(
            guild_id="guild123",
            default_model="",  # 空文字列は無効
        )


@pytest.mark.asyncio
async def test_validate_invalid_lora_list(test_db):
    """無効な LoRA リストのバリデーションテスト"""
    service = SettingsService(test_db)
    
    # リスト形式で name がない場合
    with pytest.raises(ApplicationError, match="name フィールドが必要です"):
        await service.create_settings(
            guild_id="guild123",
            default_lora_list=[{"weight": 1.0}],  # name がない
        )


@pytest.mark.asyncio
async def test_validate_invalid_steps(test_db):
    """無効なステップ数のバリデーションテスト"""
    service = SettingsService(test_db)
    
    with pytest.raises(ApplicationError, match="ステップ数は"):
        await service.create_settings(
            guild_id="guild123",
            default_sd_params={"steps": 200},  # 150 を超える
        )


@pytest.mark.asyncio
async def test_validate_invalid_cfg_scale(test_db):
    """無効な CFG スケールのバリデーションテスト"""
    service = SettingsService(test_db)
    
    with pytest.raises(ApplicationError, match="CFG スケールは"):
        await service.create_settings(
            guild_id="guild123",
            default_sd_params={"cfg_scale": 0.5},  # 1.0 未満
        )


@pytest.mark.asyncio
async def test_validate_invalid_dimensions(test_db):
    """無効な画像サイズのバリデーションテスト"""
    service = SettingsService(test_db)
    
    with pytest.raises(ApplicationError, match="width は"):
        await service.create_settings(
            guild_id="guild123",
            default_sd_params={"width": 32},  # 64 未満
        )


@pytest.mark.asyncio
async def test_server_default_settings(test_db):
    """サーバーデフォルト設定（user_id が None）のテスト"""
    service = SettingsService(test_db)
    
    # サーバーデフォルト設定を作成
    settings = await service.create_settings(
        guild_id="guild123",
        user_id=None,  # サーバーデフォルト
        default_model="sdxl",
    )
    
    assert settings.guild_id == "guild123"
    assert settings.user_id is None
    assert settings.default_model == "sdxl"
    
    # 取得できることを確認
    retrieved = await service.get_settings("guild123", None)
    assert retrieved is not None
    assert retrieved.id == settings.id
