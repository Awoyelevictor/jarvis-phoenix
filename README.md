# ULTRON — Jarvis Phoenix

**A cross-platform, voice-first personal AI assistant for Android phones and Windows/Linux/macOS computers.**

ULTRON is the user-facing assistant built in this repository. It combines a browser-based voice interface, cloud AI chat, server-side speech recognition, SONIVOX-generated speech, and private local memory. The project is open source so other developers can run it, inspect it, and contribute.

> **Project status:** Active development. This is a Python server with a browser/PWA interface, not a native Android APK or Windows desktop installer yet. Some browser voice features vary by device and browser.

## Features

- Voice-first browser interface with a reactive ULTRON core.
- Cloud chat through one OpenRouter API key and the OpenAI-compatible Chat Completions API.
- Spoken responses through one SONIVOX API key; no voice-key rotation or secondary TTS provider.
- Google Gemini audio transcription handles microphone speech-to-text through the server-side audio transcription API.
- SONIVOX handles all spoken responses through the configured `/speak` endpoint.
- Android and desktop use the same MediaRecorder capture path, avoiding dependence on browser-native speech recognition.
- Chat configuration uses `OPENROUTER_API_KEY`. Voice output uses `SONIVOX_API_URL` and `SONIVOX_API_KEY`. Legacy `ULTRON_VOICE_API_URL` and `ULTRON_VOICE_API_KEY` remain supported for compatibility.
- Local SQLite memory; optional, explicitly approved Supabase memory sync.
- Session-based voice recognition and interruption where supported by the browser.
- Runs locally on Android through Termux or on a computer with Python.

**Provider routing note:** OpenRouter is the default cloud chat provider. ULTRON uses exactly one configured OpenRouter key and does not rotate across keys or accounts. SONIVOX is the sole speech-output provider and uses exactly one SONIVOX key. Microphone transcription currently remains a separate Gemini service and therefore needs `GEMINI_API_KEY`; it is not used for chat or speech output. Ollama remains an optional local chat fallback.

## Quick start

You need:
- Python **3.10 or newer**
- Git
- An internet connection
- One OpenRouter API key for chat/reasoning
- One SONIVOX API URL and API key for spoken responses
- A Gemini API key only if server-side microphone transcription is enabled

The core application uses Python's standard library. You do not need to install the legacy MLX/Whisper/MeloTTS packages in `requirements.txt) to run the current ULTRON browser interface.

### 1. Get the project

Clone the development branch, which contains the current ULTRON implementation:

```bash
git clone --branch ultron-multidevice-foundation https://github.com/Awoyelevictor/jarvis-phoenix.git
cd jarvis-phoenix
```

### 2. Configure your AI keys

Choose **one** chat provider.

**OpenRouter chat:**

Linux, macOS, and Termux:
```bash
export OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"
export PHOENIX_CLOUD_BASE_URL="https://openrouter.ai/api/v1"
export PHOENIX_CLOUD_MODEL="openrouter/free"
# SONIVOX speech output
export SONIVOX_API_URL="https://YOUR-SONIVOX-API-HOST"
export SONIVOX_API_KEY="YOUR_SONIVOX_API_KEY"
# Optional Gemini microphone transcription
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
```

Gemini is only used for microphone transcription when configured. SONIVOX generates spoken responses. These services are separate from OpenRouter chat.

### 3. Start ULTRON

```bash
python phoenix.py --ui
```

Open the address printed in the terminal. By default it is:

```
http://127.0.0.1:8765
```

Keep the terminal session running while you use ULTRON. Press `Ctrl+C` in the terminal to stop the server.

## Run on Android (Termux)

1. Install **Termux** from its official F-Droid or GitHub distribution. Avoid outdated Play Store builds.
2. Open Termux and update its packages:
   ```bash
   pkg update && pkg upgrade
   pkg install python git
   ```
3. Clone the project:
   ```bash
   git clone --branch ultron-multidevice-foundation https://github.com/Awoyelevictor/jarvis-phoenix.git
   cd jarvis-phoenix
   ```
4. Set your provider keys using one of the configuration examples above. Do not share your keys or commit them to Git.
5. Start the server:
   ```bash
   python phoenix.py --ui
   ```
