from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


DEFAULT_INTERVAL_SECONDS = 4 * 60 * 60
DEFAULT_POLL_SECONDS = 60
DEFAULT_RETRY_INITIAL_SECONDS = 15 * 60
DEFAULT_RETRY_MAX_SECONDS = 60 * 60
DEFAULT_RETRY_MULTIPLIER = 2
DEFAULT_HOURS = 6
DEFAULT_STEP_SECONDS = 60


def _positive_int(
    environment: Mapping[str, str],
    name: str,
    default: int,
) -> int:
    raw_value = environment.get(name, str(default))

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")

    return value


@dataclass(frozen=True, slots=True)
class ConjunctionScreeningConfig:
    interval_seconds: int
    poll_seconds: int
    retry_initial_seconds: int
    retry_max_seconds: int
    retry_multiplier: int
    hours: int
    step_seconds: int

    @property
    def horizon_seconds(self) -> int:
        return self.hours * 60 * 60

    def retry_delay_seconds(self, consecutive_failures: int) -> int:
        if consecutive_failures <= 0:
            raise ValueError("consecutive_failures must be greater than zero")

        delay = self.retry_initial_seconds
        for _ in range(consecutive_failures - 1):
            if delay >= self.retry_max_seconds:
                return self.retry_max_seconds
            delay = min(
                self.retry_max_seconds,
                delay * self.retry_multiplier,
            )
        return delay

    @classmethod
    def from_env(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "ConjunctionScreeningConfig":
        values = os.environ if environment is None else environment

        interval_seconds = _positive_int(
            values,
            "ORBITAL_CONJUNCTION_SCREENING_INTERVAL_SECONDS",
            DEFAULT_INTERVAL_SECONDS,
        )
        poll_seconds = _positive_int(
            values,
            "ORBITAL_CONJUNCTION_SCREENING_POLL_SECONDS",
            DEFAULT_POLL_SECONDS,
        )
        retry_initial_seconds = _positive_int(
            values,
            "ORBITAL_CONJUNCTION_SCREENING_RETRY_INITIAL_SECONDS",
            DEFAULT_RETRY_INITIAL_SECONDS,
        )
        retry_max_seconds = _positive_int(
            values,
            "ORBITAL_CONJUNCTION_SCREENING_RETRY_MAX_SECONDS",
            DEFAULT_RETRY_MAX_SECONDS,
        )
        retry_multiplier = _positive_int(
            values,
            "ORBITAL_CONJUNCTION_SCREENING_RETRY_MULTIPLIER",
            DEFAULT_RETRY_MULTIPLIER,
        )
        hours = _positive_int(
            values,
            "ORBITAL_CONJUNCTION_SCREENING_HOURS",
            DEFAULT_HOURS,
        )
        step_seconds = _positive_int(
            values,
            "ORBITAL_CONJUNCTION_SCREENING_STEP_SECONDS",
            DEFAULT_STEP_SECONDS,
        )
        chunk_seconds = _positive_int(
            values,
            "ORBITAL_SCREENING_CHUNK_SECONDS",
            900,
        )

        if retry_max_seconds < retry_initial_seconds:
            raise ValueError(
                "ORBITAL_CONJUNCTION_SCREENING_RETRY_MAX_SECONDS must be "
                "greater than or equal to "
                "ORBITAL_CONJUNCTION_SCREENING_RETRY_INITIAL_SECONDS"
            )
        if retry_multiplier < 2:
            raise ValueError(
                "ORBITAL_CONJUNCTION_SCREENING_RETRY_MULTIPLIER must be "
                "greater than or equal to 2"
            )
        if poll_seconds > interval_seconds:
            raise ValueError(
                "ORBITAL_CONJUNCTION_SCREENING_POLL_SECONDS must be less "
                "than or equal to "
                "ORBITAL_CONJUNCTION_SCREENING_INTERVAL_SECONDS"
            )
        if step_seconds > hours * 60 * 60:
            raise ValueError(
                "ORBITAL_CONJUNCTION_SCREENING_STEP_SECONDS cannot exceed "
                "the configured screening horizon"
            )
        if chunk_seconds < step_seconds or chunk_seconds % step_seconds:
            raise ValueError(
                "ORBITAL_SCREENING_CHUNK_SECONDS must be at least and a "
                "multiple of ORBITAL_CONJUNCTION_SCREENING_STEP_SECONDS"
            )

        return cls(
            interval_seconds=interval_seconds,
            poll_seconds=poll_seconds,
            retry_initial_seconds=retry_initial_seconds,
            retry_max_seconds=retry_max_seconds,
            retry_multiplier=retry_multiplier,
            hours=hours,
            step_seconds=step_seconds,
        )
