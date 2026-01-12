"""Unit tests for error handler"""
import pytest

from src.services.error_handler import (
    ApplicationError,
    DiscordAPIError,
    ErrorCode,
    ErrorResponse,
    LLMAPIError,
    StableDiffusionAPIError,
    handle_error,
)


def test_error_response_creation():
    """ErrorResponse の作成テスト"""
    error = ErrorResponse(
        code=ErrorCode.INTERNAL_ERROR,
        message="Test error",
        details={"key": "value"},
    )

    assert error.code == ErrorCode.INTERNAL_ERROR
    assert error.message == "Test error"
    assert error.details == {"key": "value"}


def test_application_error():
    """ApplicationError のテスト"""
    error = ApplicationError(
        code=ErrorCode.VALIDATION_ERROR,
        message="Validation failed",
        details={"field": "test"},
    )

    assert error.code == ErrorCode.VALIDATION_ERROR
    assert error.message == "Validation failed"

    response = error.to_response()
    assert isinstance(response, ErrorResponse)
    assert response.code == ErrorCode.VALIDATION_ERROR


def test_discord_api_error():
    """DiscordAPIError のテスト"""
    error = DiscordAPIError("Discord failed", details={"status": 500})

    assert error.code == ErrorCode.DISCORD_API_ERROR
    assert error.message == "Discord failed"
    assert error.details["status"] == 500


def test_llm_api_error():
    """LLMAPIError のテスト"""
    error = LLMAPIError("LLM failed")

    assert error.code == ErrorCode.LLM_API_ERROR
    assert error.message == "LLM failed"


def test_sd_api_error():
    """StableDiffusionAPIError のテスト"""
    error = StableDiffusionAPIError("SD failed")

    assert error.code == ErrorCode.SD_API_ERROR
    assert error.message == "SD failed"


def test_handle_error_with_application_error():
    """handle_error で ApplicationError を処理"""
    original_error = DiscordAPIError("Test error")

    response = handle_error(original_error)

    assert isinstance(response, ErrorResponse)
    assert response.code == ErrorCode.DISCORD_API_ERROR


def test_handle_error_with_generic_exception():
    """handle_error で一般的な Exception を処理"""
    original_error = ValueError("Generic error")

    response = handle_error(original_error)

    assert isinstance(response, ErrorResponse)
    assert response.code == ErrorCode.INTERNAL_ERROR
    assert "予期しないエラー" in response.message
