import json
import os
from datetime import datetime, timezone
from typing import Iterator, Tuple, List, Dict, Any

from .settings import JSON_FILE

RowT = Tuple[datetime, str, float, float, float, float]


def _to_utc(dt: datetime) -> datetime:
    """Force a datetime in UTC (timezone-aware)"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_ts(ts: str) -> datetime:
    """
    Parse an ISO timestamp. Supports the ‘Z’ suffix.
    Always returns a datetime in UTC.
    """
    if not isinstance(ts, str):
        raise ValueError("timestamp must be string")
    ts = ts.replace("Z", "+00:00")
    return _to_utc(datetime.fromisoformat(ts))


class JSONProvider:
    """
    Reads a fixed JSON file containing
    {
      "items": [
        {"timestamp": "...", "smart_meter_id": "...", "energy_kwh": 0.5, "power_kw": 2.1, "voltage_v": 230.1, "current_a": 9.1},
        ...
      ]
    }
    - Also accepts a direct list (without the ‘items’ key).
    """

    def __init__(self) -> None:
        self._items: List[Dict[str, Any]] = []
        # Start-up load (one-shot). If you want to reload for each job, read the file in iter_readings().
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._items = data.get("items", data if isinstance(data, list) else [])
            except Exception as exc:
                # Unreadable file or invalid JSON -> empty list
                self._items = []
        else:
            self._items = []

    def iter_readings(
        self, smart_meter_id: str, start: datetime, end: datetime
    ) -> Iterator[RowT]:
        """Returns (timestamp, smart_meter_id, energy_kwh, power_kw, voltage_v, current_a) filtered by ID and period."""
        s, e = _to_utc(start), _to_utc(end)
        buf: List[RowT] = []

        for r in self._items:
            try:
                if r.get("smart_meter_id") != smart_meter_id:
                    continue
                ts_dt = _parse_ts(r["timestamp"])
                if ts_dt < s or ts_dt >= e:
                    continue
                row: RowT = (
                    ts_dt,
                    r["smart_meter_id"],
                    float(r["energy_kwh"]),
                    float(r["power_kw"]),
                    float(r["voltage_v"]),
                    float(r["current_a"]),
                )
                buf.append(row)
            except Exception:
                # Ignore une ligne mal formée
                continue

        # Trie par timestamp croissant pour un CSV régulier
        buf.sort(key=lambda x: x[0])
        for row in buf:
            yield row


def get_provider() -> JSONProvider:
    """Standard entry point for services."""
    return JSONProvider()
