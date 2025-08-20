from datetime import datetime, timedelta, timezone
from typing import Iterator, Tuple
from math import sin


from .settings import KNOWN_SMART_METERS, MAX_RANGE_DAYS, MIN_RANGE_SECONDS


class ValidationError(Exception):
    def __init__(self, code: str, message: str, details: str = ""):
        super().__init__(message)
        self.code = code
        self.details = details


def validate_request(smart_meter_id: str, start: datetime, end: datetime):
    if not smart_meter_id:
        raise ValidationError("VALIDATION_ERROR", "Smart meter ID is required")
    if smart_meter_id not in KNOWN_SMART_METERS:
        raise ValidationError(
            "SMART_METER_NOT_FOUND",
            f"Smart meter with ID '{smart_meter_id}' not found",
            "The specified smart meter does not exist in the system",
        )

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


def generate_smart_meter_data(
    smart_meter_id: str, start: datetime, end: datetime
) -> Iterator[Tuple[datetime, str, float, float, float, float]]:
    """Yield per-minute readings between start (inclusive) and end (exclusive).
    Values are mock but plausible.
    """
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    cursor = start
    step = timedelta(minutes=1)
    i = 0
    while cursor < end:
        # Synthetic waveform around base values
        energy_kwh = round(0.4 + 0.2 * (1 + sin(i / 60.0)), 4)
        power_kw = round(1.8 + 0.8 * (1 + sin(i / 15.0)), 3)
        voltage_v = round(228.0 + 4.0 * (1 + sin(i / 30.0)), 2)
        current_a = round(power_kw * 1000 / max(voltage_v, 1e-3), 2)
        yield (cursor, smart_meter_id, energy_kwh, power_kw, voltage_v, current_a)
        cursor += step
        i += 1
