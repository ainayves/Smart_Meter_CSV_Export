# tests/conftest.py
from pathlib import Path
import sys

# Assure que le package "app" est importable
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
