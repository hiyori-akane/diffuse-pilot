"""
LoRA関連モデル

LoRAMetadata
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.database.connection import Base


class LoRAMetadata(Base):
    """LoRA メタデータ"""

    __tablename__ = "lora_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)

    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    downloaded_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<LoRAMetadata(id={self.id}, name={self.name})>"
