from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from backend.app.api.routes.health import router as health_router
from backend.app.core.metrics import initialize_metrics


def create_app() -> FastAPI:
    application = FastAPI(
        title="OrbitalAI API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    application.include_router(health_router)
    application.mount("/metrics", make_asgi_app())

    initialize_metrics()

    return application


app = create_app()
