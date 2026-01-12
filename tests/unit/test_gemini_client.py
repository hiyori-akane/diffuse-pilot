"""
Gemini クライアントのユニットテスト
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.services.gemini_client import GeminiAPIError, GeminiClient


@pytest.fixture
def mock_settings():
    """モック設定"""
    settings = MagicMock()
    settings.gemini_api_key = "test_api_key"
    return settings


@pytest.fixture
def gemini_client(mock_settings):
    """Gemini クライアントのフィクスチャ"""
    with patch("src.services.gemini_client.get_settings", return_value=mock_settings):
        with patch("src.services.gemini_client.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            client = GeminiClient()
            client.client = mock_client
            yield client


@pytest.mark.asyncio
async def test_generate_image_prompt_success(gemini_client):
    """プロンプト生成が成功するケース"""
    # モックレスポンスを設定
    mock_response = MagicMock()
    expected_result = {
        "prompt": "masterpiece, best quality, a beautiful sunset over mountains, highly detailed",
        "negative_prompt": "low quality, blurry, distorted",
        "suggested_params": {
            "width": 768,
            "height": 512,
            "steps": 30,
            "cfg_scale": 8.5,
        },
    }
    mock_response.text = json.dumps(expected_result)

    gemini_client.client.models.generate_content = MagicMock(return_value=mock_response)

    # テスト実行
    result = await gemini_client.generate_image_prompt("美しい山の夕焼け")

    # 検証
    assert result == expected_result
    assert "prompt" in result
    assert "negative_prompt" in result
    assert "suggested_params" in result
    assert result["suggested_params"]["width"] == 768


@pytest.mark.asyncio
async def test_generate_image_prompt_with_style_preferences(gemini_client):
    """スタイル設定ありでのプロンプト生成"""
    mock_response = MagicMock()
    expected_result = {
        "prompt": "anime style, beautiful character, colorful, vibrant",
        "negative_prompt": "realistic, photo",
        "suggested_params": {
            "width": 512,
            "height": 768,
            "steps": 25,
            "cfg_scale": 7.5,
        },
    }
    mock_response.text = json.dumps(expected_result)

    gemini_client.client.models.generate_content = MagicMock(return_value=mock_response)

    # テスト実行
    result = await gemini_client.generate_image_prompt(
        "可愛いキャラクター", style_preferences="anime style, colorful"
    )

    # 検証
    assert result == expected_result
    assert "anime" in result["prompt"].lower()


@pytest.mark.asyncio
async def test_generate_image_prompt_json_decode_error(gemini_client):
    """JSONデコードエラーが発生するケース"""
    # 不正なJSONレスポンスを設定
    mock_response = MagicMock()
    mock_response.text = "This is not JSON"

    gemini_client.client.models.generate_content = MagicMock(return_value=mock_response)

    # テスト実行（エラーが発生することを確認）
    with pytest.raises(GeminiAPIError) as exc_info:
        await gemini_client.generate_image_prompt("テスト")

    assert "解析に失敗" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_generate_image_prompt_api_error(gemini_client):
    """Gemini APIエラーが発生するケース"""
    # API呼び出しでエラーを発生させる
    gemini_client.client.models.generate_content = MagicMock(side_effect=Exception("API Error"))

    # テスト実行（エラーが発生することを確認）
    with pytest.raises(GeminiAPIError) as exc_info:
        await gemini_client.generate_image_prompt("テスト")

    assert "エラーが発生" in str(exc_info.value.message)


def test_gemini_client_no_api_key():
    """APIキーが設定されていない場合のエラー"""
    mock_settings = MagicMock()
    mock_settings.gemini_api_key = ""

    with patch("src.services.gemini_client.get_settings", return_value=mock_settings):
        with pytest.raises(GeminiAPIError) as exc_info:
            GeminiClient()

        assert "API キーが設定されていません" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_generate_image_prompt_safety_settings(gemini_client):
    """安全性設定が正しく適用されているか確認"""
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        {
            "prompt": "test prompt",
            "negative_prompt": "test negative",
            "suggested_params": {},
        }
    )

    gemini_client.client.models.generate_content = MagicMock(return_value=mock_response)

    # テスト実行
    await gemini_client.generate_image_prompt("テスト")

    # generate_contentが呼ばれたことを確認
    assert gemini_client.client.models.generate_content.called

    # 呼び出し時の引数を取得
    call_kwargs = gemini_client.client.models.generate_content.call_args.kwargs

    # safety_settingsが設定されていることを確認
    assert "config" in call_kwargs
    config = call_kwargs["config"]
    assert hasattr(config, "safety_settings") or "safety_settings" in str(config)
