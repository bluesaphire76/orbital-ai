from __future__ import annotations

from typing import Protocol

from backend.app.services.ai.models import (
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
)


class AIProvider(Protocol):
    async def health(self) -> ProviderHealth:
        ...

    async def chat_completion(
        self,
        request: GenerationRequest,
    ) -> GenerationResult:
        ...
