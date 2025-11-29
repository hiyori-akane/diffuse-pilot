import pytest
from src.services.prompt_agent import PromptAgent
from src.models.generation import GenerationMetadata


@pytest.mark.asyncio
async def test_sampler_precedence_previous_metadata(monkeypatch):
    agent = PromptAgent()

    # Fake LLM response (sampler should be overridden by previous metadata)
    llm_result = {
        "prompt": "test prompt",
        "negative_prompt": "neg",
        "steps": 25,
        "cfg_scale": 8.0,
        "sampler": "DPM++ 2M Karras",
        "width": 768,
        "height": 768,
    }

    prev_meta = GenerationMetadata(
        request_id=1,
        prompt="prev prompt",
        negative_prompt="prev neg",
        model_name="model",
        steps=30,
        cfg_scale=7.5,
        sampler="Euler a",
        seed=42,
        width=512,
        height=512,
    )

    applied = agent._apply_defaults(llm_result, previous_metadata=prev_meta)
    assert applied["sampler"] == "Euler a"  # previous metadata wins
    assert applied["steps"] == 30


@pytest.mark.asyncio
async def test_sampler_precedence_global_settings(monkeypatch):
    agent = PromptAgent()

    llm_result = {
        "prompt": "test prompt",
        "negative_prompt": "neg",
        # sampler omitted to force default path
        "steps": None,
        "cfg_scale": None,
        "sampler": None,
        "width": None,
        "height": None,
    }

    global_settings = {
        "default_sd_params": {
            "steps": 40,
            "cfg_scale": 9.0,
            "sampler": "DDIM",
            "width": 640,
            "height": 640,
        }
    }

    applied = agent._apply_defaults(llm_result, global_settings=global_settings)
    assert applied["sampler"] == "DDIM"
    assert applied["steps"] == 40
    assert applied["width"] == 640


@pytest.mark.asyncio
async def test_sampler_falls_back_to_app_defaults(monkeypatch):
    agent = PromptAgent()
    llm_result = {
        "prompt": "p",
        "negative_prompt": "n",
        "steps": None,
        "cfg_scale": None,
        "sampler": None,
        "width": None,
        "height": None,
    }
    applied = agent._apply_defaults(llm_result)
    # Application defaults from settings should be applied (sampler defined in settings)
    assert applied["sampler"] == agent.settings.default_sampler
    assert applied["steps"] == agent.settings.default_steps


@pytest.mark.asyncio
async def test_scheduler_precedence_previous_metadata(monkeypatch):
    """Scheduler が前回メタデータで優先されるか"""
    agent = PromptAgent()

    llm_result = {
        "prompt": "test",
        "negative_prompt": "neg",
        "steps": 25,
        "cfg_scale": 8.0,
        "sampler": "DDIM",
        "scheduler": "Exponential",
        "width": 512,
        "height": 512,
    }

    prev_meta = GenerationMetadata(
        request_id=1,
        prompt="prev prompt",
        negative_prompt="prev neg",
        model_name="model",
        steps=30,
        cfg_scale=7.5,
        sampler="Euler a",
        scheduler="Karras",
        seed=42,
        width=512,
        height=512,
    )

    applied = agent._apply_defaults(llm_result, previous_metadata=prev_meta)
    assert applied["scheduler"] == "Karras"  # previous metadata wins


@pytest.mark.asyncio
async def test_scheduler_from_global_settings(monkeypatch):
    """Scheduler がグローバル設定から取得されるか"""
    agent = PromptAgent()

    llm_result = {
        "prompt": "test",
        "negative_prompt": "neg",
        "steps": None,
        "cfg_scale": None,
        "sampler": None,
        "scheduler": None,
        "width": None,
        "height": None,
    }

    global_settings = {
        "default_sd_params": {
            "steps": 40,
            "cfg_scale": 9.0,
            "sampler": "DPM++ 2M",
            "scheduler": "Automatic",
            "width": 640,
            "height": 640,
        }
    }

    applied = agent._apply_defaults(llm_result, global_settings=global_settings)
    assert applied["scheduler"] == "Automatic"
    assert applied["sampler"] == "DPM++ 2M"


@pytest.mark.asyncio
async def test_scheduler_falls_back_to_app_defaults(monkeypatch):
    """Scheduler が未指定の場合 app defaults (None) になるか"""
    agent = PromptAgent()
    llm_result = {
        "prompt": "p",
        "negative_prompt": "n",
        "steps": None,
        "cfg_scale": None,
        "sampler": None,
        "scheduler": None,
        "width": None,
        "height": None,
    }
    applied = agent._apply_defaults(llm_result)
    # scheduler のアプリ既定は None（未設定なら送信しない）
    assert applied.get("scheduler") == agent.settings.default_scheduler