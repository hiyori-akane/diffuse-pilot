"""
Stable Diffusion API クライアント

Automatic1111 Web API を使用して画像を生成
"""

import base64
import json
from io import BytesIO
from typing import Any, Optional

import httpx
from PIL import Image

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.services.error_handler import (
    StableDiffusionAPIError,
    StableDiffusionTimeoutError,
)

logger = get_logger(__name__)


class SDGenerationParams:
    """Stable Diffusion 生成パラメータ"""

    def __init__(
        self,
        prompt: str,
        negative_prompt: str = "",
        model_name: Optional[str] = None,
        lora_list: Optional[list[dict[str, Any]]] = None,
        steps: int = 20,
        cfg_scale: float = 7.0,
        sampler: Optional[str] = None,
        scheduler: Optional[str] = None,
        seed: int = -1,
        width: int = 512,
        height: int = 512,
        batch_size: int = 1,
        **kwargs,
    ):
        self.prompt = prompt
        self.negative_prompt = negative_prompt
        self.model_name = model_name
        self.lora_list = lora_list or []
        self.steps = steps
        self.cfg_scale = cfg_scale
        self.sampler = sampler
        self.scheduler = scheduler
        self.seed = seed
        self.width = width
        self.height = height
        self.batch_size = batch_size
        self.extra_params = kwargs

    def to_dict(self) -> dict[str, Any]:
        """API リクエスト用の辞書に変換"""
        params = {
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "steps": self.steps,
            "cfg_scale": self.cfg_scale,
            "seed": self.seed,
            "width": self.width,
            "height": self.height,
            "batch_size": self.batch_size,
        }

        if self.sampler:
            params["sampler_name"] = self.sampler

        if self.scheduler:
            params["scheduler"] = self.scheduler

        # 追加パラメータ
        params.update(self.extra_params)

        return params


