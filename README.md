# Jarvis-Phoenix

Jarvis-Phoenix is a cross-platform evolution of [Jarvis-MLX](https://github.com/huwprosser/jarvis-mlx). The goal is to make a practical AI assistant available across desktop and mobile environments, with local/offline AI as a first-class option and optional cloud providers.

> Development is happening on the `phoenix-upgrade` branch. The `main` branch is being kept as the preserved baseline.

## Current status

**Hybrid Gemini + local-provider foundation implemented; live inference and platform validation are ongoing.** The cross-platform runtime is built alongside the original MLX implementation. The original `main.py`, MLX code, and existing `requirements.txt` remain preserved during migration.

### Current capabilities

- Cross-platform Python entry point: `python phoenix.py`
- Gemini cloud configuration using `GEMINI_API_KEY`
- Gemini is tried first when an API key is configured
- Automatic fallback to local Ollama when the cloud request fails
- Local model remains optional and configurable; default future model is `llama3.2:1b`
- OpenAI-compatible chat-completions adapter, using Google's documented Gemini compatibility endpoint
- In-session conversation context shared with whichever provider responds
- Bounded conversation history, configurable with `PHOENIX_HISTORY_MESSAGES` (default: 20 messages)
- Conversation reset method for future UI integration
- Provider health check: `python phoenix.py --check`
- Core provider integration uses Python's standard library

Conversation history currently exists only in memory and is cleared when the process exits. Persistent memory, file access, vision, microphone input, speech-to-text, text-to-speech, and the desktop GUI are not implemented yet.

## Validation status

- Android/Termux: the project owner confirmed the previous six-test suite and Python compilation passed.
- Additional provider response-validation tests have now been added; run the full suite after pulling the latest branch to verify them.
- Gemini live API authentication and response generation still need to be tested using the owner's key.
- Local Llama inference is not yet installed or tested; no model download is required to configure Gemini.
- Windows, Linux, and macOS runtime testing remains pending.

## Requirements

- Python 3.10 or newer
- For Gemini cloud AI: a Gemini API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
- For optional local AI later: install [Ollama](https://ollama.com/) and download a model
- Internet is needed for Gemini requests and initial local model downloads

### Configure Gemini (cloud-first)

In Termux, set your key in the current shell:

~~~bash
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
~~~

Then check configuration and start Jarvis:

~~~bash
python phoenix.py --check
python phoenix.py
~~~

The default cloud endpoint is Google's OpenAI-compatible Gemini endpoint, and the default model is `gemini-3.8-flash`. These defaults can be overridden with `PHOENIX_CLOUD_BASE_URL` and `PHOENIX_CLOUD_MODEL`. The API key is read from `GEMINI_API_KEY`; `PHOENIX_CLOUD_API_KEY` is also accepted as a fallback. Keep keys in environment variables and never commit them to GitHub.

The health check confirms that the key is configured; it does not make a live Gemini request. A real message tests connectivity, model access, and quota. API usage and limits depend on the Google AI Studio project and model.

### Optional local Llama later

No local model needs to be downloaded now. The local provider is kept ready for a future Ollama installation. Its default model setting is `llama3.2:1b`; change it any time:

~~~bash
export PHOENIX_LOCAL_MODEL="llama3.2:1b"
~~~

After installing Ollama and downloading the selected model, start the Ollama service and Jarvis can use it as a fallback if Gemini is unavailable. You can override the local endpoint with `PHOENIX_LOCAL_BASE_URL`.

### Optional conversation settings

- `PHOENIX_REQUEST_TIMEOUT` (default: `90` seconds)
- `PHOENIX_HISTORY_MESSAGES` (default: `20` messages)

### Run tests

~~~bash
python -m pytest -v
~~~

Pytest is configured to run the cross-platform suite in `tests/`. The original Apple Silicon-specific tests remain in `test/` and are not part of the default cross-platform test run.

## Repository layout

- `main.py` — original MLX-based assistant, retained during migration
- `phoenix.py` — new cross-platform hybrid AI entry point
- `app/config.py` — environment configuration and Gemini defaults
- `app/providers.py` — local and OpenAI-compatible cloud adapters
- `app/assistant.py` — provider routing, fallback, and session context
- `tests/` — cross-platform tests
- `test/` — original MLX/TTS tests

## Upgrade roadmap

1. Cross-platform core and provider abstraction
2. Hybrid routing, local fallback, and in-session conversation context
3. Gemini cloud integration and provider reliability
4. Cross-platform audio capture and device selection
5. Speech-to-text with configurable lightweight models
6. Text-to-speech with an offline engine
7. Desktop/mobile interface, settings, and model setup
8. Vision, persistent memory, and permission-controlled tools
9. Windows-first testing, then Linux/macOS and supported mobile validation
10. Packaging, documentation, and release

## Design principles

- No mandatory paid API or subscription
- No mandatory GPU
- Local models remain available for offline use after download
- Cloud services are optional and replaceable
- Keep the original implementation available until migration is verified
- Do not claim platform support or test results without actually testing them

## Upstream acknowledgement

This project builds on the work in [huwprosser/jarvis-mlx](https://github.com/huwprosser/jarvis-mlx). The original MLX implementation is retained as a reference during the cross-platform migration. Check the upstream repository's license and preserve all required notices before redistributing or relicensing inherited code.
