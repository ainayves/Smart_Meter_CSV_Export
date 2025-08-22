from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Iterator, Tuple
import json, os

from .settings import MAX_RANGE_DAYS, MIN_RANGE_SECONDS, DATA_SOURCE, JSON_FILE


class ValidationError(Exception):
    def __init__(self, code: str, message: str, details: str = ""):
        super().__init__(message)
        self.code = code
        self.details = details


# Validating dates for the /jobs endpoint (and revalidating in the background)


def validate_dates_only(start: datetime, end: datetime):
    """Valide uniquement les règles de dates demandées pour l'endpoint.
    - start: requis, dans le passé
    - end: requis, après start
    - range min 1 minute, max 1 an
    Retourne (start_utc, end_utc)
    """
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


# Utilities for background processing (not used by the endpoint)
@lru_cache(maxsize=1)
def json_known_meters() -> set[str]:
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
