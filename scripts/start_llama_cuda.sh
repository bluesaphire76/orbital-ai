#!/bin/sh
set -eu

model_path=/models/Qwen3-8B-Q4_K_M.gguf
expected_size=5027783488
expected_sha256=d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785
expected_device="CUDA0: NVIDIA GeForce RTX 4070 Laptop GPU"

device_output=$(/app/llama-server --list-devices 2>&1) || {
    echo "llama.cpp startup gate: CUDA device discovery failed" >&2
    exit 1
}
printf '%s\n' "$device_output"
device_count=$(printf '%s\n' "$device_output" | grep -c '^  CUDA' || true)
if [ "$device_count" != 1 ] || ! printf '%s\n' "$device_output" \
    | grep -Fq "  $expected_device "; then
    echo "llama.cpp startup gate: required CUDA device is unavailable" >&2
    exit 1
fi

if [ ! -f "$model_path" ]; then
    echo "llama.cpp startup gate: authorized model is missing" >&2
    exit 1
fi

actual_size=$(stat -c %s "$model_path")
if [ "$actual_size" != "$expected_size" ]; then
    echo "llama.cpp startup gate: authorized model size mismatch" >&2
    exit 1
fi

actual_sha256=$(sha256sum "$model_path")
actual_sha256=${actual_sha256%% *}
if [ "$actual_sha256" != "$expected_sha256" ]; then
    echo "llama.cpp startup gate: authorized model checksum mismatch" >&2
    exit 1
fi

exec /app/llama-server "$@"
