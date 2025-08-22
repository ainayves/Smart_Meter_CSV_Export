# app/main.py
from __future__ import annotations

from fastapi import FastAPI

from .database import Base, engine
from .routes.export import router as export_router

app = FastAPI(
    title="Smart Meter CSV Export API",
    version="1.0.0",
    description="API d’export CSV des compteurs intelligents",
    docs_url="/api/docs",  # Swagger UI
    redoc_url="/api/redoc",  # ReDoc
    openapi_url="/api/openapi.json",  # schéma OpenAPI
)

# Crée les tables au démarrage
Base.metadata.create_all(bind=engine)

# Monte le routeur /api/export
app.include_router(export_router)
