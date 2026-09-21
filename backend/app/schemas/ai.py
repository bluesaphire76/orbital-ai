from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, NonNegativeFloat, PositiveInt


class AIHealthStatus(str, Enum):
    DISABLED = "disabled"
    READY = "ready"
    LOADING = "loading"
    UNAVAILABLE = "unavailable"


class AIFeaturesRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chat_completions: bool
    structured_output: bool
    conjunction_brief: bool


class AILimitsRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_output_tokens: PositiveInt
    max_queue: PositiveInt
    concurrency: PositiveInt


class AICapabilitiesRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    provider: str
    model: str | None
    features: AIFeaturesRead
    limits: AILimitsRead


class AIHealthRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    status: AIHealthStatus
    provider: str
    model: str | None
    latency_ms: NonNegativeFloat | None
