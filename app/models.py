from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, Integer, BigInteger, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from .database import Base


class Job(Base):
    """
    Table des jobs d'export.
    IMPORTANT: 'id' est la clé primaire, sinon SQLAlchemy ne peut pas mapper.
    """

    __tablename__ = "jobs"

    # Clé primaire UUID (stockée en TEXT/STRING pour compatibilité SQLite)
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    smart_meter_id: Mapped[str] = mapped_column(String, nullable=False)

    # Stockées en timezone-aware; SQLite les sérialise en texte
    start_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")

    # Timestamps gérés côté DB (CURRENT_TIMESTAMP) + onupdate pour updated_at
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )

    file_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    record_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Utilitaire pour mettre à jour updated_at côté application si besoin
    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def __repr__(self) -> str:  # pratique pour les logs
        return (
            f"Job(id={self.id!r}, meter={self.smart_meter_id!r}, "
            f"status={self.status!r})"
        )
