# Jarvis-Phoenix

Jarvis-Phoenix is a cross-platform evolution of [Jarvis-MLX](https://github.com/huwprosser/jarvis-mlx). The goal is to make a practical voice-first AI assistant available on Windows, Linux, and macOS, with local/offline AI as a first-class option and optional cloud providers.

> Development is happening on the `phoenix-upgrade` branch. The `main` branch is being kept as the preserved baseline.

## Current status

**Phase 1 foundation is in progress.** This branch now contains a separate cross-platform text assistant entry point and provider layer. The original `main.py`, MLX implementation, and existing `requirements.txt` are deliberately retained while the new runtime is built alongside them.

### Current capabilities

- Cross-platform Python entry point: `python phoenix.py`
- Optional local inference through an installed Ollama service
- Optional OpenAI-compatible cloud endpoint
- Cloud-first selection when configured, with automatic fallback to local Ollama
- Provider health check: `python phoenix.py --check`
- Core provider integration uses Python's standard library

### Not implemented yet

- Microphone capture and voice activity detection
- Speech-to-text and text-to-speech
- Desktop graphical interface
- Model manager / guided installation
- Verified Windows, Linux, and macOS packaging

Do not treat these planned features as available until they are implemented and tested.

## Requirements

- Python 3.10 or newer
- For local AI: install [Ollama](https://ollama.com/) and download a model
- Internet is only needed for initial downloads or when using a cloud provider

### Run the new foundation

```bash
python phoenix.py --check
python phoenix.py
```

The default local model is `qwen2.5:1.5b`. Download it once with:

```bash
ollama pull qwen2.5:1.5b
```

Make sure the Ollama service is running before starting Jarvis-Phoenix. Local inference can run without internet after the model has been downloaded; speed depends on available RAM and CPU/GPU.

### Optional cloud provider

Set these environment variables to use an OpenAI-compatible chat-completions endpoint:

- `PHOENIX_CLOUD_BASE_URL`
- `PHOENIX_CLOUD_API_KEY`
- `PHOENIX_CLOUD_MODEL`

The cloud provider is optional. Keep credentials in environment variables; never commit API keys.

Optional local configuration:

- `PHOENIX_LOCAL_BASE_URL` (default: `http://localhost:11434`)
- `PHOENIX_LOCAL_MODEL` (default: `qwen2.5:1.5b`)
- `PHOENIX_REQUEST_TIMEOUT` (default: `90` seconds)

## Repository layout

- `main.py` — original MLX-based assistant, retained during migration
- `phoenix.py` — new cross-platform entry point
- `app/config.py` — environment configuration
- `app/providers.py` — local and optional cloud provider adapters
- `app/assistant.py` — provider selection and fallback
- `tests/` — initial tests

## Upgrade roadmap

1. Cross-platform core and provider abstraction
2. Cross-platform audio capture and device selection
3. Speech-to-text with configurable lightweight models
4. Text-to-speech with an offline engine
5. Desktop interface, settings, and model setup
6. Windows-first testing, then Linux and macOS validation
7. Packaging, documentation, and release

## Design principles

- No mandatory paid API or subscription
- No mandatory GPU
- Local models remain available for offline use after download
- Cloud services are optional and replaceable
- Keep the original implementation available until migration is verified
- Do not claim platform support or test results without actually testing them

## Upstream acknowledgement

This project builds on the work in [huwprosser/jarvis-mlx](https://github.com/huwprosser/jarvis-mlx). The original MLX implementation is retained as a reference during the cross-platform migration. Check the upstream repository's license and preserve all required notices before redistributing or relicensing inherited code.
