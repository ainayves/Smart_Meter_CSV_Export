# tests/unit/test_utils_provider.py
import json
import importlib
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


def _purge_modules():
    """Supprime tous les modules 'app.*' du cache pour un import propre."""
    for name in list(sys.modules):
        if name == "app" or name.startswith("app."):
            sys.modules.pop(name, None)


@pytest.fixture()
def json_file(tmp_path: Path):
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
        ]
    }
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    jf = data_dir / "mock.json"
    jf.write_text(json.dumps(data), encoding="utf-8")
    return jf


def test_validate_dates_only_ok_and_errors(json_file, monkeypatch):
    # Prépare l'env avant import
    monkeypatch.setenv("DATA_SOURCE", "json")
    monkeypatch.setenv("JSON_FILE", str(json_file))

    _purge_modules()  # purge complète

    import app.settings as settings

    # settings lit les env, pas besoin de reload si import frais

    import app.utils as utils

    # OK: start passé, end après, plage >= 1 min, <= 1 an
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=10)
    end = start + timedelta(minutes=2)
    s, e = utils.validate_dates_only(start, end)
    assert s.tzinfo is not None and e.tzinfo is not None

    # Erreur: start dans le futur
    with pytest.raises(utils.ValidationError) as exc:
        utils.validate_dates_only(
            now + timedelta(minutes=1), now + timedelta(minutes=2)
        )
    assert exc.value.code == "INVALID_DATE_RANGE"

    # Erreur: end <= start
    with pytest.raises(utils.ValidationError):
        utils.validate_dates_only(start, start)

    # Erreur: range < 1 minute
    with pytest.raises(utils.ValidationError):
        utils.validate_dates_only(start, start + timedelta(seconds=30))

    # Erreur: range > 1 an
    with pytest.raises(utils.ValidationError):
        utils.validate_dates_only(
            start, start + timedelta(days=settings.MAX_RANGE_DAYS + 1)
        )


def test_json_provider_filters_and_sort(json_file, monkeypatch):
    monkeypatch.setenv("DATA_SOURCE", "json")
    monkeypatch.setenv("JSON_FILE", str(json_file))

    _purge_modules()

    import app.settings as settings  # noqa: F401
    import app.data_provider as data_provider

    prov = data_provider.JSONProvider()

    # Plage [00:00, 00:02) -> 2 lignes pour SM-001 (00:00, 00:01)
    start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    end = datetime(2024, 1, 1, 0, 2, 0, tzinfo=timezone.utc)
    rows = list(prov.iter_readings("SM-001", start, end))
    assert len(rows) == 2
    assert rows[0][0] < rows[1][0]  # tri temporel

    # Plage sans lignes -> 0
    rows2 = list(
        prov.iter_readings(
            "SM-001", start + timedelta(hours=1), end + timedelta(hours=1)
        )
    )
    assert rows2 == []

    # ID inconnu -> 0
    rows3 = list(prov.iter_readings("SM-XXX", start, end))
    assert rows3 == []
