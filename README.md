# Jarvis-Phoenix

Jarvis-Phoenix is a cross-platform evolution of [Jarvis-MLX](https://github.com/huwprosser/jarvis-mlx). The goal is to make a practical AI assistant available across desktop and mobile environments, with local/offline AI as a first-class option and optional cloud providers.

> Development is happening on the `phoenix-upgrade` branch. The `main` branch is being kept as the preserved baseline.

## Current status

**Phase 2 hybrid AI engine implemented; platform runtime validation is ongoing.** The new cross-platform runtime is built alongside the original MLX implementation. The original `main.py`, MLX code, and existing `requirements.txt` remain preserved during migration.

### Current capabilities

- Cross-platform Python entry point: `python phoenix.py`
- Hybrid provider routing: configured cloud endpoint is tried first
- Automatic fallback to local Ollama when the cloud request fails
- Local inference through an installed Ollama service
- Optional OpenAI-compatible chat-completions endpoint
- In-session conversation context shared with whichever provider responds
- Bounded conversation history, configurable with `PHOENIX_HISTORY_MESSAGES` (default: 20 messages)
- Conversation reset method for future UI integration
- Provider health check: `python phoenix.py --check`
- Core provider integration uses Python's standard library

Conversation history currently exists only in memory and is cleared when the process exits. Persistent memory, file access, vision, microphone input, speech-to-text, text-to-speech, and the desktop GUI are not implemented yet.

### Validation status

- Android/Termux: Python compilation and the initial configuration test were reported passing by the project owner.
- The original MLX tests are retained in `test/`; pytest is configured to discover the cross-platform suite in `tests/` by default.
- New hybrid routing tests have been added, but they must be executed before their results can be claimed.
- Windows, Linux, macOS, and actual local/cloud model inference still require runtime testing.

## Requirements

- Python 3.10 or newer
- For local AI: install [Ollama](https://ollama.com/) and download a model
- For cloud AI: credentials for an OpenAI-compatible endpoint (optional)
- Internet is needed for initial model downloads or cloud requests

### Run the assistant

~~~bash
python phoenix.py --check
python phoenix.py
~~~

The default local model is `qwen2.5:1.5b`. Download it once with:

~~~bash
ollama pull qwen2.5:1.5b
~~~

Make sure the Ollama service is running before starting Jarvis-Phoenix. Local inference can run without internet after the model has been downloaded; speed depends on available RAM and CPU/GPU.

### Optional cloud provider

Set these environment variables to use an OpenAI-compatible chat-completions endpoint:

- `PHOENIX_CLOUD_BASE_URL`
- `PHOENIX_CLOUD_API_KEY`
- `PHOENIX_CLOUD_MODEL`

When all three are set, Jarvis tries the cloud endpoint first and falls back to local Ollama if the cloud request fails. Keep credentials in environment variables; never commit API keys. The `--check` command reports whether cloud settings are configured; it does not make a live cloud request.

### Optional local and conversation settings

- `PHOENIX_LOCAL_BASE_URL` (default: `http://localhost:11434`)
- `PHOENIX_LOCAL_MODEL` (default: `qwen2.5:1.5b`)
- `PHOENIX_REQUEST_TIMEOUT` (default: `90` seconds)
- `PHOENIX_HISTORY_MESSAGES` (default: `20` messages)

### Run tests

Install pytest if needed, then run:

~~~bash
python -m pytest -v
~~~

Pytest is configured to run the cross-platform suite in `tests/`. The original Apple Silicon-specific tests remain in `test/` and are not part of the default cross-platform test run.

## Repository layout

- `main.py` — original MLX-based assistant, retained during migration
- `phoenix.py` — new cross-platform hybrid AI entry point
- `app/config.py` — environment configuration
- `app/providers.py` — local and optional cloud provider adapters
- `app/assistant.py` — provider routing, fallback, and session context
- `tests/` — cross-platform tests
- `test/` — original MLX/TTS tests

## Upgrade roadmap

1. Cross-platform core and provider abstraction
2. Hybrid routing, local fallback, and in-session conversation context
3. Cross-platform audio capture and device selection
4. Speech-to-text with configurable lightweight models
5. Text-to-speech with an offline engine
6. Desktop/mobile interface, settings, and model setup
7. Vision, persistent memory, and permission-controlled tools
8. Windows-first testing, then Linux/macOS and supported mobile validation
9. Packaging, documentation, and release

## Design principles

- No mandatory paid API or subscription
- No mandatory GPU
- Local models remain available for offline use after download
- Cloud services are optional and replaceable
- Keep the original implementation available until migration is verified
- Do not claim platform support or test results without actually testing them

## Upstream acknowledgement

This project builds on the work in [huwprosser/jarvis-mlx](https://github.com/huwprosser/jarvis-mlx). The original MLX implementation is retained as a reference during the cross-platform migration. Check the upstream repository's license and preserve all required notices before redistributing or relicensing inherited code.
