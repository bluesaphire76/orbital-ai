# OrbitalAI AI Runtime

## Runtime

OrbitalAI uses llama.cpp as its local AI inference runtime.

Ollama is not part of the supported architecture.

## Principles

- Local-first inference
- GGUF model format
- Dedicated inference service
- API and orbital engines remain independent from the AI runtime
- AI must never be authoritative for orbital propagation or collision calculations
- Models must be replaceable without changing the application architecture
- GPU acceleration is optional
- Model files are external runtime assets and must not be stored in the Git repository

## Intended architecture

OrbitalAI services
        |
Inference Gateway
        |
llama.cpp / llama-server
        |
GGUF models
