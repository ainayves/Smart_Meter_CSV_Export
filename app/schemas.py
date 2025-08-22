# app/schemas.py
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class ExportRequest(BaseModel):
    smart_meter_id: str = Field(..., examples=["SM-001"])
    start_datetime: datetime = Field(..., examples=["2024-01-01T00:00:00Z"])
    end_datetime: datetime = Field(..., examples=["2024-01-01T00:02:00Z"])
    format: Literal["csv"] = Field("csv", description="Only 'csv' is supported for now")

    model_config = {
        "json_schema_extra": {
            "example": {
                "smart_meter_id": "SM-001",
                "start_datetime": "2024-01-01T00:00:00Z",
                "end_datetime": "2024-01-01T00:02:00Z",
                "format": "csv",
            }
        }
    }


class ExportPeriod(BaseModel):
    start: datetime
    end: datetime


class FileInfo(BaseModel):
    filename: str
    download_url: str
    file_size_bytes: int
    record_count: int
    export_period: ExportPeriod


class JobStatusPending(BaseModel):
    job_id: str
    status: Literal["pending", "processing"] = "pending"
    message: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "job_id": "4f2c3a3a-2a9c-4a7c-8a3e-2c4f1b59b1e1",
                "status": "pending",
                "message": "Job is being processed",
                "created_at": "2024-01-01T10:00:00Z",
                "updated_at": "2024-01-01T10:00:00Z",
            }
        }
    }


class JobStatusCompleted(BaseModel):
    job_id: str
    status: Literal["completed"] = "completed"
    message: str
    created_at: datetime
    updated_at: datetime
    file_info: FileInfo

    model_config = {
        "json_schema_extra": {
            "example": {
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
            }
        }
    }


class JobStatusFailed(BaseModel):
    job_id: str
    status: Literal["failed"] = "failed"
    message: str
    created_at: datetime
    updated_at: datetime
    error: dict

    model_config = {
        "json_schema_extra": {
            "example": {
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
            }
        }
    }


class NotFoundResponse(BaseModel):
    status: Literal["not_found"]
    message: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "not_found",
                "message": "Job with ID '00000000-0000-0000-0000-000000000000' not found",
            }
        }
    }