6. Open **Chrome** on the same phone and visit `http://127.0.0.1:8765).
7. Allow microphone permission and tap the ULTRON core to begin a voice session.

**Android notes**
- Do not close Termux while using ULTRON. Android may stop background processes; keeping Termux in the foreground or using its notification/partial-wake-lock options can help.
- Keep the browser page open and the phone unlocked for the most reliable microphone experience.
- Browser speech recognition support varies. If voice input is unavailable, try a supported Chromium-based browser.
- The server binds to localhost by default, so it is intended for use on the same device.

To avoid re-entering keys every time you open Termux, you may add your export commands to your private `~/.bashrc` file. Never put real keys in this public repository.

## Run on a laptop or desktop

### Windows (PowerShell)

1. Install Python 3.10+ and Git. During Python setup, enable **Add Python to PATH**.
2. Open PowerShell and clone the project:
   ```powershell
   git clone --branch phoenix-upgrade https://github.com/Awoyelevictor/jarvis-phoenix.git
   cd jarvis-phoenix
   ```
3. Set your keys for the current PowerShell session (choose one chat provider):
   
   OpenRouter chat + SONIVOX voice:
   ```powershell
   $env:OPENROUTER_API_KEY = "YOUR_OPENROUTER_API_KEY"
   $env:PHOENIX_CLOUD_BASE_URL = "https://openrouter.ai/api/v1"
   $env:PHOENIX_CLOUD_MODEL = "openrouter/free"
   $env:PHOENIX_TTS_MODEL = "x-ai/grok-voice-tts-1.0"
   $env:PHOENIX_TTS_VOICE = "rex"
   ```

   Or Gemini chat + voice:
   ```powershell
   $env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
   $env:PHOENIX_CLOUD_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
   $env:PHOENIX_CLOUD_MODEL = "gemini-3.8-flash"
   ```
4. Start the server:
   ```powershell
   python phoenix.py --ui
   ```
5. Open `http://127.0.0.1:8765` in Chrome or another supported browser. Allow microphone access.

### macOS or Linux

Install Python 3.10+ and Git using your operating system's package manager, then follow the **Quick start** commands in a terminal.

## Optional: Ollama local fallback

Ollama is optional. If installed and running, ULTRON can try the configured local model after the cloud provider fails.

Default settings:
- Ollama URL: `http://localhost:11434`
- Model: `llama3.2:1b`

Install Ollama for your operating system, start its service, and pull the model:

```bash
ollama pull llama3.2:1b
```

On Android/Termux, Ollama is not assumed to be installed or available. You can use ULTRON without it.

## Configuration reference

| Variable | Purpose |
|---|---|
| `OPENROUTER_API_KEY` | The single OpenRouter key used for chat/reasoning |\n| `SONIVOX_API_URL` | SONIVOX API base URL; current adapter calls `/speak` |\n| `SONIVOX_API_KEY` | The single SONIVOX speech-output key |
| `GEMINI_API_KEY` | Gemini chat key and/or Gemini TTS key |
| `PHOENIX_CLOUD_BASE_URL` | Selected OpenAI-compatible chat endpoint |
| `PHOENIX_CLOUD_MODEL` | Chat model name |
| `PHOENIX_TTS_API_KEY` | Optional separate Gemini TTS key; defaults to `GEMINI_API_KEY` |
| `PHOENIX_TTS_MODEL` | TTS model (OpenRouter default: `x-ai/grok-voice-tts-1.0`; Gemini default: `gemini-3.8-flash-tts`) |
| `PHOENIX_TTS_VOICE` | Voice ID (OpenRouter default: `rex`; Gemini default: `Algenib`) |
| `PHOENIX_TTS_STYLE` | Natural-language Gemini voice direction |
| `ULTRON_ENABLE_CLOUD_TRANSCRIPTION` | Explicitly enable cloud speech-to-text (true/false, default false) |
| `ULTRON_GEMINI_STT_MODEL` | OpenRouter transcription model (default openai/whisper-1) |
| `USE_QWEN_TTS` | Enable the remote Qwen3-TTS voice engine (`true`/`false`) |
| `ULTRON_VOICE_API_URL` | Base HTTPS URL of the Qwen voice API (keep credentials out of the URL) |
| `ULTRON_VOICE_API_PATH` | Speech route; use `/synthesize` for the Colab wrapper or `/v1/audio/speech` for ULTRON-VOICE-ENGINE |
| `ULTRON_VOICE_API_KEY` | Private bearer token accepted by the Qwen voice API |
| `PHOENIX_LOCAL_BASE_URL` | Ollama endpoint |
| `PHOENIX_LOCAL_MODEL` | Ollama model name |
| `PHOENIX_REQUEST_TIMEOUT` | Provider request timeout in seconds |
| `SUPABASE_URL` | Optional Supabase project URL for approved cloud memory |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional Supabase secret/service-role key; server-side only |
| `ULTRON_OWNER_ID` | Optional UUID to share an approved cloud-memory identity across devices |

For Supabase cloud memory, configure the Supabase URL and secret key only in the trusted Python server environment. Never expose a Supabase service-role key in browser code, screenshots, public commits, or client-side apps. Cloud sync is opt-in per memory.

## Memory and privacy

