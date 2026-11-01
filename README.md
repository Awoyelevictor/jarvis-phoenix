# Jarvis-Phoenix

Jarvis-Phoenix is a cross-platform evolution of [Jarvis-MLX](https://github.com/huwprosser/jarvis-mlx). The assistant's new user-facing identity is **ULTRON**. The goal is a practical AI assistant across desktop and mobile environments, with local/offline AI as a first-class option and optional cloud providers.

> Development is happening on the `phoenix-upgrade` branch. The `main` branch is being kept as the preserved baseline.

## Current status

**Gemini-first hybrid engine and first responsive ULTRON browser interface implemented; live inference and platform validation are ongoing.** The original MLX implementation remains alongside the cross-platform runtime.

### Current capabilities

- Cross-platform Python entry point: `python phoenix.py`
- Responsive ULTRON browser UI: `python phoenix.py --ui`
- UI works in a modern browser on Android and Windows; install it as a PWA where browser support allows
- ULTRON dark metallic interface with silver surfaces and red accents
- Gemini cloud configuration using `GEMINI_API_KEY`
- Gemini is tried first when an API key is configured
- Automatic fallback to local Ollama when the cloud request fails
- Local model remains optional and configurable; default future model is `llama3.2:1b`
- OpenAI-compatible chat-completions adapter using Google's documented Gemini compatibility endpoint
- In-session conversation context shared with whichever provider responds
- Bounded conversation history, configurable with `PHOENIX_HISTORY_MESSAGES` (default: 20 messages)
- Provider health check: `python phoenix.py --check`
- Core provider integration and UI server use Python's standard library

Conversation history currently exists only in memory and is cleared when the process exits. Persistent memory, image/video vision, microphone input, speech-to-text, text-to-speech, and permission-controlled tools are not implemented yet.

## Run the ULTRON interface

Keep the Gemini key in your current shell, then run:

~~~bash
python phoenix.py --check
python phoenix.py --ui
~~~

Open **http://127.0.0.1:8765** in Chrome or another modern browser on the same device. On Android with Termux, leave the Termux server running while using the browser. On Windows, the same command starts the local interface; open the address in your browser. The server binds to localhost by default so it is not exposed to the local network.

To choose another port:

~~~bash
python phoenix.py --ui --port 9000
~~~

The interface is responsive and can be installed as a PWA from the browser's install/add-to-home-screen menu. The UI shell may be cached, but live AI chat still requires the Python server and an available provider.

## Configure Gemini (cloud-first)

In Termux or a Windows terminal, set your key in the current shell:

~~~bash
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
~~~

In PowerShell, use:

~~~powershell
$env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
~~~

The default cloud endpoint is Google's OpenAI-compatible Gemini endpoint, and the default model is `gemini-3.8-flash`. These defaults can be overridden with `PHOENIX_CLOUD_BASE_URL` and `PHOENIX_CLOUD_MODEL`. The API key is read from `GEMINI_API_KEY`; `PHOENIX_CLOUD_API_KEY` is also accepted as a fallback. Keep keys in environment variables and never commit them to GitHub.

The health check confirms that the key is configured; it does not make a live Gemini request. Sending a chat message tests connectivity, model access, and quota. API usage and limits depend on the Google AI Studio project and model.

## Optional local Llama later

No local model needs to be downloaded now. The local provider is kept ready for a future Ollama installation. Its default model setting is `llama3.2:1b`; change it with:

~~~bash
export PHOENIX_LOCAL_MODEL="llama3.2:1b"
~~~

After installing Ollama and downloading the selected model, start the Ollama service and ULTRON can use it as a fallback if Gemini is unavailable. You can override the local endpoint with `PHOENIX_LOCAL_BASE_URL`.

## Optional conversation settings

- `PHOENIX_REQUEST_TIMEOUT` (default: `90` seconds)
- `PHOENIX_HISTORY_MESSAGES` (default: `20` messages)

## Run tests

~~~bash
python -m pytest -v
~~~

Pytest is configured to run the cross-platform suite in `tests/`. The original Apple Silicon-specific tests remain in `test/` and are not part of the default cross-platform test run.

## Repository layout

- `main.py` — original MLX-based assistant, retained during migration
- `phoenix.py` — cross-platform entry point and UI launcher
- `app/config.py` — environment configuration and Gemini defaults
- `app/providers.py` — local and OpenAI-compatible cloud adapters
- `app/assistant.py` — provider routing, fallback, and session context
- `app/webui.py` — lightweight local web server for the browser UI
- `ui/` — responsive ULTRON PWA interface
- `tests/` — cross-platform tests
- `test/` — original MLX/TTS tests

## Upgrade roadmap

1. Cross-platform core and provider abstraction
2. Hybrid routing, local fallback, and in-session conversation context
3. Gemini cloud integration and provider reliability
4. Responsive ULTRON interface for Android and Windows
5. Cross-platform audio capture and device selection
6. Speech-to-text with configurable lightweight models
7. Text-to-speech with an offline engine
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
