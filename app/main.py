from datetime import timezone
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import uuid
from .database import Base, engine, get_db
from .models import Job
from .schemas import (
    ExportRequest,
    JobStatusPending,
    JobStatusCompleted,
    JobStatusFailed,
    NotFoundResponse,
    FileInfo,
    ExportPeriod,
)
from .services import processor, process_job, _filename_for
from .utils import ValidationError, validate_request
import uvicorn
from .settings import EXPORT_DIR, APP_HOST, APP_PORT, PUBLIC_BASE_URL

app = FastAPI(title="Smart Meter CSV Export API")


# Create tables on startup
Base.metadata.create_all(bind=engine)


@app.post("/api/export/csv", response_model=JobStatusPending, status_code=202)
def create_export_job(payload: ExportRequest, db: Session = Depends(get_db)):
    try:
        start, end = validate_request(
            payload.smart_meter_id, payload.start_datetime, payload.end_datetime
        )
    except ValidationError as ve:
        raise HTTPException(
            status_code=400,
            detail={"code": ve.code, "message": str(ve), "details": ve.details or ""},
        )

    job = Job(
        id=str(uuid.uuid4()),
        smart_meter_id=payload.smart_meter_id,
        start_datetime=start,
        end_datetime=end,
        status="pending",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch background task
    processor.submit(process_job, job.id, lambda: next(get_db()))

    return JobStatusPending(
        job_id=job.id,
        status=job.status,
        message="Export job created successfully",
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@app.get(
    "/api/export/status/{job_id}",
    response_model=JobStatusPending
    | JobStatusCompleted
    | JobStatusFailed
    | NotFoundResponse,
)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job: Job | None = db.query(Job).get(job_id)
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
    elif job.status == "failed":
        # Parse structured error if available
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
    else:
        return JobStatusPending(
            job_id=job.id,
            status="pending" if job.status == "pending" else job.status,
            message="Job is being processed",
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


@app.get("/api/export/download/{job_id}")
def download_export(job_id: str, db: Session = Depends(get_db)):
    job: Job | None = db.query(Job).get(job_id)
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
    return FileResponse(
        path=job.file_path,
        media_type="text/csv",
        filename=filename,
    )


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=APP_HOST, port=APP_PORT, reload=True)
