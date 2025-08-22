# app/routes/export.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    ExportRequest,
    JobStatusPending,
    JobStatusCompleted,
    JobStatusFailed,
    NotFoundResponse,
    FileInfo,
    ExportPeriod,
)
from ..services import processor, process_job, _filename_for
from ..utils import ValidationError, validate_dates_only
from ..repositories.jobs import JobRepository

router = APIRouter(prefix="/api/export", tags=["export"])


def get_job_repository(db: Session = Depends(get_db)) -> JobRepository:
    return JobRepository(db)


@router.post(
    "/csv",
    response_model=JobStatusPending,
    status_code=202,
    summary="Create a CSV export job",
    description=(
        "Accepts a smart meter export request and enqueues an asynchronous job. "
        "Only date range validation happens here; all other errors are recorded on the job and exposed via `/status/{job_id}`."
    ),
    responses={
        202: {
            "description": "Export job created",
            "content": {
                "application/json": {
                    "example": {
                        "job_id": "4f2c3a3a-2a9c-4a7c-8a3e-2c4f1b59b1e1",
                        "status": "pending",
                        "message": "Export job created successfully",
                        "created_at": "2024-01-01T10:00:00Z",
                        "updated_at": "2024-01-01T10:00:00Z",
                    }
                }
            },
        },
        400: {
            "description": "Invalid date range",
            "content": {
                "application/json": {
                    "example": {
                        "detail": {
                            "code": "INVALID_DATE_RANGE",
                            "message": "end_datetime must be after start_datetime",
                            "details": "",
                        }
                    }
                }
            },
        },
    },
)
def create_export_job(
    payload: ExportRequest = Body(
        ...,
        examples={
            "basic": {
                "summary": "Minimal CSV request",
                "value": {
                    "smart_meter_id": "SM-001",
                    "start_datetime": "2024-01-01T00:00:00Z",
                    "end_datetime": "2024-01-01T00:02:00Z",
                    "format": "csv",
                },
            }
        },
    ),
    repo: JobRepository = Depends(get_job_repository),
):
    try:
        start, end = validate_dates_only(payload.start_datetime, payload.end_datetime)
    except ValidationError as ve:
        raise HTTPException(
            status_code=400,
            detail={"code": ve.code, "message": str(ve), "details": ve.details or ""},
        )

    job = repo.create(
        smart_meter_id=payload.smart_meter_id,
        start_datetime=start,
        end_datetime=end,
        status="pending",
    )

    processor.submit(process_job, job.id, lambda: next(get_db()))

    return JobStatusPending(
        job_id=job.id,
        status=job.status,
        message="Export job created successfully",
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get(
    "/status/{job_id}",
    response_model=JobStatusPending
    | JobStatusCompleted
    | JobStatusFailed
    | NotFoundResponse,
    summary="Get export job status",
    description=(
        "Returns the current status of a job. Pending/processing jobs show timestamps only; "
        "completed jobs include download info; failed jobs include a structured error."
    ),
    responses={
        200: {
            "description": "Job status (one of pending/completed/failed)",
            "content": {
                "application/json": {
                    "examples": {
                        "pending": {
                            "summary": "Pending",
                            "value": {
                                "job_id": "4f2c3a3a-2a9c-4a7c-8a3e-2c4f1b59b1e1",
                                "status": "pending",
                                "message": "Job is being processed",
                                "created_at": "2024-01-01T10:00:00Z",
                                "updated_at": "2024-01-01T10:00:00Z",
                            },
                        },
                        "completed": {
                            "summary": "Completed",
                            "value": {
                                "job_id": "4f2c3a3a-2a9c-4a7c-8a3e-2c4f1b59b1e1",
                                "status": "completed",
                                "message": "Export completed successfully",
                                "created_at": "2024-01-01T10:00:00Z",
                                "updated_at": "2024-01-01T10:05:30Z",
                                "file_info": {
                                    "filename": "smart_meter_SM-001_20240101T000000Z_20240101T000200Z.csv",
                                    "download_url": "/api/export/download/4f2c3a3a-2a9c-4a7c-8a3e-2c4f1b59b1e1",
                                    "file_size_bytes": 1024,
                                    "record_count": 2,
                                    "export_period": {
                                        "start": "2024-01-01T00:00:00Z",
                                        "end": "2024-01-01T00:02:00Z",
                                    },
                                },
                            },
                        },
                        "failed": {
                            "summary": "Failed",
                            "value": {
                                "job_id": "4f2c3a3a-2a9c-4a7c-8a3e-2c4f1b59b1e1",
                                "status": "failed",
                                "message": "Export failed",
                                "created_at": "2024-01-01T10:00:00Z",
                                "updated_at": "2024-01-01T10:01:15Z",
                                "error": {
                                    "code": "SMART_METER_NOT_FOUND",
                                    "message": "Smart meter with ID 'SM-999' not found",
                                    "details": "The specified smart meter does not exist in the system",
                                },
                            },
                        },
                        "not_found": {
                            "summary": "Not found",
                            "value": {
                                "status": "not_found",
                                "message": "Job with ID '00000000-0000-0000-0000-000000000000' not found",
                            },
                        },
                    }
                }
            },
        }
    },
)
def get_job_status(job_id: str, repo: JobRepository = Depends(get_job_repository)):
    job = repo.get(job_id)
    if not job:
        return NotFoundResponse(
            status="not_found", message=f"Job with ID '{job_id}' not found"
        )

    if job.status == "completed":
        filename = _filename_for(job)
        return JobStatusCompleted(
            job_id=job.id,
            status=job.status,
            message="Export completed successfully",
            created_at=job.created_at,
            updated_at=job.updated_at,
            file_info=FileInfo(
                filename=filename,
                download_url=f"/api/export/download/{job.id}",
                file_size_bytes=job.file_size_bytes or 0,
                record_count=job.record_count or 0,
                export_period=ExportPeriod(
                    start=job.start_datetime, end=job.end_datetime
                ),
            ),
        )

    if job.status == "failed":
        code = "UNKNOWN"
        message = job.error_message or "Export failed"
        details = ""
        if job.error_message and ":" in job.error_message:
            try:
                code, rest = job.error_message.split(":", 1)
                if "::" in rest:
                    msg, details = rest.split("::", 1)
                    message = msg
                else:
                    message = rest
            except Exception:
                pass

        return JobStatusFailed(
            job_id=job.id,
            status=job.status,
            message="Export failed",
            created_at=job.created_at,
            updated_at=job.updated_at,
            error={"code": code, "message": message, "details": details},
        )

    return JobStatusPending(
        job_id=job.id,
        status=job.status,
        message="Job is being processed",
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get(
    "/download/{job_id}",
    summary="Download the generated CSV",
    description="Returns the CSV file for a completed job.",
    responses={
        200: {
            "description": "CSV file",
            "content": {
                "text/csv": {
                    "schema": {"type": "string", "format": "binary"},
                    "examples": {
                        "tiny": {
                            "summary": "2-row CSV preview",
                            "value": (
                                "timestamp,smart_meter_id,energy_kwh,power_kw,voltage_v,current_a\n"
                                "2024-01-01T00:00:00Z,SM-001,0.50,2.10,230.10,9.13\n"
                                "2024-01-01T00:01:00Z,SM-001,0.52,2.15,230.15,9.34\n"
                            ),
                        }
                    },
                }
            },
        },
        400: {
            "description": "File not ready",
            "content": {
                "application/json": {
                    "example": {
                        "status": "pending",
                        "message": "File not ready for download",
                    }
                }
            },
        },
        404: {
            "description": "Job not found",
            "content": {
                "application/json": {
                    "example": {
                        "status": "not_found",
                        "message": "Job with ID '...' not found",
                    }
                }
            },
        },
    },
)
def download_export(job_id: str, repo: JobRepository = Depends(get_job_repository)):
    job = repo.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "not_found",
                "message": f"Job with ID '{job_id}' not found",
            },
        )
    if job.status != "completed" or not job.file_path:
        raise HTTPException(
            status_code=400,
            detail={"status": job.status, "message": "File not ready for download"},
        )

    filename = _filename_for(job)
    return FileResponse(path=job.file_path, media_type="text/csv", filename=filename)
