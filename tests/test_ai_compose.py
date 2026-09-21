from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.validate_llama_cuda_runtime import (
    EXPECTED_GPU,
    RuntimeValidationError,
    validate_runtime_log,
)


ROOT = Path(__file__).resolve().parents[1]
CUDA_PATH = ROOT / "deploy/compose/compose.ai.cuda.yml"
CUDA_ENTRYPOINT_PATH = ROOT / "scripts/start_llama_cuda.sh"
CPU_PATH = ROOT / "deploy/compose/compose.ai.yml"
CORE_PATH = ROOT / "deploy/compose/compose.core.yml"


def _load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_cpu_overlay_is_absent_and_standard_api_does_not_enable_ai():
    assert not CPU_PATH.exists()
    core = _load(CORE_PATH)
    assert "ORBITAL_AI_ENABLED" not in core["services"]["api"]["environment"]
    assert "llama-server" not in core["services"]


def test_cuda_overlay_uses_only_digest_pinned_server_cuda_image():
    compose = _load(CUDA_PATH)
    assert set(compose["services"]) == {"api", "llama-server"}
    image = compose["services"]["llama-server"]["image"]
    assert image.startswith("ghcr.io/ggml-org/llama.cpp:server-cuda@sha256:")
    assert len(image.rsplit("@sha256:", 1)[1]) == 64
    assert "llama.cpp:server@" not in image


def test_cuda_overlay_requires_exactly_one_nvidia_gpu():
    llama = _load(CUDA_PATH)["services"]["llama-server"]
    devices = llama["deploy"]["resources"]["reservations"]["devices"]
    assert devices == [
        {"driver": "nvidia", "count": 1, "capabilities": ["gpu"]}
    ]
    assert "device_ids" not in devices[0]


def test_cuda_overlay_enforces_full_single_gpu_offload_without_cpu_options():
    command = _load(CUDA_PATH)["services"]["llama-server"]["command"]
    assert command[command.index("--ctx-size") + 1] == (
        "${ORBITAL_AI_CONTEXT_SIZE:-4096}"
    )
    assert command[command.index("--batch-size") + 1] == "512"
    assert command[command.index("--ubatch-size") + 1] == "128"
    assert command[command.index("--parallel") + 1] == "1"
    assert command[command.index("--n-gpu-layers") + 1] == "all"
    assert command[command.index("--split-mode") + 1] == "none"
    assert command[command.index("--main-gpu") + 1] == "0"
    assert command[command.index("--device") + 1] == "CUDA0"
    assert command[command.index("--fit") + 1] == "off"
    assert "--op-offload" in command
    assert "--kv-offload" in command
    assert command[command.index("--flash-attn") + 1] == "on"
    assert command[command.index("--reasoning") + 1] == "off"
    for prohibited in (
        "--cpu-moe",
        "--n-cpu-moe",
        "--n-cpu-ffn",
        "--no-op-offload",
    ):
        assert prohibited not in command


def test_cuda_overlay_is_private_read_only_and_fails_unconfigured_mount():
    compose = _load(CUDA_PATH)
    llama = compose["services"]["llama-server"]
    assert "ports" not in llama
    assert llama["networks"] == ["ai"]
    assert compose["networks"]["ai"]["internal"] is True
    assert llama["restart"] == "on-failure:3"
    mount, entrypoint_mount = llama["volumes"]
    assert mount["target"] == "/models"
    assert mount["read_only"] is True
    assert mount["bind"]["create_host_path"] is False
    assert llama["entrypoint"] == ["/opt/orbitalai/start-llama-cuda.sh"]
    assert entrypoint_mount["target"] == "/opt/orbitalai/start-llama-cuda.sh"
    assert entrypoint_mount["read_only"] is True
    assert llama["cap_drop"] == ["ALL"]
    assert llama["user"] == "1000:1000"
    assert "no-new-privileges:true" in llama["security_opt"]


def test_cuda_startup_gate_pins_authorized_model_integrity():
    command = _load(CUDA_PATH)["services"]["llama-server"]["command"]
    assert command[command.index("--model") + 1] == (
        "/models/Qwen3-8B-Q4_K_M.gguf"
    )
    gate = CUDA_ENTRYPOINT_PATH.read_text(encoding="utf-8")
    assert "expected_size=5027783488" in gate
    assert (
        "expected_sha256="
        "d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785"
    ) in gate
    assert 'expected_device="CUDA0: NVIDIA GeForce RTX 4070 Laptop GPU"' in gate
    assert "device_count" in gate
    assert "exec /app/llama-server" in gate


