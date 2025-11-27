"""
xAI クライアントのユニットテスト
"""

import base64
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from src.services.xai_client import XAIAPIError, XAIClient


@pytest.fixture
def mock_settings():
    """モック設定"""
    settings = MagicMock()
    settings.xai_api_key = "test_api_key"
    return settings


@pytest.fixture
def xai_client(mock_settings):
    """xAI クライアントのフィクスチャ"""
    with patch("src.services.xai_client.get_settings", return_value=mock_settings):
        client = XAIClient()
        yield client


def create_test_image_base64() -> str:
    """テスト用のBase64エンコードされた画像を生成"""
    img = Image.new("RGB", (100, 100), color="red")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return base64.b64encode(buffer.read()).decode("utf-8")


@pytest.mark.asyncio
async def test_generate_images_success(xai_client):
    """画像生成が成功するケース"""
    # テスト用の画像データを準備
    test_image_b64 = create_test_image_base64()

    # モックレスポンスを設定
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"b64_json": test_image_b64}]}

    # AsyncClient をモック
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.is_closed = False

    xai_client._client = mock_client

    # テスト実行
    result = await xai_client.generate_images("A beautiful sunset")

    # 検証
    assert "images" in result
    assert "prompt" in result
    assert len(result["images"]) == 1
    assert result["prompt"] == "A beautiful sunset"
    assert isinstance(result["images"][0], Image.Image)

    # API が正しく呼ばれたことを確認
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    assert call_args[0][0] == "/images/generations"
    assert call_args[1]["json"]["prompt"] == "A beautiful sunset"
    assert call_args[1]["json"]["model"] == "grok-2-image"


@pytest.mark.asyncio
async def test_generate_images_with_multiple_images(xai_client):
    """複数画像の生成"""
    # テスト用の画像データを準備
    test_image_b64 = create_test_image_base64()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": [
            {"b64_json": test_image_b64},
            {"b64_json": test_image_b64},
            {"b64_json": test_image_b64},
        ]
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.is_closed = False

    xai_client._client = mock_client

    # テスト実行
    result = await xai_client.generate_images("A cat", n=3)

    # 検証
    assert len(result["images"]) == 3
    for img in result["images"]:
        assert isinstance(img, Image.Image)


@pytest.mark.asyncio
async def test_generate_images_api_error(xai_client):
    """APIエラーが発生するケース"""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.is_closed = False

    xai_client._client = mock_client

    # テスト実行（エラーが発生することを確認）
    with pytest.raises(XAIAPIError) as exc_info:
        await xai_client.generate_images("A test prompt")

    assert "xAI API エラー" in str(exc_info.value.message)
    assert "500" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_generate_images_n_range_limit(xai_client):
    """nパラメータの範囲制限"""
    test_image_b64 = create_test_image_base64()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": [{"b64_json": test_image_b64}]}

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.is_closed = False

    xai_client._client = mock_client

    # n > 10 の場合
    await xai_client.generate_images("Test", n=15)
    call_args = mock_client.post.call_args
    assert call_args[1]["json"]["n"] == 10  # 10に制限

    # n < 1 の場合
    await xai_client.generate_images("Test", n=0)
    call_args = mock_client.post.call_args
    assert call_args[1]["json"]["n"] == 1  # 1に制限


def test_xai_client_no_api_key():
    """APIキーが設定されていない場合のエラー"""
    mock_settings = MagicMock()
    mock_settings.xai_api_key = ""

    with patch("src.services.xai_client.get_settings", return_value=mock_settings):
        with pytest.raises(XAIAPIError) as exc_info:
            XAIClient()

        assert "API キーが設定されていません" in str(exc_info.value.message)


@pytest.mark.asyncio
async def test_close_client(xai_client):
    """クライアントのクローズ"""
    mock_client = AsyncMock()
    mock_client.is_closed = False
    mock_client.aclose = AsyncMock()

    xai_client._client = mock_client

    await xai_client.close()

    mock_client.aclose.assert_called_once()
    assert xai_client._client is None


@pytest.mark.asyncio
async def test_generate_images_url_format(xai_client):
    """URL形式でのレスポンス処理"""
    # テスト用の画像を準備
    img = Image.new("RGB", (100, 100), color="blue")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    image_bytes = buffer.getvalue()

    # 画像URLからのダウンロードレスポンス
    mock_image_response = MagicMock()
    mock_image_response.status_code = 200
    mock_image_response.content = image_bytes

    # APIレスポンス
    mock_api_response = MagicMock()
    mock_api_response.status_code = 200
    mock_api_response.json.return_value = {"data": [{"url": "https://example.com/image.png"}]}

    # AsyncClient をモック
    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_api_response)
    mock_client.get = AsyncMock(return_value=mock_image_response)
    mock_client.is_closed = False

    xai_client._client = mock_client

    # テスト実行
    result = await xai_client.generate_images("A test", response_format="url")

    # 検証
    assert len(result["images"]) == 1
    assert isinstance(result["images"][0], Image.Image)
    mock_client.get.assert_called_once_with("https://example.com/image.png")
