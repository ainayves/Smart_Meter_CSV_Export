from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent
DB_URL = f"sqlite:///{BASE_DIR / 'app.db'}"
EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)


# Background workers
MAX_WORKERS = 4


# Mock smart meter registry (simulate existing meters)
KNOWN_SMART_METERS = {"SM-001", "SM-002", "SM-003"}


# Limits
MAX_RANGE_DAYS = 366  # inclusive upper bound ~ 1 year
MIN_RANGE_SECONDS = 60


# --- Nouveaux réglages réseau ---
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")  # ou "0.0.0.0" en conteneur/VM
APP_PORT = int(os.getenv("APP_PORT", "8000"))

# Optionnel : URL publique pour générer des liens absolus
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", f"http://{APP_HOST}:{APP_PORT}")
