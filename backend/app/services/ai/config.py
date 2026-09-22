from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit


def _strict_bool(environment: Mapping[str, str], name: str, default: bool) -> bool:
    raw_value = environment.get(name, "true" if default else "false")
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    raise ValueError(f"{name} must be exactly true or false")


def _positive_int(environment: Mapping[str, str], name: str, default: int) -> int:
    raw_value = environment.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _positive_float(
    environment: Mapping[str, str],
    name: str,
    default: float,
) -> float:
    raw_value = environment.get(name, str(default))
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


def _temperature(environment: Mapping[str, str]) -> float:
    raw_value = environment.get("ORBITAL_AI_TEMPERATURE", "0.1")
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError("ORBITAL_AI_TEMPERATURE must be a number") from exc
    if not math.isfinite(value) or not 0 <= value <= 2:
        raise ValueError("ORBITAL_AI_TEMPERATURE must be between 0 and 2")
    return value


def _base_url(environment: Mapping[str, str]) -> str:
    raw_value = environment.get(
        "ORBITAL_AI_BASE_URL",
        "http://llama-server:8080",
    ).strip()
    try:
        parsed = urlsplit(raw_value)
        parsed.port
    except ValueError as exc:
        raise ValueError("ORBITAL_AI_BASE_URL must be a valid URL") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("ORBITAL_AI_BASE_URL must use HTTP or HTTPS")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("ORBITAL_AI_BASE_URL must not include user information")
    if parsed.query or parsed.fragment:
        raise ValueError("ORBITAL_AI_BASE_URL must not include query or fragment")
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


@dataclass(frozen=True, slots=True)
class AIConfig:
    enabled: bool
    provider: str
    base_url: str
    api_key: str = field(repr=False)
    model: str
    connect_timeout_seconds: float
    timeout_seconds: float
    max_output_tokens: int
    max_queue: int
    concurrency: int
    temperature: float

    @classmethod
    def from_env(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "AIConfig":
        values = os.environ if environment is None else environment
        enabled = _strict_bool(values, "ORBITAL_AI_ENABLED", False)
        provider = values.get("ORBITAL_AI_PROVIDER", "llama.cpp").strip()
        if provider != "llama.cpp":
            raise ValueError("ORBITAL_AI_PROVIDER must be llama.cpp")

        model = values.get("ORBITAL_AI_MODEL", "").strip()
        api_key = values.get("ORBITAL_AI_API_KEY", "").strip()
        if model and ("/" in model or "\\" in model):
            raise ValueError("ORBITAL_AI_MODEL must be a public alias, not a path")
        if enabled and not model:
            raise ValueError("ORBITAL_AI_MODEL is required when AI is enabled")
        if enabled and not api_key:
            raise ValueError("ORBITAL_AI_API_KEY is required when AI is enabled")

        return cls(
            enabled=enabled,
            provider=provider,
            base_url=_base_url(values),
            api_key=api_key,
            model=model,
            connect_timeout_seconds=_positive_float(
                values,
                "ORBITAL_AI_CONNECT_TIMEOUT_SECONDS",
                3,
            ),
            timeout_seconds=_positive_float(
                values,
                "ORBITAL_AI_TIMEOUT_SECONDS",
                45,
            ),
            max_output_tokens=_positive_int(
                values,
                "ORBITAL_AI_MAX_OUTPUT_TOKENS",
                512,
            ),
            max_queue=_positive_int(values, "ORBITAL_AI_MAX_QUEUE", 20),
            concurrency=_positive_int(values, "ORBITAL_AI_CONCURRENCY", 1),
            temperature=_temperature(values),
        )


@lru_cache
def get_ai_config() -> AIConfig:
    return AIConfig.from_env()
