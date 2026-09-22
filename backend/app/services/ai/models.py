from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class AITask(str, Enum):
    FOUNDATION_PROBE = "foundation_probe"
    CONJUNCTION_ANALYST_BRIEF = "conjunction_analyst_brief"


class ChatRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ProviderHealthStatus(str, Enum):
    READY = "ready"
    LOADING = "loading"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: ChatRole
    content: str

    def __post_init__(self) -> None:
        if not self.content.strip():
            raise ValueError("Chat message content must not be empty")


@dataclass(frozen=True, slots=True)
class JSONSchemaResponseFormat:
    name: str
    schema: Mapping[str, object]
    strict: bool = True

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("JSON schema name must not be empty")


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    task: AITask
    messages: tuple[ChatMessage, ...]
    max_output_tokens: int | None = None
    response_format: JSONSchemaResponseFormat | None = None

    def __post_init__(self) -> None:
        if not self.messages:
            raise ValueError("Generation request must contain messages")
        if self.max_output_tokens is not None and self.max_output_tokens <= 0:
            raise ValueError("max_output_tokens must be greater than zero")


@dataclass(frozen=True, slots=True)
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class GenerationTimings:
    prompt_ms: float | None = None
    predicted_ms: float | None = None
    prompt_per_second: float | None = None
    predicted_per_second: float | None = None


@dataclass(frozen=True, slots=True)
class GenerationResult:
    content: str
    usage: TokenUsage | None = None
    timings: GenerationTimings | None = None
    finish_reason: str | None = None
    reasoning_content: str | None = None
    provider_latency_ms: float | None = None


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    status: ProviderHealthStatus
    latency_ms: float | None = None
