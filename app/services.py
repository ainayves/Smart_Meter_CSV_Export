import csv
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from sqlalchemy.orm import Session
from .models import Job
from .settings import EXPORT_DIR, MAX_WORKERS
from .utils import ValidationError, validate_request, generate_smart_meter_data


class JobProcessor:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    def submit(self, fn: Callable, *args, **kwargs):
        return self._executor.submit(fn, *args, **kwargs)


processor = JobProcessor()


def _filename_for(job: Job) -> str:
    start_str = job.start_datetime.strftime("%Y%m%dT%H%M%SZ")
    end_str = job.end_datetime.strftime("%Y%m%dT%H%M%SZ")
    return f"smart_meter_{job.smart_meter_id}_{start_str}_{end_str}.csv"


def process_job(job_id: str, db_factory: Callable[[], Session]):
    db = db_factory()
    try:
        job: Job | None = db.query(Job).get(job_id)
        if not job:
            return
        job.status = "processing"
        job.touch()
        db.commit()

        # Validate again & generate data
        start, end = validate_request(
            job.smart_meter_id, job.start_datetime, job.end_datetime
        )

        # Write CSV
        filename = _filename_for(job)
        filepath = EXPORT_DIR / filename
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
            for ts, smid, e, p, v, c in generate_smart_meter_data(
                job.smart_meter_id, start, end
            ):
                writer.writerow(
                    [
                        ts.replace(tzinfo=timezone.utc)
                        .isoformat()
                        .replace("+00:00", "Z"),
                        smid,
                        e,
                        p,
                        v,
                        c,
                    ]
                )
                record_count += 1

        file_size_bytes = os.path.getsize(filepath)
        job.file_path = str(filepath)
        job.record_count = record_count
        job.file_size_bytes = file_size_bytes
        job.status = "completed"
        job.touch()
        db.commit()

    except ValidationError as ve:
        job = db.query(Job).get(job_id)
        if job:
            job.status = "failed"
            job.error_message = f"{ve.code}:{ve}::{ve.details}"
            job.touch()
            db.commit()
    except Exception as ex:
        job = db.query(Job).get(job_id)
        if job:
            job.status = "failed"
            job.error_message = f"UNEXPECTED_ERROR:{ex}"
            job.touch()
            db.commit()
    finally:
        db.close()
