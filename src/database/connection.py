"""
データベース接続モジュール

SQLAlchemy async engine を提供します。
"""

from typing import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config.logging import get_logger
from src.config.settings import get_settings

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy ベースクラス"""

    pass


# グローバル変数
_engine = None
_async_session_maker = None


def get_engine():
    """データベースエンジンを取得"""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            echo=settings.environment == "development",
            future=True,
        )

        # SQLite の外部キー制約を有効化
        @event.listens_for(_engine.sync_engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        logger.info(f"Database engine created: {settings.database_url}")

    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """セッションメーカーを取得"""
    global _async_session_maker
    if _async_session_maker is None:
        engine = get_engine()
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Session maker created")

    return _async_session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """データベースセッションを取得（依存性注入用）

    Yields:
        AsyncSession: データベースセッション
    """
    session_maker = get_session_maker()
    async with session_maker() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            logger.error(f"Session error: {e}")
            raise
        finally:
            await session.close()


async def init_db():
    """データベースを初期化（テーブル作成）"""
    engine = get_engine()
    async with engine.begin() as conn:
        # すべてのモデルをインポート
        from src.models import generation, lora, settings  # noqa: F401

        # テーブル作成
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database initialized")


async def close_db():
    """データベース接続を閉じる"""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        logger.info("Database connection closed")
        _engine = None
