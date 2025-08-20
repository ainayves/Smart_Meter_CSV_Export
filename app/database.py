from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from .settings import DB_URL


# --- Declarative base (SQLAlchemy 2.x) ----------------------------------------
class Base(DeclarativeBase):
    """Base declarative class for all models."""

    pass


# --- Engine & session ---------------------------------------------------------
# SQLite + FastAPI: check_same_thread=False permet l'accès multi-threads.
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    """Dépendance FastAPI: ouvre une session et la ferme proprement."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Créer les tables si elles n'existent pas (idempotent)."""
    from . import models  # s'assurer que les modèles sont importés

    Base.metadata.create_all(bind=engine)
