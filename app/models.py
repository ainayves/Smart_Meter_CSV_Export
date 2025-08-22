# app/models.py (extrait)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, DateTime, Integer, BigInteger, Text
from sqlalchemy.sql import func
from .database import Base
from datetime import datetime, timezone


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = {"extend_existing": True}

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    smart_meter_id: Mapped[str] = mapped_column(String, nullable=False)
    start_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    end_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.current_timestamp(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
        nullable=False,
    )
    file_path: Mapped[str | None] = mapped_column(String)
    error_message: Mapped[str | None] = mapped_column(Text)
    record_count: Mapped[int | None] = mapped_column(Integer)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger)

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
