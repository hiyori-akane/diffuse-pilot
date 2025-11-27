"""
エラーハンドリングユーティリティ

一貫したエラーレスポンスを提供します。
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel

from src.config.logging import get_logger

logger = get_logger(__name__)


class ErrorCode(str, Enum):
    """エラーコード"""

    # 一般エラー
    INTERNAL_ERROR = "INTERNAL_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Discord 関連
    DISCORD_API_ERROR = "DISCORD_API_ERROR"
    DISCORD_PERMISSION_ERROR = "DISCORD_PERMISSION_ERROR"

    # Stable Diffusion 関連
    SD_API_ERROR = "SD_API_ERROR"
    SD_API_TIMEOUT = "SD_API_TIMEOUT"
    SD_MODEL_NOT_FOUND = "SD_MODEL_NOT_FOUND"
    SD_LORA_NOT_FOUND = "SD_LORA_NOT_FOUND"

    # LLM 関連
    LLM_API_ERROR = "LLM_API_ERROR"
    LLM_GENERATION_ERROR = "LLM_GENERATION_ERROR"

    # データベース関連
    DATABASE_ERROR = "DATABASE_ERROR"
    RECORD_NOT_FOUND = "RECORD_NOT_FOUND"

    # ストレージ関連
    STORAGE_ERROR = "STORAGE_ERROR"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"


class ErrorResponse(BaseModel):
    """エラーレスポンス"""

    code: ErrorCode
    message: str
    details: Optional[dict[str, Any]] = None


class ApplicationError(Exception):
    """アプリケーション基底例外"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: Optional[dict[str, Any]] = None,
        original_error: Optional[Exception] = None,
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        self.original_error = original_error
        super().__init__(message)

    def to_response(self) -> ErrorResponse:
        """ErrorResponse に変換"""
        return ErrorResponse(code=self.code, message=self.message, details=self.details)


class DiscordAPIError(ApplicationError):
    """Discord API エラー"""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None, **kwargs):
        super().__init__(
            code=ErrorCode.DISCORD_API_ERROR, message=message, details=details, **kwargs
        )


class StableDiffusionAPIError(ApplicationError):
    """Stable Diffusion API エラー"""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None, **kwargs):
        super().__init__(code=ErrorCode.SD_API_ERROR, message=message, details=details, **kwargs)


class StableDiffusionTimeoutError(ApplicationError):
    """Stable Diffusion タイムアウトエラー"""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None, **kwargs):
        super().__init__(code=ErrorCode.SD_API_TIMEOUT, message=message, details=details, **kwargs)


class LLMAPIError(ApplicationError):
    """LLM API エラー"""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None, **kwargs):
        super().__init__(code=ErrorCode.LLM_API_ERROR, message=message, details=details, **kwargs)


class DatabaseError(ApplicationError):
    """データベースエラー"""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None, **kwargs):
        super().__init__(code=ErrorCode.DATABASE_ERROR, message=message, details=details, **kwargs)


class RecordNotFoundError(ApplicationError):
    """レコード未検出エラー"""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None, **kwargs):
        super().__init__(
            code=ErrorCode.RECORD_NOT_FOUND, message=message, details=details, **kwargs
        )


def handle_error(error: Exception, context: Optional[dict[str, Any]] = None) -> ErrorResponse:
    """エラーをハンドリングして ErrorResponse を返す

    Args:
        error: 例外
        context: コンテキスト情報

    Returns:
        ErrorResponse
    """
    context = context or {}

    if isinstance(error, ApplicationError):
        logger.error(
            f"Application error: {error.code} - {error.message}",
            extra={"error_details": error.details, **context},
        )
        return error.to_response()

    # 予期しないエラー
    logger.exception("Unexpected error", extra=context)
    return ErrorResponse(
        code=ErrorCode.INTERNAL_ERROR,
        message="予期しないエラーが発生しました",
        details={"original_error": str(error)},
    )
