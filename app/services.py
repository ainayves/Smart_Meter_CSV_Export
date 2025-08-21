from __future__ import annotations
import csv, os
from datetime import timezone
from pathlib import Path
from typing import Callable
from sqlalchemy.orm import Session
from concurrent.futures import ThreadPoolExecutor
from .models import Job
from .settings import EXPORT_DIR, MAX_WORKERS
from .utils import ValidationError, validate_request
from .data_provider import get_provider  # <-- on lit via provider (JSON)


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

        # Valide la période + existence du compteur selon la source (JSON)
        start, end = validate_request(
            job.smart_meter_id, job.start_datetime, job.end_datetime
        )

        provider = get_provider()  # <- DATA_SOURCE=json => JSONProvider
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

            # <-- lit uniquement ce qui est présent dans le JSON
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
