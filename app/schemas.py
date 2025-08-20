from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional, Literal


class ExportRequest(BaseModel):
    smart_meter_id: str = Field(..., description="Smart meter ID")
    start_datetime: datetime = Field(..., description="Start datetime (UTC ISO 8601)")
    end_datetime: datetime = Field(..., description="End datetime (UTC ISO 8601)")
    format: Literal["csv"] = "csv"


class JobStatusBase(BaseModel):
    job_id: str
    status: str
    message: str
    created_at: datetime
    updated_at: datetime


class ExportPeriod(BaseModel):
    start: datetime
    end: datetime


class FileInfo(BaseModel):
    filename: str
    download_url: str
    file_size_bytes: int
    record_count: int
    export_period: ExportPeriod


class JobStatusPending(JobStatusBase):
    pass


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: str


class JobStatusCompleted(JobStatusBase):
    file_info: FileInfo


class JobStatusFailed(JobStatusBase):
    error: ErrorInfo


class NotFoundResponse(BaseModel):
    status: str
    message: str
