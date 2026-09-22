from __future__ import annotations

import asyncio
from time import perf_counter

from backend.app.observability.ai_metrics import AIMetrics
from backend.app.services.ai.config import AIConfig
from backend.app.services.ai.errors import (
    AIDisabledError,
    AIError,
    AIQueueFullError,
    AITimeoutError,
)
from backend.app.services.ai.models import (
    GenerationRequest,
    GenerationResult,
    ProviderHealth,
    ProviderHealthStatus,
)
from backend.app.services.ai.provider import AIProvider


class AIGateway:
    def __init__(
        self,
        config: AIConfig,
        provider: AIProvider,
        *,
        metrics: AIMetrics | None = None,
    ) -> None:
        self._config = config
        self._provider = provider
        self._metrics = metrics
        self._semaphore = asyncio.Semaphore(config.concurrency)
        self._state_lock = asyncio.Lock()
        self._running = 0
        self._waiting = 0
        if metrics is not None:
            metrics.set_queue_capacity(config.max_queue)
            metrics.set_concurrency_capacity(config.concurrency)
            self._set_execution_state()

    @property
    def running(self) -> int:
        return self._running

    @property
    def waiting(self) -> int:
        return self._waiting

    async def health(self) -> ProviderHealth:
        if not self._config.enabled:
            if self._metrics is not None:
                self._metrics.set_runtime_ready(False)
            return ProviderHealth(status=ProviderHealthStatus.UNAVAILABLE)
        health = await self._provider.health()
        if self._metrics is not None:
            self._metrics.set_runtime_ready(
                health.status is ProviderHealthStatus.READY
            )
        return health

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        task = request.task
        if not self._config.enabled:
            if self._metrics is not None:
                self._metrics.observe_request(task, "disabled")
            raise AIDisabledError()

        queued = False
        counted_running = False
        acquired = False
        async with self._state_lock:
            if self._running < self._config.concurrency:
                self._running += 1
                counted_running = True
                self._set_execution_state()
            elif self._waiting >= self._config.max_queue:
                if self._metrics is not None:
                    self._metrics.observe_request(task, "queue_full")
                raise AIQueueFullError()
            else:
                self._waiting += 1
                queued = True
                self._set_execution_state()

        started = perf_counter()
        try:
            await self._semaphore.acquire()
            acquired = True
            if queued:
                async with self._state_lock:
                    self._waiting -= 1
                    self._running += 1
                    queued = False
                    counted_running = True
                    self._set_execution_state()

            try:
                async with asyncio.timeout(self._config.timeout_seconds):
                    result = await self._provider.chat_completion(request)
            except (TimeoutError, AITimeoutError) as exc:
                if self._metrics is not None:
                    self._metrics.observe_request(
                        task, "timeout", perf_counter() - started
                    )
                    self._metrics.observe_timeout(task)
                if isinstance(exc, AITimeoutError):
                    raise
                raise AITimeoutError() from exc
            except AIError:
                if self._metrics is not None:
                    self._metrics.observe_request(
                        task, "error", perf_counter() - started
                    )
                raise
            except Exception:
                if self._metrics is not None:
                    self._metrics.observe_request(
                        task, "error", perf_counter() - started
                    )
                raise

            if self._metrics is not None:
                self._metrics.observe_request(
                    task, "success", perf_counter() - started
                )
                if result.usage is not None:
                    self._metrics.observe_tokens(
                        task,
                        result.usage.prompt_tokens,
                        result.usage.completion_tokens,
                    )
            return result
        finally:
            async with self._state_lock:
                if queued:
                    self._waiting -= 1
                if counted_running:
                    self._running -= 1
                self._set_execution_state()
            if acquired:
                self._semaphore.release()

    def _set_execution_state(self) -> None:
        if self._metrics is not None:
            self._metrics.set_queue_depth(self._waiting)
            self._metrics.set_active_requests(self._running)
