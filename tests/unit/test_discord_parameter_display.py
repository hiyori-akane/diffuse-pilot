"""Unit tests for Discord parameter display functionality"""
import pytest

from src.models.generation import GenerationMetadata, GenerationRequest


@pytest.mark.asyncio
async def test_metadata_with_all_parameters(test_db):
    """メタデータに全パラメータが含まれることをテスト"""
    # GenerationRequest を作成
    request = GenerationRequest(
        guild_id="123456789",
        user_id="987654321",
        thread_id="111222333",
        original_instruction="Test instruction",
    )
    test_db.add(request)
    await test_db.commit()
    await test_db.refresh(request)

    # GenerationMetadata を作成（全パラメータを含む）
    raw_params = {
        "prompt": "test prompt",
        "negative_prompt": "test negative",
        "steps": 20,
        "cfg_scale": 7.0,
        "sampler": "Euler a",
        "scheduler": "Automatic",
        "seed": 12345,
        "width": 512,
        "height": 512,
        "batch_size": 2,
        "batch_count": 1,
        "enable_hr": True,
        "hr_scale": 2.0,
        "hr_upscaler": "Latent",
        "hr_second_pass_steps": 15,
        "denoising_strength": 0.7,
        "refiner_checkpoint": "sd_xl_refiner_1.0.safetensors",
        "refiner_switch_at": 0.8,
        "restore_faces": True,
        "tiling": False,
        "subseed": -1,
        "subseed_strength": 0,
        "clip_skip": 2,
    }

    metadata = GenerationMetadata(
        request_id=request.id,
        prompt="test prompt",
        negative_prompt="test negative",
        model_name="test_model_v1.0",
        lora_list=[
            {"name": "test_lora_1", "weight": 0.8},
            {"name": "test_lora_2", "weight": 0.5},
        ],
        steps=20,
        cfg_scale=7.0,
        sampler="Euler a",
        scheduler="Automatic",
        seed=12345,
        width=512,
        height=512,
        raw_params=raw_params,
    )

    test_db.add(metadata)
    await test_db.commit()
    await test_db.refresh(metadata)

    # 基本パラメータのテスト
    assert metadata.model_name == "test_model_v1.0"
    assert metadata.prompt == "test prompt"
    assert metadata.negative_prompt == "test negative"
    assert metadata.steps == 20
    assert metadata.cfg_scale == 7.0
    assert metadata.sampler == "Euler a"
    assert metadata.scheduler == "Automatic"
    assert metadata.seed == 12345
    assert metadata.width == 512
    assert metadata.height == 512

    # LoRAのテスト
    assert metadata.lora_list is not None
    assert len(metadata.lora_list) == 2
    assert metadata.lora_list[0]["name"] == "test_lora_1"
    assert metadata.lora_list[1]["name"] == "test_lora_2"

    # raw_paramsのテスト
    assert metadata.raw_params is not None
    assert metadata.raw_params["batch_size"] == 2
    assert metadata.raw_params["enable_hr"] is True
    assert metadata.raw_params["hr_scale"] == 2.0
    assert metadata.raw_params["hr_upscaler"] == "Latent"
    assert metadata.raw_params["hr_second_pass_steps"] == 15
    assert metadata.raw_params["denoising_strength"] == 0.7
    assert metadata.raw_params["refiner_checkpoint"] == "sd_xl_refiner_1.0.safetensors"
    assert metadata.raw_params["refiner_switch_at"] == 0.8
    assert metadata.raw_params["restore_faces"] is True
    assert metadata.raw_params["tiling"] is False  # Falsy値も保存されることを確認
    assert metadata.raw_params["clip_skip"] == 2


@pytest.mark.asyncio
async def test_metadata_with_minimal_parameters(test_db):
    """最小限のパラメータでメタデータが作成できることをテスト"""
    # GenerationRequest を作成
    request = GenerationRequest(
        guild_id="123456789",
        user_id="987654321",
        thread_id="111222333",
        original_instruction="Test instruction",
    )
    test_db.add(request)
    await test_db.commit()
    await test_db.refresh(request)

    # 最小限のパラメータでメタデータを作成
    metadata = GenerationMetadata(
        request_id=request.id,
        prompt="test prompt",
        model_name="test_model",
        steps=20,
        cfg_scale=7.0,
        sampler="Euler a",
        seed=12345,
        width=512,
        height=512,
    )

    test_db.add(metadata)
    await test_db.commit()
    await test_db.refresh(metadata)

    assert metadata.id is not None
    assert metadata.prompt == "test prompt"
    assert metadata.negative_prompt is None
    assert metadata.lora_list is None
    assert metadata.scheduler is None
    assert metadata.raw_params is None


@pytest.mark.asyncio
async def test_metadata_with_legacy_parameters(test_db):
    """古いパラメータ名でもメタデータが作成できることをテスト（互換性確認）"""
    # GenerationRequest を作成
    request = GenerationRequest(
        guild_id="123456789",
        user_id="987654321",
        thread_id="111222333",
        original_instruction="Test instruction",
    )
    test_db.add(request)
    await test_db.commit()
    await test_db.refresh(request)

    # 古いパラメータ名を含むraw_params
    raw_params = {
        "upscale_by": 2.0,
        "hires_upscaler": "Latent",
        "hires_steps": 15,
        "denoising_strength": 0.7,
    }

    metadata = GenerationMetadata(
        request_id=request.id,
        prompt="test prompt",
        model_name="test_model",
        steps=20,
        cfg_scale=7.0,
        sampler="Euler a",
        seed=12345,
        width=512,
        height=512,
        raw_params=raw_params,
    )

    test_db.add(metadata)
    await test_db.commit()
    await test_db.refresh(metadata)

    # 古いパラメータ名でも正しく保存されることを確認
    assert metadata.raw_params is not None
    assert metadata.raw_params["upscale_by"] == 2.0
    assert metadata.raw_params["hires_upscaler"] == "Latent"
    assert metadata.raw_params["hires_steps"] == 15
    assert metadata.raw_params["denoising_strength"] == 0.7


@pytest.mark.asyncio
async def test_metadata_with_falsy_values(test_db):
    """Falsy値（False, 0）が正しく保存・表示されることをテスト"""
    # GenerationRequest を作成
    request = GenerationRequest(
        guild_id="123456789",
        user_id="987654321",
        thread_id="111222333",
        original_instruction="Test instruction",
    )
    test_db.add(request)
    await test_db.commit()
    await test_db.refresh(request)

    # Falsy値を含むraw_params
    raw_params = {
        "tiling": False,  # Boolean False
        "subseed_strength": 0,  # Integer 0
        "restore_faces": False,  # Boolean False
        "clip_skip": 0,  # Integer 0
    }

    metadata = GenerationMetadata(
        request_id=request.id,
        prompt="test prompt",
        model_name="test_model",
        steps=20,
        cfg_scale=7.0,
        sampler="Euler a",
        seed=12345,
        width=512,
        height=512,
        raw_params=raw_params,
    )

    test_db.add(metadata)
    await test_db.commit()
    await test_db.refresh(metadata)

    # Falsy値も正しく保存されることを確認
    assert metadata.raw_params is not None
    assert metadata.raw_params["tiling"] is False
    assert metadata.raw_params["subseed_strength"] == 0
    assert metadata.raw_params["restore_faces"] is False
    assert metadata.raw_params["clip_skip"] == 0