def test_cuda_overlay_enables_gateway_only_when_explicitly_added():
    api = _load(CUDA_PATH)["services"]["api"]
    environment = api["environment"]
    assert environment["ORBITAL_AI_ENABLED"] == "true"
    assert environment["ORBITAL_AI_PROVIDER"] == "llama.cpp"
    assert environment["ORBITAL_AI_BASE_URL"] == "http://llama-server:8080"
    assert set(api["networks"]) == {"app", "data", "observability", "ai"}
    assert "depends_on" not in api


def test_cuda_runtime_key_is_environment_only_not_process_argument():
    llama = _load(CUDA_PATH)["services"]["llama-server"]
    assert llama["environment"] == {
        "LLAMA_API_KEY": (
            "${ORBITAL_AI_API_KEY:?ORBITAL_AI_API_KEY is required}"
        )
    }
    assert "--api-key" not in llama["command"]


def test_cuda_overlay_requires_key_alias_and_model_directory():
    compose = _load(CUDA_PATH)
    api_environment = compose["services"]["api"]["environment"]
    llama = compose["services"]["llama-server"]
    assert ":?" in api_environment["ORBITAL_AI_API_KEY"]
    assert ":?" in api_environment["ORBITAL_AI_MODEL"]
    assert ":?" in llama["command"][llama["command"].index("--alias") + 1]
    assert ":?" in llama["volumes"][0]["source"]
    assert "UNCONFIGURED_AI_API_KEY" not in CUDA_PATH.read_text(
        encoding="utf-8"
    )


VALID_GPU_LOG = f"""
ggml_cuda_init: found 1 CUDA devices:
  Device 0: {EXPECTED_GPU}, compute capability 8.9, VMM: yes
load_tensors: offloaded 33/33 layers to GPU
load_tensors: CUDA0 model buffer size = 6112.50 MiB
llama_kv_cache_init: CUDA0 KV buffer size = 512.00 MiB
llama_init_from_model: CUDA0 compute buffer size = 180.00 MiB
srv  server is listening on http://0.0.0.0:8080
"""


def test_runtime_log_gate_accepts_only_complete_cuda_evidence():
    evidence = validate_runtime_log(VALID_GPU_LOG)
    assert evidence.gpu_count == 1
    assert evidence.gpu_name == EXPECTED_GPU
    assert evidence.offloaded_layers == evidence.total_layers == 33


def test_runtime_log_gate_accepts_current_list_devices_format():
    current_log = VALID_GPU_LOG.replace(
        "ggml_cuda_init: found 1 CUDA devices:\n"
        f"  Device 0: {EXPECTED_GPU}, compute capability 8.9, VMM: yes",
        "Available devices:\n"
        f"  CUDA0: {EXPECTED_GPU} (8187 MiB, 7054 MiB free)",
    )
    evidence = validate_runtime_log(current_log)
    assert evidence.gpu_count == 1
    assert evidence.gpu_name == EXPECTED_GPU


@pytest.mark.parametrize(
    "invalid_log",
    (
        VALID_GPU_LOG.replace("found 1 CUDA devices", "found 2 CUDA devices"),
        VALID_GPU_LOG + f"  CUDA1: {EXPECTED_GPU} (4096 MiB free)\n",
        VALID_GPU_LOG.replace(EXPECTED_GPU, "NVIDIA Other GPU"),
        VALID_GPU_LOG.replace("33/33", "32/33"),
        VALID_GPU_LOG.replace("CUDA0 model buffer", "CPU model buffer"),
        VALID_GPU_LOG.replace("CUDA0 KV buffer", "CPU KV buffer"),
        VALID_GPU_LOG.replace("CUDA0 compute buffer", "CPU compute buffer"),
        VALID_GPU_LOG + "CPU KV buffer size = 32.00 MiB\n",
        VALID_GPU_LOG + "CPU compute buffer size = 8.00 MiB\n",
        VALID_GPU_LOG.replace("server is listening", "server is starting"),
    ),
)
def test_runtime_log_gate_fails_closed_without_full_gpu_evidence(invalid_log):
    with pytest.raises(RuntimeValidationError):
        validate_runtime_log(invalid_log)
