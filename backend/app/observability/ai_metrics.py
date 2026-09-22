from __future__ import annotations

from threading import Lock
from weakref import WeakKeyDictionary

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, REGISTRY

from backend.app.services.ai.models import AITask


AI_OUTCOMES = (
    "success",
    "error",
    "timeout",
    "queue_full",
    "disabled",
    "grounding_error",
    "validation_error",
)
AI_TASKS = tuple(task.value for task in AITask)


class AIMetrics:
    def __init__(self, registry: CollectorRegistry) -> None:
        self.runtime_ready = Gauge(
            "orbitalai_ai_runtime_ready",
            "Whether the configured local AI runtime is ready",
            registry=registry,
        )
        self.requests = Counter(
            "orbitalai_ai_requests_total",
            "Local AI generation requests by bounded task and outcome",
            ("task", "outcome"),
            registry=registry,
        )
        self.duration = Histogram(
            "orbitalai_ai_request_duration_seconds",
            "Local AI generation request duration",
            ("task",),
            registry=registry,
        )
        self.queue_depth = Gauge(
            "orbitalai_ai_queue_depth",
            "Local AI generation requests waiting for an execution slot",
            registry=registry,
        )
        self.queue_capacity = Gauge(
            "orbitalai_ai_queue_capacity",
            "Configured maximum local AI waiting queue size",
            registry=registry,
        )
        self.active_requests = Gauge(
            "orbitalai_ai_active_requests",
            "Local AI generation requests holding an execution slot",
            registry=registry,
        )
        self.concurrency_capacity = Gauge(
            "orbitalai_ai_concurrency_capacity",
            "Configured maximum concurrent local AI generation requests",
            registry=registry,
        )
        self.timeouts = Counter(
            "orbitalai_ai_timeouts_total",
            "Local AI generation request timeouts",
            ("task",),
            registry=registry,
        )
        self.prompt_tokens = Counter(
            "orbitalai_ai_prompt_tokens_total",
            "Prompt tokens reported by the local AI provider",
            ("task",),
            registry=registry,
        )
        self.completion_tokens = Counter(
            "orbitalai_ai_completion_tokens_total",
            "Completion tokens reported by the local AI provider",
            ("task",),
            registry=registry,
        )

        self.runtime_ready.set(0)
        self.queue_depth.set(0)
        self.active_requests.set(0)
        for task in AI_TASKS:
            self.duration.labels(task=task)
            self.timeouts.labels(task=task)
            self.prompt_tokens.labels(task=task)
            self.completion_tokens.labels(task=task)
            for outcome in AI_OUTCOMES:
                self.requests.labels(task=task, outcome=outcome)

    def set_queue_capacity(self, capacity: int) -> None:
        self.queue_capacity.set(capacity)

    def set_queue_depth(self, depth: int) -> None:
        self.queue_depth.set(depth)

    def set_active_requests(self, active: int) -> None:
        self.active_requests.set(active)

    def set_concurrency_capacity(self, capacity: int) -> None:
        self.concurrency_capacity.set(capacity)

    def set_runtime_ready(self, ready: bool) -> None:
        self.runtime_ready.set(1 if ready else 0)

    def observe_request(
        self,
        task: AITask,
        outcome: str,
        duration_seconds: float | None = None,
    ) -> None:
        if outcome not in AI_OUTCOMES:
            raise ValueError("Unsupported AI request outcome")
        self.requests.labels(task=task.value, outcome=outcome).inc()
        if duration_seconds is not None:
            self.duration.labels(task=task.value).observe(duration_seconds)

    def observe_timeout(self, task: AITask) -> None:
        self.timeouts.labels(task=task.value).inc()

    def observe_tokens(
        self,
        task: AITask,
        prompt_tokens: int | None,
        completion_tokens: int | None,
    ) -> None:
        if prompt_tokens is not None:
            self.prompt_tokens.labels(task=task.value).inc(prompt_tokens)
        if completion_tokens is not None:
            self.completion_tokens.labels(task=task.value).inc(completion_tokens)


_instances: WeakKeyDictionary[CollectorRegistry, AIMetrics] = WeakKeyDictionary()
_instances_lock = Lock()


def get_ai_metrics(registry: CollectorRegistry = REGISTRY) -> AIMetrics:
    with _instances_lock:
        metrics = _instances.get(registry)
        if metrics is None:
            metrics = AIMetrics(registry)
            _instances[registry] = metrics
        return metrics
