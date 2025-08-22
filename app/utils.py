from __future__ import annotations
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import json, os
from typing import Iterator, Tuple

from .settings import (
    KNOWN_SMART_METERS,
    MAX_RANGE_DAYS,
    MIN_RANGE_SECONDS,
    DATA_SOURCE,
    JSON_FILE,
)


class ValidationError(Exception):
    def __init__(self, code: str, message: str, details: str = ""):
        super().__init__(message)
        self.code = code
        self.details = details


@lru_cache(maxsize=1)
def _json_known_meters() -> set[str]:
    """Construit l’ensemble des smart_meter_id présents dans le fichier JSON."""
    if not JSON_FILE or not os.path.exists(JSON_FILE):
        return set()
    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        items = data.get("items", data if isinstance(data, list) else [])
        return {
            str(it.get("smart_meter_id")) for it in items if it.get("smart_meter_id")
        }
    except Exception:
        return set()


def validate_request(smart_meter_id: str, start: datetime, end: datetime):
    if not smart_meter_id:
        raise ValidationError("VALIDATION_ERROR", "Smart meter ID is required")

    # 🔒 Validation de l'existence du compteur en fonction de la source
    if DATA_SOURCE == "json":
        json_ids = _json_known_meters()
        if not json_ids:
            raise ValidationError(
                "SMART_DATA_SOURCE_EMPTY",
                "data source not available or empty",
                f"JSON_FILE={JSON_FILE!r}",
            )
        if smart_meter_id not in json_ids:
            raise ValidationError(
                "SMART_METER_NOT_FOUND",
                f"Smart meter '{smart_meter_id}' not found in data",
                f"Available IDs: {sorted(json_ids)}",
            )
    else:
        if smart_meter_id not in KNOWN_SMART_METERS:
            raise ValidationError(
                "SMART_METER_NOT_FOUND",
                f"Smart meter with ID '{smart_meter_id}' not found",
                "The specified smart meter does not exist in the system",
            )

    # Normalisation UTC
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    if start >= now:
        raise ValidationError(
            "INVALID_DATE_RANGE", "Start datetime must be in the past"
        )
    if end <= start:
        raise ValidationError(
            "INVALID_DATE_RANGE", "End datetime must be after start datetime"
        )

    total_seconds = (end - start).total_seconds()
    if total_seconds < MIN_RANGE_SECONDS:
        raise ValidationError("INVALID_DATE_RANGE", "Minimum date range is 1 minute")
    if (end - start) > timedelta(days=MAX_RANGE_DAYS):
        raise ValidationError("INVALID_DATE_RANGE", "Maximum date range is 1 year")

    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)
