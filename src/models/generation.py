"""
画像生成関連モデル

GenerationRequest, GenerationMetadata, GeneratedImage
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.connection import Base


class RequestStatus(str, Enum):
    """リクエストステータス"""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class GenerationRequest(Base):
    """画像生成リクエスト"""

    __tablename__ = "generation_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    original_instruction: Mapped[str] = mapped_column(Text, nullable=False)
    web_research: Mapped[bool] = mapped_column(nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=RequestStatus.PENDING)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # リレーション
    generation_metadata: Mapped[Optional["GenerationMetadata"]] = relationship(
        "GenerationMetadata", back_populates="request", uselist=False, cascade="all, delete-orphan"
    )
    images: Mapped[list["GeneratedImage"]] = relationship(
        "GeneratedImage", back_populates="request", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GenerationRequest(id={self.id}, status={self.status})>"


class GenerationMetadata(Base):
    """画像生成メタデータ"""

    __tablename__ = "generation_metadata"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generation_requests.id"), nullable=False
    )

    # プロンプト
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # モデル・LoRA
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    lora_list: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # パラメータ
    steps: Mapped[int] = mapped_column(Integer, nullable=False)
    cfg_scale: Mapped[float] = mapped_column(Float, nullable=False)
    sampler: Mapped[str] = mapped_column(String(100), nullable=False)
    scheduler: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)

    # その他のパラメータ
    raw_params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    # リレーション
    request: Mapped["GenerationRequest"] = relationship(
        "GenerationRequest", back_populates="generation_metadata"
    )
    images: Mapped[list["GeneratedImage"]] = relationship(
        "GeneratedImage", back_populates="generation_metadata"
    )

    def __repr__(self) -> str:
        return f"<GenerationMetadata(id={self.id}, model={self.model_name})>"


class GeneratedImage(Base):
    """生成された画像"""

    __tablename__ = "generated_images"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generation_requests.id"), nullable=False
    )
    metadata_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("generation_metadata.id"), nullable=False
    )

    file_path: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    discord_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)

    # リレーション
    request: Mapped["GenerationRequest"] = relationship(
        "GenerationRequest", back_populates="images"
    )
    generation_metadata: Mapped["GenerationMetadata"] = relationship(
        "GenerationMetadata", back_populates="images"
    )

    def __repr__(self) -> str:
        return f"<GeneratedImage(id={self.id}, file={self.file_path})>"
