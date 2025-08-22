import os
import json
import time
import importlib
from pathlib import Path
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient


# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture()
def sample_items() -> Dict[str, Any]:
    # Données fixes (exactement celles de l'exemple fourni)
    return {
        "items": [
            {
                "timestamp": "2024-01-01T00:00:00Z",
                "smart_meter_id": "SM-001",
                "energy_kwh": 0.50,
                "power_kw": 2.10,
                "voltage_v": 230.10,
                "current_a": 9.13,
            },
            {
                "timestamp": "2024-01-01T00:01:00Z",
                "smart_meter_id": "SM-001",
                "energy_kwh": 0.52,
                "power_kw": 2.15,
                "voltage_v": 230.15,
                "current_a": 9.34,
            },
            {
                "timestamp": "2024-01-01T00:02:00Z",
                "smart_meter_id": "SM-001",
                "energy_kwh": 0.54,
                "power_kw": 2.20,
                "voltage_v": 230.20,
                "current_a": 9.56,
            },
            {
                "timestamp": "2024-01-01T00:03:00Z",
                "smart_meter_id": "SM-002",
                "energy_kwh": 0.56,
                "power_kw": 2.25,
                "voltage_v": 230.25,
                "current_a": 9.77,
            },
            {
                "timestamp": "2024-01-01T00:04:00Z",
                "smart_meter_id": "SM-002",
                "energy_kwh": 0.58,
                "power_kw": 2.30,
                "voltage_v": 230.30,
                "current_a": 9.99,
            },
            {
                "timestamp": "2024-01-01T00:05:00Z",
                "smart_meter_id": "SM-002",
                "energy_kwh": 0.60,
                "power_kw": 2.35,
                "voltage_v": 230.35,
                "current_a": 10.20,
            },
            {
                "timestamp": "2024-01-01T00:06:00Z",
                "smart_meter_id": "SM-003",
                "energy_kwh": 0.62,
                "power_kw": 2.40,
                "voltage_v": 230.40,
                "current_a": 10.42,
            },
            {
                "timestamp": "2024-01-01T00:07:00Z",
                "smart_meter_id": "SM-003",
                "energy_kwh": 0.64,
                "power_kw": 2.45,
                "voltage_v": 230.45,
                "current_a": 10.63,
            },
            {
                "timestamp": "2024-01-01T00:08:00Z",
                "smart_meter_id": "SM-004",
                "energy_kwh": 0.66,
                "power_kw": 2.50,
                "voltage_v": 230.50,
                "current_a": 10.85,
            },
            {
                "timestamp": "2024-01-01T00:09:00Z",
                "smart_meter_id": "SM-004",
                "energy_kwh": 0.68,
                "power_kw": 2.55,
                "voltage_v": 230.55,
                "current_a": 11.06,
            },
        ]
    }


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, sample_items) -> TestClient:
    # 1) Écrit un JSON temporaire
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    json_file = data_dir / "mock_readings.json"
    json_file.write_text(json.dumps(sample_items), encoding="utf-8")

    # 2) Configure l'app pour la source JSON
    monkeypatch.setenv("DATA_SOURCE", "json")
    monkeypatch.setenv("JSON_FILE", str(json_file))

    # 3) Recharge la config & l'app pour prendre en compte ces variables
    import app.settings as settings

    importlib.reload(settings)
    # data_provider et utils lisent settings
    import app.data_provider as data_provider
    import app.utils as utils

    importlib.reload(data_provider)
    importlib.reload(utils)
    # Enfin l'app
    import app.main as main

    importlib.reload(main)

    return TestClient(main.app)


# -----------------------------
# Helpers
# -----------------------------


def _poll_until_completed(client: TestClient, job_id: str, timeout_s: float = 10.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = client.get(f"/api/export/status/{job_id}")
        assert r.status_code == 200
        data = r.json()
        if data.get("status") == "completed":
            return data
        time.sleep(0.1)
    raise AssertionError("Job did not complete in time")


# -----------------------------
# Tests
# -----------------------------


def test_happy_path_sm001_2_minutes(client: TestClient):
    # Période: [00:00, 00:02) => lignes à 00:00 et 00:01 (2 enregistrements)
    payload = {
        "smart_meter_id": "SM-001",
        "start_datetime": "2024-01-01T00:00:00Z",
        "end_datetime": "2024-01-01T00:02:00Z",
        "format": "csv",
    }
    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    status = _poll_until_completed(client, job_id)
    assert status["file_info"]["record_count"] == 2

    d = client.get(f"/api/export/download/{job_id}")
    assert d.status_code == 200
    text = d.text.strip().splitlines()
    # 1 header + 2 rows
    assert len(text) == 3


def test_range_with_no_rows_is_ok(client: TestClient):
    # Aucune ligne dans cette plage pour SM-001
    payload = {
        "smart_meter_id": "SM-001",
        "start_datetime": "2024-01-01T01:00:00Z",
        "end_datetime": "2024-01-01T01:10:00Z",
        "format": "csv",
    }
    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    status = _poll_until_completed(client, job_id)
    assert status["file_info"]["record_count"] == 0

    d = client.get(f"/api/export/download/{job_id}")
    assert d.status_code == 200
    text = d.text.strip().splitlines()
    # Seulement l'en-tête
    assert len(text) == 1


def test_invalid_meter_id(client: TestClient):
    payload = {
        "smart_meter_id": "SM-999",
        "start_datetime": "2024-01-01T00:00:00Z",
        "end_datetime": "2024-01-01T00:10:00Z",
        "format": "csv",
    }
    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 400
    detail = r.json()["detail"]
    # En mode JSON, le code provient de validate_request() adapté
    assert detail["code"] == "SMART_METER_NOT_FOUND"


def test_concurrent_jobs_across_ids(client: TestClient):
    jobs = []

    # SM-002: [00:03, 00:06) -> 3 lignes (00:03, 00:04, 00:05)
    jobs.append(
        {
            "smart_meter_id": "SM-002",
            "start_datetime": "2024-01-01T00:03:00Z",
            "end_datetime": "2024-01-01T00:06:00Z",
            "format": "csv",
        }
    )

    # SM-003: [00:06, 00:08) -> 2 lignes (00:06, 00:07)
    jobs.append(
        {
            "smart_meter_id": "SM-003",
            "start_datetime": "2024-01-01T00:06:00Z",
            "end_datetime": "2024-01-01T00:08:00Z",
            "format": "csv",
        }
    )

    # SM-004: [00:08, 00:10) -> 2 lignes (00:08, 00:09)
    jobs.append(
        {
            "smart_meter_id": "SM-004",
            "start_datetime": "2024-01-01T00:08:00Z",
            "end_datetime": "2024-01-01T00:10:00Z",
            "format": "csv",
        }
    )

    job_ids = []
    for payload in jobs:
        r = client.post("/api/export/csv", json=payload)
        assert r.status_code == 202
        job_ids.append(r.json()["job_id"])

    counts = []
    for jid in job_ids:
        st = _poll_until_completed(client, jid)
        counts.append(st["file_info"]["record_count"])

    assert counts == [3, 2, 2]


def test_not_found_status_and_download(client: TestClient):
    s = client.get("/api/export/status/00000000-0000-0000-0000-000000000000")
    assert s.status_code == 200
    assert s.json()["status"] == "not_found"

    d = client.get("/api/export/download/00000000-0000-0000-0000-000000000000")
    assert d.status_code == 404
