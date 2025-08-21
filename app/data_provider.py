
import json
import os
from datetime import datetime, timezone
from typing import Iterator, Tuple, List, Dict, Any

from .settings import JSON_FILE  # chemin du fichier JSON (configuré dans settings.py)

# Type d'une ligne normalisée
RowT = Tuple[datetime, str, float, float, float, float]


def _to_utc(dt: datetime) -> datetime:
    """Force un datetime en UTC (timezone-aware)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _parse_ts(ts: str) -> datetime:
    """
    Parse un timestamp ISO. Supporte le suffixe 'Z'.
    Retourne toujours un datetime en UTC.
    """
    if not isinstance(ts, str):
        raise ValueError("timestamp must be string")
    ts = ts.replace("Z", "+00:00")
    return _to_utc(datetime.fromisoformat(ts))


class JSONProvider:
    """
    Lit un fichier JSON fixe contenant:
    {
      "items": [
        {"timestamp": "...", "smart_meter_id": "...", "energy_kwh": 0.5, "power_kw": 2.1, "voltage_v": 230.1, "current_a": 9.1},
        ...
      ]
    }
    - Accepte aussi une liste directe (sans clé 'items').
    """

    def __init__(self) -> None:
        self._items: List[Dict[str, Any]] = []
        # Charge au démarrage (one-shot). Si tu veux recharger à chaque job, lis le fichier dans iter_readings().
        if os.path.exists(JSON_FILE):
            try:
                with open(JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._items = data.get("items", data if isinstance(data, list) else [])
            except Exception as exc:
                # Fichier illisible ou JSON invalide -> liste vide
                self._items = []
        else:
            self._items = []

    def iter_readings(self, smart_meter_id: str, start: datetime, end: datetime) -> Iterator[RowT]:
        """Rend (timestamp, smart_meter_id, energy_kwh, power_kw, voltage_v, current_a) filtrés par ID et période."""
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
    """Point d'entrée standard pour les services."""
    return JSONProvider()