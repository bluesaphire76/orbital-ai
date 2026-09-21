from __future__ import annotations

import pytest

from backend.app.services.ai.config import AIConfig


def test_ai_config_disabled_defaults():
    config = AIConfig.from_env({})
    assert config.enabled is False
    assert config.provider == "llama.cpp"
    assert config.base_url == "http://llama-server:8080"
    assert config.model == ""
    assert config.api_key == ""
    assert config.connect_timeout_seconds == 3
    assert config.timeout_seconds == 45
    assert config.max_output_tokens == 512
    assert config.max_queue == 20
    assert config.concurrency == 1
    assert config.temperature == 0.1


def test_ai_config_enabled_and_trailing_slash_normalized():
    config = AIConfig.from_env({
        "ORBITAL_AI_ENABLED": "true",
        "ORBITAL_AI_PROVIDER": "llama.cpp",
        "ORBITAL_AI_BASE_URL": "https://ai.example.test/internal/",
        "ORBITAL_AI_API_KEY": "private-key",
        "ORBITAL_AI_MODEL": "local-alias",
        "ORBITAL_AI_CONNECT_TIMEOUT_SECONDS": "2.5",
        "ORBITAL_AI_TIMEOUT_SECONDS": "30",
        "ORBITAL_AI_MAX_OUTPUT_TOKENS": "256",
        "ORBITAL_AI_MAX_QUEUE": "4",
        "ORBITAL_AI_CONCURRENCY": "2",
        "ORBITAL_AI_TEMPERATURE": "0",
    })
    assert config.enabled is True
    assert config.base_url == "https://ai.example.test/internal"
    assert config.connect_timeout_seconds == 2.5
    assert config.temperature == 0


@pytest.mark.parametrize("value", ("1", "TRUE", "yes", "", "False"))
def test_ai_config_rejects_non_strict_boolean(value):
    with pytest.raises(ValueError, match="exactly true or false"):
        AIConfig.from_env({"ORBITAL_AI_ENABLED": value})


@pytest.mark.parametrize(
    "environment, message",
    (
        ({"ORBITAL_AI_ENABLED": "true"}, "MODEL is required"),
        ({
            "ORBITAL_AI_ENABLED": "true",
            "ORBITAL_AI_MODEL": "model",
        }, "API_KEY is required"),
        ({"ORBITAL_AI_PROVIDER": "openai"}, "must be llama.cpp"),
    ),
)
def test_ai_config_rejects_invalid_required_fields(environment, message):
    with pytest.raises(ValueError, match=message):
        AIConfig.from_env(environment)


@pytest.mark.parametrize("model", ("/models/model.gguf", r"C:\models\model.gguf"))
def test_ai_config_rejects_model_paths_from_public_alias(model):
    with pytest.raises(ValueError, match="public alias"):
        AIConfig.from_env({"ORBITAL_AI_MODEL": model})


@pytest.mark.parametrize(
    "url, message",
    (
        ("llama-server:8080", "HTTP or HTTPS"),
        ("ftp://example.test", "HTTP or HTTPS"),
        ("http://", "HTTP or HTTPS"),
        ("http://user:password@example.test", "user information"),
        ("http://example.test/path?secret=value", "query or fragment"),
        ("http://example.test/path#fragment", "query or fragment"),
        ("http://example.test:invalid", "valid URL"),
    ),
)
def test_ai_config_rejects_invalid_base_url(url, message):
    with pytest.raises(ValueError, match=message):
        AIConfig.from_env({"ORBITAL_AI_BASE_URL": url})


@pytest.mark.parametrize(
    "name,value,message",
    (
        ("ORBITAL_AI_CONNECT_TIMEOUT_SECONDS", "0", "positive finite"),
        ("ORBITAL_AI_TIMEOUT_SECONDS", "nan", "positive finite"),
        ("ORBITAL_AI_MAX_OUTPUT_TOKENS", "0", "greater than zero"),
        ("ORBITAL_AI_MAX_QUEUE", "invalid", "must be an integer"),
        ("ORBITAL_AI_CONCURRENCY", "-1", "greater than zero"),
        ("ORBITAL_AI_TEMPERATURE", "2.1", "between 0 and 2"),
        ("ORBITAL_AI_TEMPERATURE", "nan", "between 0 and 2"),
    ),
)
def test_ai_config_rejects_invalid_numeric_values(name, value, message):
    with pytest.raises(ValueError, match=message):
        AIConfig.from_env({name: value})


def test_ai_api_key_is_absent_from_repr():
    config = AIConfig.from_env({
        "ORBITAL_AI_API_KEY": "never-print-this",
    })
    assert "never-print-this" not in repr(config)
    assert "api_key" not in repr(config)
