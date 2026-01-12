"""Tests for PromptAgent with structured outputs"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.prompt_agent import PromptAgent, PromptGenerationResponse


@pytest.fixture
def mock_settings():
    """Mock settings"""
    settings = MagicMock()
    settings.default_steps = 30
    settings.default_cfg_scale = 7.5
    settings.default_sampler = "Euler a"
    settings.default_width = 512
    settings.default_height = 512
    return settings


@pytest.fixture
def mock_ollama_client():
    """Mock OllamaClient"""
    client = MagicMock()
    client.chat = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def prompt_agent(mock_settings, mock_ollama_client):
    """Create PromptAgent with mocked dependencies"""
    with patch("src.services.prompt_agent.get_settings", return_value=mock_settings):
        with patch("src.services.prompt_agent.OllamaClient", return_value=mock_ollama_client):
            agent = PromptAgent()
            return agent


@pytest.mark.asyncio
async def test_prompt_generation_response_schema():
    """Test PromptGenerationResponse schema validation"""
    # Valid response
    valid_data = {
        "prompt": "masterpiece, best quality, beautiful landscape",
        "negative_prompt": "worst quality, low quality, blurry",
        "steps": 30,
        "cfg_scale": 7.5,
        "sampler": "Euler a",
        "width": 512,
        "height": 512,
    }
    response = PromptGenerationResponse(**valid_data)
    assert response.prompt == valid_data["prompt"]
    assert response.steps == 30
    assert response.cfg_scale == 7.5

    # Test JSON schema generation
    schema = PromptGenerationResponse.model_json_schema()
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "prompt" in schema["properties"]
    assert "negative_prompt" in schema["properties"]
    assert "steps" in schema["properties"]
    assert "cfg_scale" in schema["properties"]
    assert "sampler" in schema["properties"]
    assert "width" in schema["properties"]
    assert "height" in schema["properties"]


@pytest.mark.asyncio
async def test_generate_prompt_with_structured_output(prompt_agent, mock_ollama_client):
    """Test generate_prompt uses structured outputs"""
    # Mock LLM response - structured JSON
    mock_response = {
        "prompt": "masterpiece, best quality, anime girl, detailed face",
        "negative_prompt": "worst quality, low quality, blurry, bad anatomy",
        "steps": 28,
        "cfg_scale": 7.0,
        "sampler": "DPM++ 2M Karras",
        "width": 512,
        "height": 768,
    }
    mock_ollama_client.chat.return_value = json.dumps(mock_response)

    result = await prompt_agent.generate_prompt("an anime girl")

    # Verify chat was called with format parameter
    mock_ollama_client.chat.assert_called_once()
    call_kwargs = mock_ollama_client.chat.call_args.kwargs
    assert "format" in call_kwargs
    assert call_kwargs["format"] is not None
    assert "temperature" in call_kwargs
    assert call_kwargs["temperature"] == 0.7  # Use temperature 0.7 for creative prompt generation

    # Verify result contains expected fields
    assert "prompt" in result
    assert "negative_prompt" in result
    assert "steps" in result
    assert "cfg_scale" in result
    assert "sampler" in result
    assert "width" in result
    assert "height" in result
    assert "seed" in result  # Should be added by _apply_defaults


@pytest.mark.asyncio
async def test_generate_prompt_validates_response_schema(prompt_agent, mock_ollama_client):
    """Test that invalid structured output raises validation error"""
    # Mock invalid LLM response - missing required fields
    invalid_response = {
        "prompt": "test prompt",
        # Missing other required fields
    }
    mock_ollama_client.chat.return_value = json.dumps(invalid_response)

    with pytest.raises(Exception):  # Should raise pydantic ValidationError
        await prompt_agent.generate_prompt("test")


@pytest.mark.asyncio
async def test_structured_output_schema_constraints():
    """Test that schema constraints are properly defined"""
    schema = PromptGenerationResponse.model_json_schema()

    # Check steps constraints
    steps_schema = schema["properties"]["steps"]
    assert steps_schema["type"] == "integer"
    assert steps_schema.get("minimum") == 1
    assert steps_schema.get("maximum") == 150

    # Check cfg_scale constraints
    cfg_scale_schema = schema["properties"]["cfg_scale"]
    assert cfg_scale_schema["type"] == "number"
    assert cfg_scale_schema.get("minimum") == 1.0
    assert cfg_scale_schema.get("maximum") == 30.0

    # Check width/height constraints
    width_schema = schema["properties"]["width"]
    assert width_schema["type"] == "integer"
    assert width_schema.get("minimum") == 64
    assert width_schema.get("maximum") == 2048

    height_schema = schema["properties"]["height"]
    assert height_schema["type"] == "integer"
    assert height_schema.get("minimum") == 64
    assert height_schema.get("maximum") == 2048


@pytest.mark.asyncio
async def test_close_client(prompt_agent, mock_ollama_client):
    """Test that close properly closes the client"""
    await prompt_agent.close()
    mock_ollama_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_global_settings_override_llm_values(prompt_agent, mock_ollama_client):
    """Test that global settings override LLM-generated values with correct priority"""
    # Mock LLM response with different values
    mock_response = {
        "prompt": "test prompt",
        "negative_prompt": "test negative",
        "steps": 20,  # LLM suggests 20
        "cfg_scale": 7.0,  # LLM suggests 7.0
        "sampler": "Euler a",  # LLM suggests Euler a
        "width": 512,
        "height": 512,
    }
    mock_ollama_client.chat.return_value = json.dumps(mock_response)

    # Global settings with different values
    global_settings = {
        "default_sd_params": {
            "steps": 30,  # User wants 30 steps
            "cfg_scale": 8.5,  # User wants 8.5 CFG
            "sampler": "DPM++ 2M Karras",  # User wants different sampler
        },
        "seed": 20251121,  # User wants specific seed
    }

    result = await prompt_agent.generate_prompt("test instruction", global_settings=global_settings)

    # Verify user settings override LLM values
    assert result["steps"] == 30, "User setting for steps should override LLM value"
    assert result["cfg_scale"] == 8.5, "User setting for cfg_scale should override LLM value"
    assert result["sampler"] == "DPM++ 2M Karras", "User setting for sampler should override LLM value"
    assert result["seed"] == 20251121, "User setting for seed should be applied"
    # Prompt should still come from LLM
    assert "test prompt" in result["prompt"]