- Local memories are stored in `~/.ultron/memory.sqlite3`.
- The local owner ID is stored in `~/.ultron/owner_id`.
- ULTRON only saves a memory when the operator explicitly asks it to remember or save something.
- Cloud memory is optional and only syncs memories explicitly approved for cloud sync.
- Voice recordings and speaker voiceprints are not stored by this application.
- The default server address is `127.0.0.1), which limits access to the same device. Do not expose the server to a public network without adding authentication and appropriate security controls.

## Troubleshooting

- **No AI provider responded:** check your internet connection, selected endpoint, model name, and API key. Do not paste API keys into issues or chat.
- **OpenRouter HTTP 401:** the key may be missing, invalid, or revoked.
- **OpenRouter HTTP 429:** the selected model/provider may be rate-limited or out of quota; try again later or choose another model.
- **Gemini voice HTTP 429:** Gemini TTS quota is exhausted; wait for the quota reset or check your Google AI plan/usage. This does not necessarily mean Gemini chat is unavailable.
- **Ollama connection refused:** Ollama is not running at the configured local URL. This is expected if you have not installed it.
- **Microphone does not work:** allow browser microphone permission, keep the page in the foreground, and check whether the browser supports its speech-recognition API.
- **Port already in use:** start with another port, for example `python phoenix.py --ui --port 8766`, then open `http://127.0.0.1:8766`.

## Tests

The test suite uses pytest. Install it if you want to run the tests:

```bash
python -m pip install pytest
python -m pytest -v
```

## Repository layout

- `phoenix.py` — application entry point
- `app/config.py` — environment configuration
- `app/providers.py` — cloud and Ollama chat adapters
- `app/speech.py` — Gemini transcription and SONIVOX speech output
- `app/memory.py` — SQLite memory and optional Supabase sync
- `app/assistant.py` — ULTRON persona, memory context, and provider routing
- `app/webui.py` — local HTTP server and API
- `ui/` — browser voice interface
- `tests/` — automated tests

## Contributing

Issues and pull requests are welcome. Please:
1. Work on a feature branch rather than pushing directly to `main`.
2. Never commit API keys, credentials, personal memory databases, or other secrets.
3. Include tests for bug fixes and new behaviour.
4. Describe device/browser details when reporting voice-interface issues.

## Upstream acknowledgement

This project builds on [huwprosser/jarvis-mlx](https://github.com/huwprosser/jarvis-mlx). Check the upstream repository's license and preserve all required notices before redistributing or relicensing inherited code.


### Qwen3-TTS voice engine

The Qwen adapter is server-side. The browser continues to call the existing `/api/voice` route; the Python backend forwards speech requests to Qwen and returns WAV audio in the existing response format. Gemini remains the fallback for speech generation, and Gemini transcription remains unchanged.

For a Colab-hosted API, set `ULTRON_VOICE_API_URL` to the current Ngrok HTTPS host, `ULTRON_VOICE_API_PATH=/synthesize`, `ULTRON_VOICE_API_KEY` to the same private bearer key configured by the Colab server, and `USE_QWEN_TTS=true`. For the standalone ULTRON Voice Engine API, use `ULTRON_VOICE_API_PATH=/v1/audio/speech`.

Colab runtimes and Ngrok URLs are temporary: when the runtime stops or the tunnel URL changes, update the backend environment. Never commit real API keys or Ngrok tokens. Qwen speech synthesis currently returns a complete WAV response; this does not change the separate SSE streaming behaviour of ULTRON chat.


## Multi-device foundation (development branch)

The `ultron-multidevice-foundation` branch adds the first shared-device API layer.
The registry stores device records, one-time pairing-code hashes, and device-token
hashes in SQLite. Set `ULTRON_DEVICE_DB` to a persistent disk path when hosting
the service; without persistent storage, pairings and queued commands will not
survive an ephemeral container restart.

The owner-facing routes use the existing ULTRON server authentication:

- `POST /api/devices/pairing` — create a short-lived pairing code (default 5 minutes).
- `GET /api/devices` — list paired devices and their recent online state.
- `POST /api/devices/commands` — queue an allowed command for a paired device.
- `DELETE /api/devices/{device_id}` — revoke a paired device.

Device-agent routes use the device's bearer token:

- `POST /api/devices/pair` — exchange a one-time pairing code for a device token.
- `POST /api/devices/heartbeat` — update the device's last-seen time.
- `GET /api/device/commands` — claim the next queued command.
- `POST /api/devices/commands/complete` — submit a claimed command result.

The first command allowlist is deliberately narrow: `open_app`, `open_url`,
`run_tests`, `inspect_project`, `notify`, and `ping`. This API queues
instructions; it does not itself execute operating-system actions. Native Android
and Windows agents must validate each command locally and request confirmation
for sensitive operations before execution. Device tokens are returned only once
during pairing; store them in platform-protected storage and never log them.
