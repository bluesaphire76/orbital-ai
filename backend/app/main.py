from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import (
    make_asgi_app,
)

from backend.app.api.routes.conjunctions import (
    router as conjunction_router,
)
from backend.app.api.routes.health import (
    router as health_router,
)
from backend.app.api.routes.visualization import (
    router as visualization_router,
)
from backend.app.core.metrics import (
    initialize_metrics,
)


def create_app() -> FastAPI:
    initialize_metrics()

    app = FastAPI(
        title="OrbitalAI API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
    )

    app.include_router(
        health_router
    )

    app.include_router(
        conjunction_router
    )

    app.include_router(
        visualization_router
    )

    app.mount(
        "/metrics",
        make_asgi_app(),
    )

    return app


app = create_app()
