from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import logging
import json
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from sqlalchemy.orm import Session

from backend.app.api.dependencies import get_db_session
from backend.app.db.repositories.conjunctions import ConjunctionRepository

from backend.app.schemas.ai import (
    AICapabilitiesRead,
    AIFeaturesRead,
    AIHealthRead,
    AIHealthStatus,
    AILimitsRead,
    ConjunctionBriefEventRead,
    ConjunctionBriefMetadataRead,
    ConjunctionBriefResponse,
)
from backend.app.services.ai.config import AIConfig, get_ai_config
from backend.app.services.ai.gateway import AIGateway
from backend.app.services.ai.conjunction_brief import (
    DISCLAIMER,
    PROMPT_VERSION,
    GroundingError,
    build_context,
    generation_request,
    grounding_sha256,
    normalization_log_record,
    validate_result_with_normalization,
    validation_log_record,
)
from backend.app.services.ai.errors import (
    AIDisabledError,
    AIInvalidResponseError,
    AIProviderUnavailableError,
    AIQueueFullError,
    AITimeoutError,
)
from backend.app.services.ai.models import AITask, ProviderHealthStatus


router = APIRouter(prefix="/ai", tags=["ai"])
logger = logging.getLogger(__name__)


def get_ai_gateway(
    request: Request,
) -> AIGateway:
    return request.app.state.ai_gateway


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
            conjunction_brief=config.enabled,
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


@router.post(
    "/conjunctions/{event_id}/brief",
    response_model=ConjunctionBriefResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate an analyst brief for a persisted conjunction event",
    responses={
        404: {"description": "Conjunction event not found"},
        409: {"description": "Persisted event grounding is incomplete"},
        429: {"description": "Local AI request queue is full"},
        502: {"description": "Local AI returned invalid output"},
        503: {"description": "Local AI is disabled or unavailable"},
        504: {"description": "Local AI request timed out"},
    },
)
async def create_conjunction_analyst_brief(
    request: Request,
    event_id: int = Path(gt=0),
    session: Session = Depends(get_db_session),
    config: AIConfig = Depends(get_ai_config),
    gateway: AIGateway = Depends(get_ai_gateway),
) -> ConjunctionBriefResponse:
    if request.query_params or (await request.body()).strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This endpoint accepts only the event ID path parameter",
        )

    metrics = request.app.state.ai_metrics
    row = ConjunctionRepository(session).get_event_grounding(event_id)
    if row is None:
        metrics.observe_request(AITask.CONJUNCTION_ANALYST_BRIEF, "grounding_error")
        raise HTTPException(status_code=404, detail="Conjunction event not found")
    try:
        context = build_context(row)
    except GroundingError as exc:
        metrics.observe_request(AITask.CONJUNCTION_ANALYST_BRIEF, "grounding_error")
        raise HTTPException(
            status_code=409,
            detail="Conjunction event grounding is incomplete or inconsistent",
        ) from exc

    if not config.enabled:
        metrics.observe_request(AITask.CONJUNCTION_ANALYST_BRIEF, "disabled")
        raise HTTPException(status_code=503, detail="Local AI is disabled")

    parsed = None

    def log_normalization(normalization):
        logger.info(
            json.dumps(normalization_log_record(normalization), sort_keys=True)
        )

    def validate(generation_result):
        nonlocal parsed
        parsed, _ = validate_result_with_normalization(
            generation_result,
            context,
            normalization_observer=log_normalization,
        )

    started = perf_counter()
    try:
        result = await gateway.generate(
            generation_request(context),
            validate_result=validate,
        )
    except AIQueueFullError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except AITimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except (AIDisabledError, AIProviderUnavailableError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AIInvalidResponseError as exc:
        logger.warning(json.dumps(validation_log_record(exc), sort_keys=True))
        raise HTTPException(
            status_code=502,
            detail="Local AI provider returned an invalid response",
        ) from exc

    if parsed is None:
        raise HTTPException(status_code=502, detail="Local AI provider returned an invalid response")
    usage = result.usage
    return ConjunctionBriefResponse(
        event=ConjunctionBriefEventRead.model_validate(asdict(context)),
        brief=parsed,
        metadata=ConjunctionBriefMetadataRead(
            task=AITask.CONJUNCTION_ANALYST_BRIEF.value,
            prompt_version=PROMPT_VERSION,
            grounding_sha256=grounding_sha256(context),
            generated_at=datetime.now(timezone.utc),
            provider=config.provider,
            model=config.model,
            finish_reason="stop",
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            total_tokens=usage.total_tokens if usage else None,
            duration_seconds=perf_counter() - started,
        ),
        disclaimer=DISCLAIMER,
    )
