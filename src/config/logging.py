"""
ログ設定モジュール

構造化ログを提供します。
"""

import logging
import sys
from typing import Any

from src.config.settings import get_settings


class StructuredFormatter(logging.Formatter):
    """構造化ログフォーマッター"""

    def format(self, record: logging.LogRecord) -> str:
        """ログレコードをフォーマット"""
        # 基本情報
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 追加情報
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        if hasattr(record, "guild_id"):
            log_data["guild_id"] = record.guild_id

        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id

        # エラー情報
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # フォーマット
        parts = [f"{k}={v}" for k, v in log_data.items()]
        return " | ".join(parts)


def setup_logging() -> None:
    """ログ設定を初期化"""
    settings = get_settings()

    # ログレベル設定
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # ハンドラー設定
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    # フォーマッター設定
    formatter = StructuredFormatter(datefmt="%Y-%m-%d %H:%M:%S")
    handler.setFormatter(formatter)

    # ハンドラー追加
    root_logger.addHandler(handler)

    # サードパーティライブラリのログレベル調整
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """ロガーを取得

    Args:
        name: ロガー名

    Returns:
        ロガーインスタンス
    """
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """コンテキスト情報を追加するロガーアダプター"""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        """ログメッセージを処理"""
        # extra に含まれる情報を LogRecord に追加
        if "extra" not in kwargs:
            kwargs["extra"] = {}

        kwargs["extra"].update(self.extra)
        return msg, kwargs


def get_logger_with_context(name: str, **context: Any) -> LoggerAdapter:
    """コンテキスト付きロガーを取得

    Args:
        name: ロガー名
        **context: コンテキスト情報（request_id, guild_id, user_id など）

    Returns:
        ロガーアダプター
    """
    logger = get_logger(name)
    return LoggerAdapter(logger, context)
