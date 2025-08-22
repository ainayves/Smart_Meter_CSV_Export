# app/routes/export.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
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
from ..settings import EXPORT_DIR
from ..services import processor, process_job, _filename_for
from ..utils import ValidationError, validate_dates_only
from ..repositories.jobs import JobRepository

router = APIRouter(prefix="/api/export", tags=["export"])


def get_job_repository(db: Session = Depends(get_db)) -> JobRepository:
    return JobRepository(db)


@router.post("/csv", response_model=JobStatusPending, status_code=202)
def create_export_job(
    payload: ExportRequest,
    repo: JobRepository = Depends(get_job_repository),
):
    """
    Validation endpoint limitée aux dates :
    - requis: start/end
    - start dans le passé, end après start
    - min 1 minute, max 1 an
    Toute autre erreur sera traitée en tâche de fond et visible via /status.
    """
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

    # Lance le traitement en arrière-plan (le worker écrira le résultat/erreur dans la DB)
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
)
def get_job_status(
    job_id: str,
    repo: JobRepository = Depends(get_job_repository),
):
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
        # Parse du champ error_message pour renvoyer la structure demandée
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

    # pending / processing
    return JobStatusPending(
        job_id=job.id,
        status=job.status,
        message="Job is being processed",
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/download/{job_id}")
def download_export(
    job_id: str,
    repo: JobRepository = Depends(get_job_repository),
):
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
