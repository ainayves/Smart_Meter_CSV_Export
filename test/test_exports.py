import os
import time
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from ..app.main import app
from app.settings import EXPORT_DIR

client = TestClient(app)


def test_happy_path_export_and_download():
    start = datetime.now(timezone.utc) - timedelta(hours=2)
    end = start + timedelta(minutes=10)

    payload = {
        "smart_meter_id": "SM-001",
        "start_datetime": start.isoformat().replace("+00:00", "Z"),
        "end_datetime": end.isoformat().replace("+00:00", "Z"),
        "format": "csv",
    }

    # Create job
    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    # Poll status until completed or timeout
    for _ in range(60):
        s = client.get(f"/api/export/status/{job_id}")
        assert s.status_code == 200
        data = s.json()
        if data.get("status") == "completed":
            break
        time.sleep(0.2)
    else:
        pytest.fail("Job did not complete in time")

    # Download file
    d = client.get(f"/api/export/download/{job_id}")
    assert d.status_code == 200
    assert d.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in d.headers["content-disposition"]
    assert len(d.content) > 0


def test_invalid_meter_id():
    start = datetime.now(timezone.utc) - timedelta(hours=1)
    end = start + timedelta(minutes=5)

    payload = {
        "smart_meter_id": "SM-XXX",
        "start_datetime": start.isoformat().replace("+00:00", "Z"),
        "end_datetime": end.isoformat().replace("+00:00", "Z"),
        "format": "csv",
    }

    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert detail["code"] == "SMART_METER_NOT_FOUND"


def test_invalid_date_ranges():
    now = datetime.now(timezone.utc)
    # End before start
    payload = {
        "smart_meter_id": "SM-001",
        "start_datetime": (now - timedelta(minutes=5))
        .isoformat()
        .replace("+00:00", "Z"),
        "end_datetime": (now - timedelta(minutes=10))
        .isoformat()
        .replace("+00:00", "Z"),
        "format": "csv",
    }
    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 400

    # Start in the future
    payload = {
        "smart_meter_id": "SM-001",
        "start_datetime": (now + timedelta(minutes=5))
        .isoformat()
        .replace("+00:00", "Z"),
        "end_datetime": (now + timedelta(minutes=10))
        .isoformat()
        .replace("+00:00", "Z"),
        "format": "csv",
    }
    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 400

    # Too small range (< 1 minute)
    payload = {
        "smart_meter_id": "SM-001",
        "start_datetime": (now - timedelta(minutes=5))
        .isoformat()
        .replace("+00:00", "Z"),
        "end_datetime": (now - timedelta(minutes=5, seconds=30))
        .isoformat()
        .replace("+00:00", "Z"),
        "format": "csv",
    }
    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 400


def test_concurrent_requests():
    now = datetime.now(timezone.utc)
    jobs = []
    for i in range(5):
        payload = {
            "smart_meter_id": "SM-002",
            "start_datetime": (now - timedelta(minutes=60 + i))
            .isoformat()
            .replace("+00:00", "Z"),
            "end_datetime": (now - timedelta(minutes=30 + i))
            .isoformat()
            .replace("+00:00", "Z"),
            "format": "csv",
        }
        r = client.post("/api/export/csv", json=payload)
        assert r.status_code == 202
        jobs.append(r.json()["job_id"])

        # Wait for all to finish
    for jid in jobs:
        for _ in range(60):
            s = client.get(f"/api/export/status/{jid}")
            assert s.status_code == 200
            if s.json().get("status") == "completed":
                break
            time.sleep(0.2)
        else:
            pytest.fail(f"Job {jid} did not complete in time")


def test_not_found_status_and_download():
    s = client.get("/api/export/status/00000000-0000-0000-0000-000000000000")
    assert s.status_code == 200
    assert s.json()["status"] == "not_found"

    d = client.get("/api/export/download/00000000-0000-0000-0000-000000000000")
    assert d.status_code == 404
