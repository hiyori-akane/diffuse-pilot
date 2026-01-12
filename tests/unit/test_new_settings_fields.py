"""Unit tests for new settings fields"""

import pytest
from src.models.settings import GlobalSettings
from src.services.error_handler import ApplicationError
from src.services.settings_service import SettingsService


@pytest.mark.asyncio
async def test_create_settings_with_general_params(test_db):
    """一般設定パラメータの作成テスト"""
    service = SettingsService(test_db)

    settings = await service.create_settings(
        guild_id="guild123",
        user_id="user456",
        seed=42,
        batch_size=2,
        batch_count=4,
    )

    assert settings.seed == 42
    assert settings.batch_size == 2
    assert settings.batch_count == 4


@pytest.mark.asyncio
async def test_create_settings_with_hires_fix(test_db):
    """Hires. fix 設定の作成テスト"""
    service = SettingsService(test_db)

    settings = await service.create_settings(
        guild_id="guild123",
        user_id="user456",
        hires_upscaler="R-ESRGAN 4x+ Anime6B",
        hires_steps=50,
        denoising_strength=0.7,
        upscale_by=2.0,
    )

    assert settings.hires_upscaler == "R-ESRGAN 4x+ Anime6B"
    assert settings.hires_steps == 50
    assert settings.denoising_strength == 0.7
    assert settings.upscale_by == 2.0


@pytest.mark.asyncio
async def test_create_settings_with_refiner(test_db):
    """Refiner 設定の作成テスト"""
    service = SettingsService(test_db)

    settings = await service.create_settings(
        guild_id="guild123",
        user_id="user456",
        refiner_checkpoint="sd_xl_refiner_1.0",
        refiner_switch_at=0.8,
    )

    assert settings.refiner_checkpoint == "sd_xl_refiner_1.0"
    assert settings.refiner_switch_at == 0.8


@pytest.mark.asyncio
async def test_update_settings_with_new_fields(test_db):
    """新しいフィールドの更新テスト"""
    service = SettingsService(test_db)

    # 初期設定を作成
    original = await service.create_settings(
        guild_id="guild123",
        user_id="user456",
        seed=-1,
    )

    # 新しいフィールドを更新
    updated = await service.update_settings(
        guild_id="guild123",
        user_id="user456",
        seed=12345,
        batch_size=4,
        hires_upscaler="R-ESRGAN 4x+",
        hires_steps=30,
    )

    assert updated.id == original.id
    assert updated.seed == 12345
    assert updated.batch_size == 4
    assert updated.hires_upscaler == "R-ESRGAN 4x+"
    assert updated.hires_steps == 30


@pytest.mark.asyncio
async def test_validate_invalid_seed(test_db):
    """無効なシード値のバリデーションテスト"""
    service = SettingsService(test_db)

    with pytest.raises(ApplicationError, match="シード値は"):
        await service.create_settings(
            guild_id="guild123",
            seed=-2,  # -1 未満は無効
        )


@pytest.mark.asyncio
async def test_validate_invalid_batch_size(test_db):
    """無効なバッチサイズのバリデーションテスト"""
    service = SettingsService(test_db)

    with pytest.raises(ApplicationError, match="バッチサイズは"):
        await service.create_settings(
            guild_id="guild123",
            batch_size=0,  # 1 未満は無効
        )

    with pytest.raises(ApplicationError, match="バッチサイズは"):
        await service.create_settings(
            guild_id="guild123",
            batch_size=10,  # 8 を超えるのは無効
        )


@pytest.mark.asyncio
async def test_validate_invalid_batch_count(test_db):
    """無効なバッチカウントのバリデーションテスト"""
    service = SettingsService(test_db)

    with pytest.raises(ApplicationError, match="バッチカウントは"):
        await service.create_settings(
            guild_id="guild123",
            batch_count=0,  # 1 未満は無効
        )

    with pytest.raises(ApplicationError, match="バッチカウントは"):
        await service.create_settings(
            guild_id="guild123",
            batch_count=101,  # 100 を超えるのは無効
        )


