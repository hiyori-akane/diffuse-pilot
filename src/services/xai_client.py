"""
xAI API クライアント

xAI API (Grok-2-Image) を使用して画像を生成
"""

import base64
from io import BytesIO
from typing import Any

import httpx
from PIL import Image

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.services.error_handler import ApplicationError, ErrorCode

logger = get_logger(__name__)


class XAIAPIError(ApplicationError):
    """xAI API エラー"""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(
            code=ErrorCode.LLM_API_ERROR,
            message=message,
            original_error=original_error,
        )


class XAIClient:
    """xAI API クライアント（画像生成用）"""

    # xAI API のエンドポイント
    BASE_URL = "https://api.x.ai/v1"
    IMAGES_ENDPOINT = "/images/generations"

    def __init__(self):
        self.settings = get_settings()
        if not self.settings.xai_api_key:
            raise XAIAPIError("xAI API キーが設定されていません")

        self.api_key = self.settings.xai_api_key
        self.model = "grok-2-image"  # xAI の画像生成モデル
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTPクライアントを取得（遅延初期化）"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(120.0),  # 画像生成は時間がかかる場合がある
            )
        return self._client

    async def close(self):
        """HTTPクライアントをクローズ"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def generate_images(
        self,
        prompt: str,
        n: int = 1,
        response_format: str = "b64_json",
    ) -> dict[str, Any]:
        """xAI APIで画像を生成

        Args:
            prompt: 画像生成のプロンプト
            n: 生成する画像の枚数（1-10）
            response_format: レスポンスフォーマット ("url" または "b64_json")

        Returns:
            生成結果を含む辞書
            {
                "images": [PIL.Image, ...],
                "prompt": str,
            }
        """
        try:
            client = await self._get_client()

            # リクエストペイロード
            payload = {
                "model": self.model,
                "prompt": prompt,
                "n": min(max(n, 1), 10),  # 1-10の範囲に制限
                "response_format": response_format,
            }

            logger.info(
                "Sending request to xAI API",
                extra={
                    "model": self.model,
                    "prompt_length": len(prompt),
                    "n": payload["n"],
                },
            )

            # API リクエスト
            response = await client.post(self.IMAGES_ENDPOINT, json=payload)

            if response.status_code != 200:
                error_detail = response.text
                logger.error(
                    f"xAI API error: {response.status_code}",
                    extra={"status_code": response.status_code, "response": error_detail},
                )
                raise XAIAPIError(f"xAI API エラー: {response.status_code} - {error_detail}")

            result = response.json()
            images = []

            # レスポンスから画像を抽出
            data = result.get("data", [])
            for item in data:
                if response_format == "b64_json":
                    # Base64 エンコードされた画像データ
                    b64_data = item.get("b64_json")
                    if b64_data:
                        image_bytes = base64.b64decode(b64_data)
                        image = Image.open(BytesIO(image_bytes))
                        images.append(image)
                elif response_format == "url":
                    # URL から画像をダウンロード
                    image_url = item.get("url")
                    if image_url:
                        img_response = await client.get(image_url)
                        if img_response.status_code == 200:
                            image = Image.open(BytesIO(img_response.content))
                            images.append(image)
                        else:
                            logger.warning(f"Failed to download image from URL: {image_url}")

            logger.info(
                f"Generated {len(images)} images via xAI API",
                extra={
                    "prompt_length": len(prompt),
                    "images_count": len(images),
                },
            )

            return {
                "images": images,
                "prompt": prompt,
            }

        except httpx.TimeoutException as e:
            logger.error(f"xAI API timeout: {str(e)}")
            raise XAIAPIError(
                "xAI API リクエストがタイムアウトしました",
                original_error=e,
            ) from e

        except httpx.HTTPStatusError as e:
            logger.error(f"xAI API HTTP error: {str(e)}")
            raise XAIAPIError(
                f"xAI API HTTP エラー: {str(e)}",
                original_error=e,
            ) from e

        except XAIAPIError:
            # 既にXAIAPIErrorの場合はそのまま再raise
            raise

        except Exception as e:
            logger.exception(f"xAI image generation error: {str(e)}")
            raise XAIAPIError(
                f"xAI APIで画像生成エラーが発生しました: {str(e)}",
                original_error=e,
            ) from e
