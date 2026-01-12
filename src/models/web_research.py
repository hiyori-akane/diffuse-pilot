"""
Webリサーチ関連モデル

WebResearchCache
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.connection import Base


class WebResearchCache(Base):
    """Webリサーチ結果のキャッシュ"""

    __tablename__ = "web_research_cache"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    query_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True, unique=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    results: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