class StableDiffusionClient:
    """Stable Diffusion API クライアント"""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.sd_api_url
        self.timeout = self.settings.sd_api_timeout
        self.client = httpx.AsyncClient(timeout=self.timeout)

    async def close(self):
        """クライアントを閉じる"""
        await self.client.aclose()

    async def txt2img(self, params: SDGenerationParams) -> list[Image.Image]:
        """テキストから画像を生成

        Args:
            params: 生成パラメータ

        Returns:
            生成された画像のリスト

        Raises:
            StableDiffusionAPIError: API エラー
            StableDiffusionTimeoutError: タイムアウト
        """
        try:
            logger.info(
                f"Generating images: {params.width}x{params.height}, "
                f"steps={params.steps}, batch={params.batch_size}"
            )

            # API リクエスト
            request_data = params.to_dict()

            # サンプラー検証（存在しない場合は省略し API に委ねる）
            sampler_name = request_data.get("sampler_name")
            if sampler_name:
                try:
                    # キャッシュされたサンプラー一覧を使用（未取得なら取得）
                    if not hasattr(self, "_cached_samplers"):
                        self._cached_samplers = await self.get_samplers()
                    if sampler_name not in self._cached_samplers:
                        logger.warning(
                            f"Unknown sampler '{sampler_name}', omitting to let API choose",
                            extra={"sampler_name": sampler_name},
                        )
                        # 不明サンプラーを除去
                        request_data.pop("sampler_name", None)
                except Exception as _e:
                    # 検証失敗時は警告のみで続行
                    logger.warning(
                        "Sampler validation failed, proceeding without validation",
                        extra={"error": str(_e)},
                    )

            # スケジューラ検証（存在しない場合は省略し API に委ねる）
            scheduler = request_data.get("scheduler")
            if scheduler:
                try:
                    # キャッシュされたスケジューラ一覧を使用（未取得なら取得）
                    if not hasattr(self, "_cached_schedulers"):
                        self._cached_schedulers = await self.get_schedulers()
                    if scheduler not in self._cached_schedulers:
                        logger.warning(
                            f"Unknown scheduler '{scheduler}', omitting to let API choose",
                            extra={"scheduler": scheduler},
                        )
                        # 不明スケジューラを除去
                        request_data.pop("scheduler", None)
                except Exception as _e:
                    # 検証失敗時は警告のみで続行
                    logger.warning(
                        "Scheduler validation failed, proceeding without validation",
                        extra={"error": str(_e)},
                    )

            # 送信前のサンプラー/スケジューラ確認ログ
            logger.info(
                (
                    "SD request parameters: sampler_name=%s scheduler=%s steps=%s cfg_scale=%s "
                    "size=%sx%s batch_size=%s"
                ),
                request_data.get("sampler_name"),
                request_data.get("scheduler"),
                request_data.get("steps"),
                request_data.get("cfg_scale"),
                request_data.get("width"),
                request_data.get("height"),
                request_data.get("batch_size"),
            )

            response = await self.client.post(
                f"{self.base_url}/sdapi/v1/txt2img", json=request_data
            )

            if response.status_code != 200:
                error_msg = f"SD API error: {response.status_code}"
                logger.error(error_msg, extra={"response_text": response.text[:500]})
                raise StableDiffusionAPIError(
                    error_msg, details={"status_code": response.status_code, "body": response.text}
                )

            # レスポンス解析
            result = response.json()
            images_data = result.get("images", [])

            if not images_data:
                raise StableDiffusionAPIError("No images in response")

            # Base64 デコードして PIL Image に変換
            images = []
            for img_data in images_data:
                img_bytes = base64.b64decode(img_data)
                img = Image.open(BytesIO(img_bytes))
                images.append(img)

            logger.info(
                f"Image generation complete: {len(images)} images generated",
                extra={"seed": result.get("parameters", {}).get("seed")},
            )

            return images

        except httpx.TimeoutException as e:
            error_msg = f"SD API timeout after {self.timeout} seconds"
            logger.error(error_msg)
            raise StableDiffusionTimeoutError(
                error_msg, details={"timeout": self.timeout}, original_error=e
            )

        except httpx.RequestError as e:
            error_msg = f"SD API request error: {str(e)}"
            logger.error(error_msg)
            raise StableDiffusionAPIError(error_msg, original_error=e)

        except json.JSONDecodeError as e:
            error_msg = "Failed to decode SD API response"
            logger.error(error_msg)
            raise StableDiffusionAPIError(error_msg, original_error=e)

        except Exception as e:
            if isinstance(e, (StableDiffusionAPIError, StableDiffusionTimeoutError)):
                raise
            error_msg = f"Unexpected error in SD client: {str(e)}"
            logger.exception(error_msg)
            raise StableDiffusionAPIError(error_msg, original_error=e)

    async def get_models(self) -> list[str]:
        """利用可能なモデルのリストを取得

        Returns:
            モデル名のリスト

        Raises:
            StableDiffusionAPIError: API エラー
        """
        try:
            response = await self.client.get(f"{self.base_url}/sdapi/v1/sd-models")

            if response.status_code != 200:
                raise StableDiffusionAPIError(
                    f"Failed to get models: {response.status_code}",
                    details={"body": response.text},
                )

            models = response.json()
            model_names = [m.get("model_name", m.get("title", "")) for m in models]

            logger.info(f"Retrieved {len(model_names)} models from SD API")
            return model_names

        except Exception as e:
            if isinstance(e, StableDiffusionAPIError):
                raise
            logger.error(f"Error getting models: {str(e)}")
            raise StableDiffusionAPIError("Failed to get models", original_error=e)

    async def get_loras(self) -> list[dict[str, Any]]:
        """利用可能な LoRA のリストを取得

        Returns:
            LoRA 情報のリスト

        Raises:
            StableDiffusionAPIError: API エラー
        """
        try:
            response = await self.client.get(f"{self.base_url}/sdapi/v1/loras")

            if response.status_code != 200:
                raise StableDiffusionAPIError(
                    f"Failed to get LoRAs: {response.status_code}",
                    details={"body": response.text},
                )

            loras = response.json()
            logger.info(f"Retrieved {len(loras)} LoRAs from SD API")
            return loras

        except Exception as e:
            if isinstance(e, StableDiffusionAPIError):
                raise
            logger.error(f"Error getting LoRAs: {str(e)}")
            raise StableDiffusionAPIError("Failed to get LoRAs", original_error=e)

    async def get_samplers(self) -> list[str]:
        """利用可能なサンプラーのリストを取得

        Returns:
            サンプラー名のリスト

        Raises:
            StableDiffusionAPIError: API エラー
        """
        try:
            response = await self.client.get(f"{self.base_url}/sdapi/v1/samplers")

            if response.status_code != 200:
                raise StableDiffusionAPIError(
                    f"Failed to get samplers: {response.status_code}",
                    details={"body": response.text},
                )

            samplers = response.json()
            sampler_names = [s.get("name", "") for s in samplers]

            logger.info(f"Retrieved {len(sampler_names)} samplers from SD API")
            return sampler_names

        except Exception as e:
            if isinstance(e, StableDiffusionAPIError):
                raise
            logger.error(f"Error getting samplers: {str(e)}")
            raise StableDiffusionAPIError("Failed to get samplers", original_error=e)

    async def get_schedulers(self) -> list[str]:
        """利用可能なスケジューラのリストを取得

        Returns:
            スケジューラ名のリスト

        Raises:
            StableDiffusionAPIError: API エラー
        """
        try:
            response = await self.client.get(f"{self.base_url}/sdapi/v1/schedulers")

            if response.status_code != 200:
                raise StableDiffusionAPIError(
                    f"Failed to get schedulers: {response.status_code}",
                    details={"body": response.text},
                )

            schedulers = response.json()
            scheduler_names = [s.get("name", "") for s in schedulers]

            logger.info(f"Retrieved {len(scheduler_names)} schedulers from SD API")
            return scheduler_names

        except Exception as e:
            if isinstance(e, StableDiffusionAPIError):
                raise
            logger.error(f"Error getting schedulers: {str(e)}")
            raise StableDiffusionAPIError("Failed to get schedulers", original_error=e)

    async def get_upscalers(self) -> list[str]:
        """利用可能なアップスケーラーのリストを取得

        Returns:
            アップスケーラー名のリスト

        Raises:
            StableDiffusionAPIError: API エラー
        """
        try:
            response = await self.client.get(f"{self.base_url}/sdapi/v1/upscalers")

            if response.status_code != 200:
                raise StableDiffusionAPIError(
                    f"Failed to get upscalers: {response.status_code}",
                    details={"body": response.text},
                )

            upscalers = response.json()
            upscaler_names = [u.get("name", "") for u in upscalers]

            logger.info(f"Retrieved {len(upscaler_names)} upscalers from SD API")
            return upscaler_names

        except Exception as e:
            if isinstance(e, StableDiffusionAPIError):
                raise
            logger.error(f"Error getting upscalers: {str(e)}")
            raise StableDiffusionAPIError("Failed to get upscalers", original_error=e)
