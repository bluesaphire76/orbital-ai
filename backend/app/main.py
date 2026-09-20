from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import (
    make_asgi_app,
    REGISTRY,
)

from backend.app.api.routes.catalog import (
    router as catalog_router,
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


def create_app(*, metrics_registry=None) -> FastAPI:
    if metrics_registry is None:
        initialize_metrics()
        metrics_registry = REGISTRY

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
        catalog_router
    )

    app.include_router(
        conjunction_router
    )

    app.include_router(
        visualization_router
    )

    app.mount(
        "/metrics",
        make_asgi_app(registry=metrics_registry),
    )

    return app


app = create_app()
