from __future__ import annotations

from fastapi.testclient import TestClient
from prometheus_client import CollectorRegistry
from prometheus_client import generate_latest

from backend.app.api.routes.ai import get_ai_gateway
from backend.app.main import create_app
from backend.app.services.ai.config import AIConfig, get_ai_config
from backend.app.services.ai.models import ProviderHealth, ProviderHealthStatus


def _config(*, enabled: bool = False) -> AIConfig:
    values = {"ORBITAL_AI_ENABLED": "true" if enabled else "false"}
    if enabled:
        values.update({
            "ORBITAL_AI_MODEL": "configured-alias",
            "ORBITAL_AI_API_KEY": "private-test-key",
            "ORBITAL_AI_BASE_URL": "http://private-llama:8080/models/path",
        })
    return AIConfig.from_env(values)


class HealthGateway:
    def __init__(self, health: ProviderHealth) -> None:
        self.result = health
        self.calls = 0

    async def health(self) -> ProviderHealth:
        self.calls += 1
        return self.result


def _client(config: AIConfig, gateway=None):
    app = create_app(metrics_registry=CollectorRegistry())
    app.dependency_overrides[get_ai_config] = lambda: config
    if gateway is not None:
        app.dependency_overrides[get_ai_gateway] = lambda: gateway
    return TestClient(app), app


def test_capabilities_disabled_are_bounded_and_do_not_expose_infrastructure():
    client, _ = _client(_config())
    with client:
        response = client.get("/ai/capabilities")
    assert response.status_code == 200
    assert response.json() == {
        "enabled": False,
        "provider": "llama.cpp",
        "model": None,
        "features": {
            "chat_completions": True,
            "structured_output": True,
            "conjunction_brief": False,
        },
        "limits": {
            "max_output_tokens": 512,
            "max_queue": 20,
            "concurrency": 1,
        },
    }
    assert "base_url" not in response.text
    assert "api_key" not in response.text


def test_health_disabled_is_200_and_does_not_call_provider():
    gateway = HealthGateway(ProviderHealth(ProviderHealthStatus.READY))
    client, _ = _client(_config(), gateway)
    with client:
        response = client.get("/ai/health")
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"
    assert gateway.calls == 0


def test_health_ready_is_200():
    gateway = HealthGateway(ProviderHealth(ProviderHealthStatus.READY, 12.4))
    client, _ = _client(_config(enabled=True), gateway)
    with client:
        response = client.get("/ai/health")
    assert response.status_code == 200
    assert response.json() == {
        "enabled": True,
        "status": "ready",
        "provider": "llama.cpp",
        "model": "configured-alias",
        "latency_ms": 12.4,
    }
    assert "private" not in response.text
    assert "/models/path" not in response.text


def test_health_loading_and_unavailable_are_503():
    for provider_status in (
        ProviderHealthStatus.LOADING,
        ProviderHealthStatus.UNAVAILABLE,
    ):
        gateway = HealthGateway(ProviderHealth(provider_status))
        client, _ = _client(_config(enabled=True), gateway)
        with client:
            response = client.get("/ai/health")
        assert response.status_code == 503
        assert response.json()["status"] == provider_status.value


def test_ai_failure_does_not_change_global_health():
    gateway = HealthGateway(ProviderHealth(ProviderHealthStatus.UNAVAILABLE))
    client, _ = _client(_config(enabled=True), gateway)
    with client:
        assert client.get("/ai/health").status_code == 503
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_documents_models_and_has_no_prompt_endpoint():
    client, _ = _client(_config())
    with client:
        schema = client.get("/openapi.json").json()
        assert client.get("/health").status_code == 200
    assert "200" in schema["paths"]["/ai/health"]["get"]["responses"]
    assert "503" in schema["paths"]["/ai/health"]["get"]["responses"]
    assert "/ready" in schema["paths"]
    assert all("prompt" not in path for path in schema["paths"])


def test_custom_app_registry_contains_ai_metrics_once():
    registry = CollectorRegistry()
    create_app(metrics_registry=registry)
    create_app(metrics_registry=registry)
    output = generate_latest(registry).decode()
    assert output.count("# HELP orbitalai_ai_runtime_ready ") == 1
    assert "orbitalai_ai_queue_capacity 20.0" in output
