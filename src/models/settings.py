"""
設定関連モデル

GlobalSettings, ThreadContext
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.connection import Base


class GlobalSettings(Base):
    """グローバル設定"""

    __tablename__ = "global_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)

    # デフォルト設定
    default_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_lora_list: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    default_prompt_suffix: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_sd_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 一般設定
    seed: Mapped[int | None] = mapped_column(nullable=True)
    batch_size: Mapped[int | None] = mapped_column(nullable=True)
    batch_count: Mapped[int | None] = mapped_column(nullable=True)

    # Hires. fix 設定
    hires_upscaler: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hires_steps: Mapped[int | None] = mapped_column(nullable=True)
    denoising_strength: Mapped[float | None] = mapped_column(nullable=True)
    upscale_by: Mapped[float | None] = mapped_column(nullable=True)

    # Refiner 設定
    refiner_checkpoint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    refiner_switch_at: Mapped[float | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<GlobalSettings(id={self.id}, guild={self.guild_id}, user={self.user_id})>"


class ThreadContext(Base):
    """スレッドコンテキスト"""

    __tablename__ = "thread_contexts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    guild_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    user_id: Mapped[str] = mapped_column(String(32), nullable=False)

    # 生成履歴
    generation_history: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latest_metadata_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("generation_metadata.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # リレーション
    latest_metadata: Mapped[Optional["GenerationMetadata"]] = relationship(
        "GenerationMetadata", foreign_keys=[latest_metadata_id]
    )

    def __repr__(self) -> str:
        return f"<ThreadContext(id={self.id}, thread={self.thread_id})>"
