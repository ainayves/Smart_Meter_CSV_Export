# tests/unit/test_job_repository.py
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest


def _purge_modules():
    """Supprime tous les modules 'app.*' du cache pour forcer un import propre par test."""
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """
    Prépare une DB SQLite temporaire et retourne (repo, session, models).
    Chaque test part d'un état DB vierge.
    """
    _purge_modules()

    # Chemins & env
    db_file = tmp_path / "app.db"
    monkeypatch.setenv(
        "DATA_SOURCE", "json"
    )  # pas utilisé ici, mais cohérent avec l'app

    # settings
    import app.settings as settings

    settings.DB_URL = f"sqlite:///{db_file}"

    # database
    import app.database as database

    try:
        database.engine.dispose()
    except Exception:
        pass
    database.Base.metadata.clear()

    # models (déclare Job sur le Base)
    import app.models as models

    # Crée les tables
    database.Base.metadata.create_all(bind=database.engine)

    # session + repo
    session = database.SessionLocal()

    from app.repositories.jobs import JobRepository

    yield JobRepository(session), session, models

    # Teardown
    session.close()
    try:
        database.engine.dispose()
    except Exception:
        pass


def _utc(y, m, d, hh=0, mm=0, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """Normalise un datetime en aware UTC. Si tzinfo manquant (SQLite), on assume UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def test_create_and_get(repo):
    job_repo, session, models = repo  # noqa: F841

    start = _utc(2024, 1, 1, 0, 0, 0)
    end = _utc(2024, 1, 1, 0, 10, 0)

    job = job_repo.create(
        smart_meter_id="SM-001", start_datetime=start, end_datetime=end
    )
    assert job.id and isinstance(job.id, str)
    assert job.smart_meter_id == "SM-001"
    assert job.status == "pending"

    fetched = job_repo.get(job.id)
    assert fetched is not None
    # ⚠️ SQLite peut renvoyer des datetimes naïfs : on normalise avant de comparer
    assert _as_utc(fetched.start_datetime) == start
    assert _as_utc(fetched.end_datetime) == end


def test_mark_processing_updates_status_and_timestamp(repo):
    job_repo, session, models = repo  # noqa: F841
    start = _utc(2024, 1, 1, 0, 0, 0)
    end = _utc(2024, 1, 1, 0, 10, 0)

    job = job_repo.create(
        smart_meter_id="SM-001", start_datetime=start, end_datetime=end
    )
    before = job.updated_at
    job_repo.mark_processing(job)
    assert job.status == "processing"
    assert job.updated_at is not None
    assert (
        job.updated_at != before
    )  # on ne compare pas le tzinfo ici, juste le changement


def test_mark_completed_sets_file_info_and_status(repo, tmp_path: Path):
    job_repo, session, models = repo  # noqa: F841
    start = _utc(2024, 1, 1, 0, 0, 0)
    end = _utc(2024, 1, 1, 0, 10, 0)

    job = job_repo.create(
        smart_meter_id="SM-001", start_datetime=start, end_datetime=end
    )

    file_path = tmp_path / "exports" / "file.csv"
    record_count = 42
    file_size_bytes = 1234

    job_repo.mark_completed(
        job,
        file_path=file_path,
        record_count=record_count,
        file_size_bytes=file_size_bytes,
    )

    assert job.status == "completed"
    assert job.file_path == str(file_path)
    assert job.record_count == record_count
    assert job.file_size_bytes == file_size_bytes


def test_mark_failed_formats_error_message_with_details(repo):
    job_repo, session, models = repo  # noqa: F841
    start = _utc(2024, 1, 1, 0, 0, 0)
    end = _utc(2024, 1, 1, 0, 10, 0)

    job = job_repo.create(
        smart_meter_id="SM-001", start_datetime=start, end_datetime=end
    )

    job_repo.mark_failed(
        job,
        code="SMART_METER_NOT_FOUND",
        message="Smart meter 'SM-999' not found",
        details="Available: ['SM-001']",
    )
    assert job.status == "failed"
    assert job.error_message.startswith("SMART_METER_NOT_FOUND:")
    assert "::" in job.error_message  # CODE:Message::details


def test_mark_failed_formats_error_message_without_details(repo):
    job_repo, session, models = repo  # noqa: F841
    start = _utc(2024, 1, 1, 0, 0, 0)
    end = _utc(2024, 1, 1, 0, 10, 0)

    job = job_repo.create(
        smart_meter_id="SM-001", start_datetime=start, end_datetime=end
    )

    job_repo.mark_failed(job, code="UNEXPECTED_ERROR", message="IO error")
    assert job.status == "failed"
    assert (
        job.error_message == "UNEXPECTED_ERROR:IO error"
    )  # sans details => pas de '::'
