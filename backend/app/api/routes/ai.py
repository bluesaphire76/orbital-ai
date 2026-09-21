from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status

from backend.app.schemas.ai import (
    AICapabilitiesRead,
    AIFeaturesRead,
    AIHealthRead,
    AIHealthStatus,
    AILimitsRead,
)
from backend.app.services.ai.config import AIConfig, get_ai_config
from backend.app.services.ai.gateway import AIGateway
from backend.app.services.ai.llama_cpp import LlamaCppProvider
from backend.app.services.ai.models import ProviderHealthStatus


router = APIRouter(prefix="/ai", tags=["ai"])


def get_ai_gateway(
    request: Request,
    config: AIConfig = Depends(get_ai_config),
) -> AIGateway:
    return AIGateway(
        config,
        LlamaCppProvider(config),
        metrics=request.app.state.ai_metrics,
    )


@router.get(
    "/capabilities",
    response_model=AICapabilitiesRead,
    status_code=status.HTTP_200_OK,
    summary="Get local AI capabilities",
)
def get_ai_capabilities(
    config: AIConfig = Depends(get_ai_config),
) -> AICapabilitiesRead:
    return AICapabilitiesRead(
        enabled=config.enabled,
        provider=config.provider,
        model=config.model or None,
        features=AIFeaturesRead(
            chat_completions=True,
            structured_output=True,
            conjunction_brief=False,
        ),
        limits=AILimitsRead(
            max_output_tokens=config.max_output_tokens,
            max_queue=config.max_queue,
            concurrency=config.concurrency,
        ),
    )


@router.get(
    "/health",
    response_model=AIHealthRead,
    status_code=status.HTTP_200_OK,
    summary="Get optional local AI runtime health",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": AIHealthRead,
            "description": "Local AI model is loading or unavailable",
        }
    },
)
async def get_ai_health(
    response: Response,
    config: AIConfig = Depends(get_ai_config),
    gateway: AIGateway = Depends(get_ai_gateway),
) -> AIHealthRead:
    if not config.enabled:
        return AIHealthRead(
            enabled=False,
            status=AIHealthStatus.DISABLED,
            provider=config.provider,
            model=config.model or None,
            latency_ms=None,
        )

    health = await gateway.health()
    public_status = AIHealthStatus(health.status.value)
    if health.status is not ProviderHealthStatus.READY:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return AIHealthRead(
        enabled=True,
        status=public_status,
        provider=config.provider,
        model=config.model or None,
        latency_ms=health.latency_ms,
    )
