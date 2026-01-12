"""Unit tests for models"""
import pytest
from datetime import datetime

from src.models.generation import GenerationRequest, GenerationMetadata, GeneratedImage, RequestStatus


@pytest.mark.asyncio
async def test_generation_request_creation(test_db):
    """GenerationRequest の作成テスト"""
    request = GenerationRequest(
        guild_id="123456789",
        user_id="987654321",
        thread_id="111222333",
        original_instruction="Test instruction",
        status=RequestStatus.PENDING,
    )

    test_db.add(request)
    await test_db.commit()
    await test_db.refresh(request)

    assert request.id is not None
    assert request.guild_id == "123456789"
    assert request.status == RequestStatus.PENDING
    assert isinstance(request.created_at, datetime)


@pytest.mark.asyncio
async def test_generation_metadata_creation(test_db):
    """GenerationMetadata の作成テスト"""
    # まず GenerationRequest を作成
    request = GenerationRequest(
        guild_id="123456789",
        user_id="987654321",
        thread_id="111222333",
        original_instruction="Test instruction",
    )
    test_db.add(request)
    await test_db.commit()
    await test_db.refresh(request)

    # GenerationMetadata を作成
    metadata = GenerationMetadata(
        request_id=request.id,
        prompt="test prompt",
        negative_prompt="test negative",
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
    assert metadata.request_id == request.id
    assert metadata.prompt == "test prompt"
    assert metadata.steps == 20


@pytest.mark.asyncio
async def test_generated_image_creation(test_db):
    """GeneratedImage の作成テスト"""
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

    # GenerationMetadata を作成
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

    # GeneratedImage を作成
    image = GeneratedImage(
        request_id=request.id,
        metadata_id=metadata.id,
        file_path="/path/to/image.png",
        file_size_bytes=1024000,
    )

    test_db.add(image)
    await test_db.commit()
    await test_db.refresh(image)

    assert image.id is not None
    assert image.request_id == request.id
    assert image.metadata_id == metadata.id
    assert image.file_path == "/path/to/image.png"
    assert image.file_size_bytes == 1024000
