# app/main.py
from __future__ import annotations

from fastapi import FastAPI

from .database import Base, engine
from .routes.export import router as export_router

app = FastAPI(title="Smart Meter CSV Export API")

# Crée les tables au démarrage
Base.metadata.create_all(bind=engine)

# Monte le routeur /api/export
app.include_router(export_router)
