"""
Ollama LLM クライアント

プロンプト生成のための LLM API クライアント
"""

import json
from typing import Any

import httpx

from src.config.logging import get_logger
from src.config.settings import get_settings
from src.services.error_handler import LLMAPIError

logger = get_logger(__name__)


class OllamaClient:
    """Ollama API クライアント"""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.ollama_api_url
        self.model = self.settings.ollama_model
        self.client = httpx.AsyncClient(timeout=600.0)

    async def close(self):
        """クライアントを閉じる"""
        await self.client.aclose()

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """テキスト生成

        Args:
            prompt: プロンプト
            system: システムプロンプト
            temperature: 温度パラメータ
            max_tokens: 最大トークン数

        Returns:
            生成されたテキスト

        Raises:
            LLMAPIError: API エラー
        """
        try:
            logger.info(f"Generating text with Ollama: model={self.model}")

            # リクエストボディ構築
            request_data: dict[str, Any] = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature},
            }

            if system:
                request_data["system"] = system

            if max_tokens:
                request_data["options"]["num_predict"] = max_tokens

            # API 呼び出し
            response = await self.client.post(f"{self.base_url}/api/generate", json=request_data)

            if response.status_code != 200:
                error_msg = f"Ollama API error: {response.status_code}"
                logger.error(error_msg, extra={"response_text": response.text})
                raise LLMAPIError(
                    error_msg, details={"status_code": response.status_code, "body": response.text}
                )

            # レスポンス解析
            result = response.json()
            generated_text = result.get("response", "").strip()

            if not generated_text:
                raise LLMAPIError("Empty response from Ollama")

            logger.info(
                f"Text generation complete: {len(generated_text)} characters",
                extra={"prompt_length": len(prompt)},
            )

            return generated_text

        except httpx.TimeoutException:
            error_msg = "リクエストがタイムアウトしました"
            logger.error(error_msg)
            raise LLMAPIError(error_msg, original_error=e)

        except httpx.HTTPStatusError as exc:
            error_msg = f"HTTPエラーが発生しました。ステータスコード: {exc.response.status_code}"
            logger.error(error_msg)
            raise LLMAPIError(error_msg, original_error=e)

        except httpx.RequestError as e:
            error_msg = f"Ollama API request error: {e}"
            logger.error(error_msg)
            raise LLMAPIError(error_msg, original_error=e)

        except json.JSONDecodeError as e:
            error_msg = "Failed to decode Ollama response"
            logger.error(error_msg)
            raise LLMAPIError(error_msg, original_error=e)

        except Exception as e:
            if isinstance(e, LLMAPIError):
                raise
            error_msg = f"Unexpected error in Ollama client: {str(e)}"
            logger.exception(error_msg)
            raise LLMAPIError(error_msg, original_error=e)

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        format: dict[str, Any] | None = None,
    ) -> str:
        """チャット形式で生成

        Args:
            messages: メッセージリスト [{"role": "user|assistant|system", "content": "..."}]
            temperature: 温度パラメータ
            max_tokens: 最大トークン数
            format: JSON schema for structured outputs (optional)

        Returns:
            生成されたテキスト

        Raises:
            LLMAPIError: API エラー
        """
        try:
            logger.info(f"Chat generation with Ollama: model={self.model}")

            # リクエストボディ構築
            request_data: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            }

            if max_tokens:
                request_data["options"]["num_predict"] = max_tokens

            if format:
                request_data["format"] = format

            # API 呼び出し
            response = await self.client.post(f"{self.base_url}/api/chat", json=request_data)

            if response.status_code != 200:
                error_msg = f"Ollama API error: {response.status_code}"
                logger.error(error_msg, extra={"response_text": response.text})
                raise LLMAPIError(
                    error_msg, details={"status_code": response.status_code, "body": response.text}
                )

            # レスポンス解析
            result = response.json()
            message = result.get("message", {})
            generated_text = message.get("content", "").strip()

            if not generated_text:
                raise LLMAPIError("Empty response from Ollama")

            logger.info(
                f"Chat generation complete: {len(generated_text)} characters",
                extra={"message_count": len(messages)},
            )

            return generated_text

        except httpx.RequestError as e:
            error_msg = f"Ollama API request error: {str(e)}"
            logger.error(error_msg)
            raise LLMAPIError(error_msg, original_error=e)

        except json.JSONDecodeError as e:
            error_msg = "Failed to decode Ollama response"
            logger.error(error_msg)
            raise LLMAPIError(error_msg, original_error=e)

        except Exception as e:
            if isinstance(e, LLMAPIError):
                raise
            error_msg = f"Unexpected error in Ollama client: {str(e)}"
            logger.exception(error_msg)
            raise LLMAPIError(error_msg, original_error=e)
