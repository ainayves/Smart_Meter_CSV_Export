# app/main.py
from __future__ import annotations
from fastapi import FastAPI
import uvicorn
from .database import Base, engine
from .routes.export import router as export_router
from .settings import APP_HOST, APP_PORT


app = FastAPI(
    title="Smart Meter CSV Export API",
    version="1.0.0",
    description="API d’export CSV des compteurs intelligents",
    docs_url="/api/docs",  # Swagger UI
    redoc_url="/api/redoc",  # ReDoc
    openapi_url="/api/openapi.json",  # OpenAPI
)

# Creates tables on startup
Base.metadata.create_all(bind=engine)

# Mount the router /api/export
app.include_router(export_router)

if __name__ == "__main__":
    
    uvicorn.run(app, host=APP_HOST, port=APP_PORT)
