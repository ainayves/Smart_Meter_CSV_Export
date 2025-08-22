import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, BigInteger, Text
from sqlalchemy.dialects.sqlite import BLOB
from sqlalchemy.sql import func
from .database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    smart_meter_id = Column(String, nullable=False)
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True), nullable=False)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(
        DateTime(timezone=True), server_default=func.current_timestamp()
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )
    file_path = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    record_count = Column(Integer, nullable=True)
    file_size_bytes = Column(BigInteger, nullable=True)

    # Convenience updater for timestamps
    def touch(self):
        self.updated_at = datetime.utcnow()
