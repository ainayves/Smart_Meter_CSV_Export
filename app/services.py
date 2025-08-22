from __future__ import annotations

import csv, os
from datetime import timezone
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from .models import Job
from .settings import EXPORT_DIR, DATA_SOURCE, JSON_FILE
from .data_provider import get_provider
from .utils import ValidationError, validate_dates_only, json_known_meters

from concurrent.futures import ThreadPoolExecutor
from .settings import MAX_WORKERS


class JobProcessor:
    def __init__(self, max_workers: int = MAX_WORKERS):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def submit(self, fn, *args, **kwargs):
        return self._executor.submit(fn, *args, **kwargs)


processor = JobProcessor()


def _filename_for(job: Job) -> str:
    start_str = job.start_datetime.strftime("%Y%m%dT%H%M%SZ")
    end_str = job.end_datetime.strftime("%Y%m%dT%H%M%SZ")
    return f"smart_meter_{job.smart_meter_id}_{start_str}_{end_str}.csv"


def _fail_job(db: Session, job: Job, code: str, message: str, details: str = ""):
    job.status = "failed"
    job.error_message = f"{code}:{message}::{details}"
    job.touch()
    db.commit()


def process_job(job_id: str, db_factory: Callable[[], Session]):
    db = db_factory()
    try:
        job: Job | None = db.query(Job).get(job_id)
        if not job:
            return
        job.status = "processing"
        job.touch()
        db.commit()

        # Sécurité: revalider UNIQUEMENT les dates (mêmes règles que l'endpoint)
        try:
            start, end = validate_dates_only(job.start_datetime, job.end_datetime)
        except ValidationError as ve:
            _fail_job(db, job, ve.code, str(ve))
            return

        # Vérifs spécifiques à la source (non bloquantes pour l'endpoint)
        if DATA_SOURCE == "json":
            ids = json_known_meters()
            if not ids:
                _fail_job(
                    db,
                    job,
                    "SMART_DATA_SOURCE_EMPTY",
                    "JSON data source is empty or unreadable",
                    f"JSON_FILE={JSON_FILE!r}",
                )
                return
            if job.smart_meter_id not in ids:
                _fail_job(
                    db,
                    job,
                    "SMART_METER_NOT_FOUND",
                    f"Smart meter '{job.smart_meter_id}' not found in JSON",
                    f"Available IDs: {sorted(ids)}",
                )
                return

        provider = get_provider()
        filename = _filename_for(job)
        filepath = Path(EXPORT_DIR) / filename
        record_count = 0

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "timestamp",
                    "smart_meter_id",
                    "energy_kwh",
                    "power_kw",
                    "voltage_v",
                    "current_a",
                ]
            )
            for ts, smid, e, p, v, c in provider.iter_readings(
                job.smart_meter_id, start, end
            ):
                writer.writerow(
                    [
                        ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                        smid,
                        e,
                        p,
                        v,
                        c,
                    ]
                )
                record_count += 1

        job.file_path = str(filepath)
        job.record_count = record_count
        job.file_size_bytes = os.path.getsize(filepath)
        job.status = "completed"
        job.touch()
        db.commit()

    except Exception as ex:
        # Toutes autres erreurs non prévues: stockées et visibles via /status
        job = db.query(Job).get(job_id)
        if job:
            _fail_job(db, job, "UNEXPECTED_ERROR", str(ex))
    finally:
        db.close()