@pytest.mark.asyncio
async def test_validate_invalid_hires_steps(test_db):
    """無効な Hires. fix ステップ数のバリデーションテスト"""
    service = SettingsService(test_db)

    with pytest.raises(ApplicationError, match="Hires. fix ステップ数は"):
        await service.create_settings(
            guild_id="guild123",
            hires_steps=0,  # 1 未満は無効
        )

    with pytest.raises(ApplicationError, match="Hires. fix ステップ数は"):
        await service.create_settings(
            guild_id="guild123",
            hires_steps=200,  # 150 を超えるのは無効
        )


@pytest.mark.asyncio
async def test_validate_invalid_denoising_strength(test_db):
    """無効な Denoising strength のバリデーションテスト"""
    service = SettingsService(test_db)

    with pytest.raises(ApplicationError, match="Denoising strength は"):
        await service.create_settings(
            guild_id="guild123",
            denoising_strength=-0.1,  # 0.0 未満は無効
        )

    with pytest.raises(ApplicationError, match="Denoising strength は"):
        await service.create_settings(
            guild_id="guild123",
            denoising_strength=1.1,  # 1.0 を超えるのは無効
        )


@pytest.mark.asyncio
async def test_validate_invalid_upscale_by(test_db):
    """無効な Upscale by のバリデーションテスト"""
    service = SettingsService(test_db)

    with pytest.raises(ApplicationError, match="Upscale by は"):
        await service.create_settings(
            guild_id="guild123",
            upscale_by=0.5,  # 1.0 未満は無効
        )

    with pytest.raises(ApplicationError, match="Upscale by は"):
        await service.create_settings(
            guild_id="guild123",
            upscale_by=5.0,  # 4.0 を超えるのは無効
        )


@pytest.mark.asyncio
async def test_validate_invalid_refiner_switch_at(test_db):
    """無効な Refiner switch at のバリデーションテスト"""
    service = SettingsService(test_db)

    with pytest.raises(ApplicationError, match="Refiner switch at は"):
        await service.create_settings(
            guild_id="guild123",
            refiner_switch_at=-0.1,  # 0.0 未満は無効
        )

    with pytest.raises(ApplicationError, match="Refiner switch at は"):
        await service.create_settings(
            guild_id="guild123",
            refiner_switch_at=1.1,  # 1.0 を超えるのは無効
        )


@pytest.mark.asyncio
async def test_validate_invalid_hires_upscaler(test_db):
    """無効な Hires. fix Upscaler のバリデーションテスト"""
    service = SettingsService(test_db)

    with pytest.raises(ApplicationError, match="Hires. fix Upscaler 名が無効です"):
        await service.create_settings(
            guild_id="guild123",
            hires_upscaler="",  # 空文字列は無効
        )


@pytest.mark.asyncio
async def test_validate_invalid_refiner_checkpoint(test_db):
    """無効な Refiner checkpoint のバリデーションテスト"""
    service = SettingsService(test_db)

    with pytest.raises(ApplicationError, match="Refiner checkpoint 名が無効です"):
        await service.create_settings(
            guild_id="guild123",
            refiner_checkpoint="",  # 空文字列は無効
        )


@pytest.mark.asyncio
async def test_all_new_fields_together(test_db):
    """すべての新しいフィールドを一度に設定するテスト"""
    service = SettingsService(test_db)

    settings = await service.create_settings(
        guild_id="guild123",
        user_id="user456",
        default_model="sdxl",
        seed=42,
        batch_size=2,
        batch_count=4,
        hires_upscaler="R-ESRGAN 4x+ Anime6B",
        hires_steps=50,
        denoising_strength=0.7,
        upscale_by=2.0,
        refiner_checkpoint="sd_xl_refiner_1.0",
        refiner_switch_at=0.8,
    )

    # すべてのフィールドが正しく設定されていることを確認
    assert settings.default_model == "sdxl"
    assert settings.seed == 42
    assert settings.batch_size == 2
    assert settings.batch_count == 4
    assert settings.hires_upscaler == "R-ESRGAN 4x+ Anime6B"
    assert settings.hires_steps == 50
    assert settings.denoising_strength == 0.7
    assert settings.upscale_by == 2.0
    assert settings.refiner_checkpoint == "sd_xl_refiner_1.0"
    assert settings.refiner_switch_at == 0.8
