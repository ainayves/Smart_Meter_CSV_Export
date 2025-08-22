# tests/integration/test_exports_integration.py
import json
import time
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def _purge_modules():
    """Supprime tous les modules 'app.*' du cache pour un import propre."""
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """
    Démarre l'app avec:
      - un JSON temporaire (data/mock.json)
      - un EXPORT_DIR temporaire
      - une DB SQLite temporaire (app.db dans tmp_path)
    """
    # Jeu de données fixe
    data = {
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

    # Chemins temporaires
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    json_file = data_dir / "mock.json"
    json_file.write_text(json.dumps(data), encoding="utf-8")

    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    db_file = tmp_path / "app.db"

    # Purge complète avant (ré)imports
    _purge_modules()

    # 1) settings: pointe vers nos chemins temporaires
    import app.settings as settings

    settings.DATA_SOURCE = "json"
    settings.JSON_FILE = str(json_file)
    settings.EXPORT_DIR = exports_dir
    settings.DB_URL = f"sqlite:///{db_file}"

    # 2) database: dispose tout ancien engine et nettoie le MetaData
    import app.database as database

    try:
        database.engine.dispose()
    except Exception:
        pass
    database.Base.metadata.clear()

    # 3) imports frais du reste de la stack (aucun reload nécessaire après purge)
    import app.models as models  # noqa: F401
    import app.utils as utils  # noqa: F401
    import app.data_provider as data_provider  # noqa: F401
    import app.services as services  # noqa: F401
    import app.main as main

    return TestClient(main.app)


def _poll_until_terminal(client: TestClient, job_id: str, timeout_s: float = 10.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = client.get(f"/api/export/status/{job_id}")
        assert r.status_code == 200
        data = r.json()
        if data.get("status") in ("completed", "failed"):
            return data
        time.sleep(0.1)
    raise AssertionError("Timeout waiting job terminal state")


def test_happy_path_sm001_2_minutes(client: TestClient):
    payload = {
        "smart_meter_id": "SM-001",
        "start_datetime": "2024-01-01T00:00:00Z",
        "end_datetime": "2024-01-01T00:02:00Z",
        "format": "csv",
    }
    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    status = _poll_until_terminal(client, job_id)
    assert status["status"] == "completed"
    assert status["file_info"]["record_count"] == 2

    d = client.get(f"/api/export/download/{job_id}")
    assert d.status_code == 200
    assert "text/csv" in d.headers["content-type"]
    lines = d.text.strip().splitlines()
    assert len(lines) == 3  # header + 2 rows


def test_invalid_dates_rejected_at_endpoint(client: TestClient):
    payload = {
        "smart_meter_id": "SM-001",
        "start_datetime": "2024-01-01T00:02:00Z",
        "end_datetime": "2024-01-01T00:01:00Z",
        "format": "csv",
    }
    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 400
    detail = r.json().get("detail", {})
    assert detail.get("code") == "INVALID_DATE_RANGE"


def test_unknown_meter_id_is_reported_in_status(client: TestClient):
    payload = {
        "smart_meter_id": "SM-999",
        "start_datetime": "2024-01-01T00:00:00Z",
        "end_datetime": "2024-01-01T00:10:00Z",
        "format": "csv",
    }
    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    status = _poll_until_terminal(client, job_id)
    assert status["status"] == "failed"
    err = status.get("error", {})
    assert err.get("code") in {
        "SMART_METER_NOT_FOUND",
        "SMART_DATA_SOURCE_EMPTY",
        "UNEXPECTED_ERROR",
    }


def test_range_with_no_rows_is_ok(client: TestClient):
    payload = {
        "smart_meter_id": "SM-001",
        "start_datetime": "2024-01-01T01:00:00Z",
        "end_datetime": "2024-01-01T01:10:00Z",
        "format": "csv",
    }
    r = client.post("/api/export/csv", json=payload)
    assert r.status_code == 202
    job_id = r.json()["job_id"]

    status = _poll_until_terminal(client, job_id)
    assert status["status"] == "completed"
    assert status["file_info"]["record_count"] == 0

    d = client.get(f"/api/export/download/{job_id}")
    assert d.status_code == 200
    assert len(d.text.strip().splitlines()) == 1  # header only


def test_concurrent_jobs_across_ids(client: TestClient):
    jobs = [
        {
            "smart_meter_id": "SM-002",
            "start_datetime": "2024-01-01T00:03:00Z",
            "end_datetime": "2024-01-01T00:06:00Z",
            "format": "csv",
        },  # 3
        {
            "smart_meter_id": "SM-003",
            "start_datetime": "2024-01-01T00:06:00Z",
            "end_datetime": "2024-01-01T00:08:00Z",
            "format": "csv",
        },  # 2
        {
            "smart_meter_id": "SM-004",
            "start_datetime": "2024-01-01T00:08:00Z",
            "end_datetime": "2024-01-01T00:10:00Z",
            "format": "csv",
        },  # 2
    ]
    job_ids = []
    for p in jobs:
        r = client.post("/api/export/csv", json=p)
        assert r.status_code == 202
        job_ids.append(r.json()["job_id"])

    counts = []
    for jid in job_ids:
        st = _poll_until_terminal(client, jid)
        assert st["status"] == "completed"
        counts.append(st["file_info"]["record_count"])

    assert counts == [3, 2, 2]


def test_not_found_status_and_download(client: TestClient):
    s = client.get("/api/export/status/00000000-0000-0000-0000-000000000000")
    assert s.status_code == 200
    assert s.json()["status"] == "not_found"

    d = client.get("/api/export/download/00000000-0000-0000-0000-000000000000")
    assert d.status_code == 404
