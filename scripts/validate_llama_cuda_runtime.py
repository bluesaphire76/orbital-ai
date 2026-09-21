from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


EXPECTED_GPU = "NVIDIA GeForce RTX 4070 Laptop GPU"


class RuntimeValidationError(RuntimeError):
    """Raised when llama.cpp runtime evidence does not prove GPU-only use."""


@dataclass(frozen=True, slots=True)
class CUDARuntimeEvidence:
    gpu_count: int
    gpu_name: str
    offloaded_layers: int
    total_layers: int
    model_buffer_mib: float
    kv_buffer_mib: float
    compute_buffer_mib: float
    server_ready: bool


def _positive_buffer(log_text: str, buffer_name: str) -> float | None:
    matches = re.findall(
        rf"CUDA0\s+{buffer_name}\s+buffer size\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*MiB",
        log_text,
        flags=re.IGNORECASE,
    )
    if not matches:
        return None
    value = float(matches[-1])
    return value if value > 0 else None


def validate_runtime_log(
    log_text: str,
    *,
    expected_gpu: str = EXPECTED_GPU,
) -> CUDARuntimeEvidence:
    device_count_matches = re.findall(
        r"found\s+(\d+)\s+CUDA devices?",
        log_text,
        flags=re.IGNORECASE,
    )
    listed_device_indices = re.findall(
        r"\sCUDA(\d+):",
        log_text,
        flags=re.IGNORECASE,
    )
    reported_device_counts = {int(value) for value in device_count_matches}
    listed_devices = set(listed_device_indices)
    no_device_evidence = not reported_device_counts and not listed_devices
    conflicting_reported_count = (
        bool(reported_device_counts) and reported_device_counts != {1}
    )
    conflicting_listed_devices = (
        bool(listed_devices) and listed_devices != {"0"}
    )
    if (
        no_device_evidence
        or conflicting_reported_count
        or conflicting_listed_devices
    ):
        raise RuntimeValidationError(
            "Runtime log does not prove exactly one CUDA device"
        )

    device_matches = re.findall(
        r"(?:Device\s+0|CUDA0):\s*([^,\r\n(]+)",
        log_text,
        flags=re.IGNORECASE,
    )
    if not device_matches or device_matches[-1].strip() != expected_gpu:
        raise RuntimeValidationError(
            "Runtime log does not identify the required NVIDIA GPU"
        )

    layer_matches = re.findall(
        r"offloaded\s+(\d+)\s*/\s*(\d+)\s+layers\s+to\s+GPU",
        log_text,
        flags=re.IGNORECASE,
    )
    if not layer_matches:
        raise RuntimeValidationError(
            "Runtime log does not report model layer offload"
        )
    offloaded_layers, total_layers = map(int, layer_matches[-1])
    if total_layers <= 0 or offloaded_layers != total_layers:
        raise RuntimeValidationError(
            "Runtime log reports partial model layer offload"
        )

    model_buffer = _positive_buffer(log_text, "model")
    kv_buffer = _positive_buffer(log_text, "KV")
    compute_buffer = _positive_buffer(log_text, "compute")
    if model_buffer is None:
        raise RuntimeValidationError(
            "Runtime log does not prove CUDA model buffer allocation"
        )
    if kv_buffer is None:
        raise RuntimeValidationError(
            "Runtime log does not prove CUDA KV cache allocation"
        )
    if compute_buffer is None:
        raise RuntimeValidationError(
            "Runtime log does not prove CUDA operation offload"
        )

    cpu_kv_matches = re.findall(
        r"CPU(?:_Mapped)?\s+KV\s+buffer size\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*MiB",
        log_text,
        flags=re.IGNORECASE,
    )
    if any(float(value) > 0 for value in cpu_kv_matches):
        raise RuntimeValidationError(
            "Runtime log reports a CPU-resident KV cache"
        )

    cpu_compute_matches = re.findall(
        r"CPU(?:_Mapped)?\s+compute\s+buffer size\s*=\s*"
        r"([0-9]+(?:\.[0-9]+)?)\s*MiB",
        log_text,
        flags=re.IGNORECASE,
    )
    if any(float(value) > 0 for value in cpu_compute_matches):
        raise RuntimeValidationError(
            "Runtime log reports a CPU-resident compute buffer"
        )

    ready_patterns = (
        r"server\s+is\s+listening",
        r"server\s+listening\s+on",
        r"llama_server:\s+listening\s+on",
        r"all\s+slots\s+are\s+idle",
    )
    if not any(
        re.search(pattern, log_text, flags=re.IGNORECASE)
        for pattern in ready_patterns
    ):
        raise RuntimeValidationError(
            "Runtime log does not prove that the server became ready"
        )

    return CUDARuntimeEvidence(
        gpu_count=1,
        gpu_name=expected_gpu,
        offloaded_layers=offloaded_layers,
        total_layers=total_layers,
        model_buffer_mib=model_buffer,
        kv_buffer_mib=kv_buffer,
        compute_buffer_mib=compute_buffer,
        server_ready=True,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate bounded llama.cpp startup logs for OrbitalAI's "
            "NVIDIA-only runtime gate."
        )
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Read logs from this file instead of standard input.",
    )
    parser.add_argument(
        "--expected-gpu",
        default=EXPECTED_GPU,
        help="Exact GPU name required in llama.cpp device discovery logs.",
    )
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    log_text = (
        arguments.log_file.read_text(encoding="utf-8")
        if arguments.log_file is not None
        else sys.stdin.read()
    )
    try:
        evidence = validate_runtime_log(
            log_text,
            expected_gpu=arguments.expected_gpu,
        )
    except RuntimeValidationError as exc:
        print(f"GPU-only runtime gate: FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "pass", **asdict(evidence)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
