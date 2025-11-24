"""Test configuration"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.database.connection import Base
# Import all models to ensure they are registered
from src.models.generation import GeneratedImage, GenerationMetadata, GenerationRequest
from src.models.settings import GlobalSettings, ThreadContext


@pytest.fixture
async def test_db():
    """テスト用データベースセッション"""
    # インメモリ SQLite
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    await engine.dispose()
