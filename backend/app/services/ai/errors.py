from __future__ import annotations


class AIError(RuntimeError):
    """Base error with bounded, public-safe messages."""


class AIDisabledError(AIError):
    def __init__(self) -> None:
        super().__init__("Local AI is disabled")


class AIQueueFullError(AIError):
    def __init__(self) -> None:
        super().__init__("Local AI request queue is full")


class AITimeoutError(AIError):
    def __init__(self) -> None:
        super().__init__("Local AI request timed out")


class AIProviderUnavailableError(AIError):
    def __init__(self) -> None:
        super().__init__("Local AI provider is unavailable")


class AIInvalidResponseError(AIError):
    def __init__(self) -> None:
        super().__init__("Local AI provider returned an invalid response")
