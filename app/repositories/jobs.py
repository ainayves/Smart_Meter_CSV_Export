# app/repositories/jobs.py
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from ..models import Job


class JobRepository:
    """DB access for the Job entity (CRUD + status helpers)."""

    def __init__(self, db: Session):
        self.db = db

    # --- Read ---
    def get(self, job_id: str) -> Optional[Job]:
        return self.db.get(Job, job_id)

    # --- Create ---
    def create(
        self,
        *,
        smart_meter_id: str,
        start_datetime,
        end_datetime,
        status: str = "pending",
        job_id: Optional[str] = None,
    ) -> Job:
        job = Job(
            id=job_id or str(uuid.uuid4()),
            smart_meter_id=smart_meter_id,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            status=status,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    # --- Update status helpers ---
    def mark_processing(self, job: Job) -> Job:
        job.status = "processing"
        job.touch()
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_completed(
        self,
        job: Job,
        *,
        file_path: Path,
        record_count: int,
        file_size_bytes: int,
    ) -> Job:
        job.file_path = str(file_path)
        job.record_count = record_count
        job.file_size_bytes = file_size_bytes
        job.status = "completed"
        job.touch()
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_failed(
        self, job: Job, *, code: str, message: str, details: str = ""
    ) -> Job:
        job.status = "failed"
        job.error_message = (
            f"{code}:{message}::{details}" if details else f"{code}:{message}"
        )
        job.touch()
        self.db.commit()
        self.db.refresh(job)
        return job
