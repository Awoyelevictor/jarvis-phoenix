# Jarvis-Phoenix

Jarvis-Phoenix is a cross-platform evolution of [Jarvis-MLX](https://github.com/huwprosser/jarvis-mlx). The assistant's user-facing identity is **ULTRON**. Development happens on `phoenix-upgrade`; `main` remains the preserved baseline.

## Current status

**Cloud-first hybrid assistant with a voice-only browser interface.** OpenRouter or Gemini can power chat; Gemini-generated TTS remains a separate speech service. The interface uses browser speech recognition for microphone input and generated audio for ULTRON's spoken replies. It does not use the phone's built-in speech synthesizer.

### Voice interface

- Launch with `python phoenix.py --ui` and open `http://127.0.0.1:8765`
- Voice-only screen: no text composer or visible chat transcript
- Tap the central microphone to start a hands-free voice session; tap End Session to stop
- Browser speech recognition captures the user's speech; availability depends on the browser and its speech-recognition service
- Gemini 3.8 Flash TTS generates ULTRON's spoken audio using the configured voice persona
- Default voice: **Algenib**, with a deep, resonant, calm and authoritative delivery direction
- The red reactor analyses the generated playback audio for amplitude and estimated pitch, then animates in sync
- The browser does not fall back to Android or Windows device TTS
- Requires microphone permission, browser speech-recognition support, and a Gemini API key for generated speech

### AI engine

- OpenRouter or Gemini can power cloud chat through the OpenAI-compatible chat-completions API
- OpenRouter free router (`openrouter/free`) is the default model when the OpenRouter base URL is selected
- Gemini remains available as a chat provider by setting its base URL and model
- Gemini TTS uses its own key, independently from the chat provider
- Automatic fallback to local Ollama when cloud chat fails
- Local model remains optional; default future model is `llama3.2:1b`
- In-session conversation context is held in memory and cleared when the server exits
- Python standard library used for HTTP server and REST calls

## Run on Android (Termux) or Windows

### OpenRouter chat + Gemini voice

Set your OpenRouter key for chat and retain your Gemini key for voice generation:

~~~bash
export OPENROUTER_API_KEY="YOUR_OPENROUTER_API_KEY"
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
export PHOENIX_CLOUD_BASE_URL="https://openrouter.ai/api/v1"
export PHOENIX_CLOUD_MODEL="openrouter/free"
python phoenix.py --ui
~~~

PowerShell:

~~~powershell
$env:OPENROUTER_API_KEY = "YOUR_OPENROUTER_API_KEY"
$env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
$env:PHOENIX_CLOUD_BASE_URL = "https://openrouter.ai/api/v1"
$env:PHOENIX_CLOUD_MODEL = "openrouter/free"
python phoenix.py --ui
~~~

Open `http://127.0.0.1:8765` in a recent Chrome browser. Keep the Python server running. Grant microphone permission when prompted. On Android, use Chrome rather than an embedded browser if speech recognition is unavailable.

### Gemini chat instead

~~~bash
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
unset OPENROUTER_API_KEY
unset PHOENIX_CLOUD_BASE_URL
unset PHOENIX_CLOUD_MODEL
python phoenix.py --ui
~~~

## Configuration

- `OPENROUTER_API_KEY` — OpenRouter chat key (takes priority for cloud chat)
- `GEMINI_API_KEY` — Gemini TTS key; also used for chat if OpenRouter is not selected
- `PHOENIX_TTS_API_KEY` — optional separate Gemini TTS key
- `PHOENIX_CLOUD_BASE_URL` — cloud chat base URL
- `PHOENIX_CLOUD_MODEL` — chat model ID; defaults to `openrouter/free` for OpenRouter and `gemini-3.8-flash` for Gemini
- `PHOENIX_TTS_MODEL` (default: `gemini-3.8-flash-tts`)
- `PHOENIX_TTS_VOICE` (default: `Algenib`)
- `PHOENIX_TTS_STYLE` (default: deep, resonant, calm, authoritative cinematic delivery)
- `PHOENIX_REQUEST_TIMEOUT` (default: `90` seconds)

OpenRouter's free models have low rate limits and availability can vary. The free router selects from currently available free models; a successful API key setup does not guarantee every request will be served. See [OpenRouter free models](https://openrouter.ai/collections/free-models).

## Current limitations

- Browser speech recognition is browser-provided and may depend on network connectivity; it is not a custom offline STT engine.
- This is a browser/PWA foundation, not yet a native Android APK or Windows executable.
- Local/offline speech recognition and local speech generation are not yet implemented.
- Image/video vision, persistent memory, and permission-controlled computer actions remain on the roadmap.
- Voice quality and real-time performance must be validated on the target phone and Windows device before release.

## Tests

~~~bash
python -m pytest -v
~~~

The default test suite covers the cross-platform Python core. Original Apple Silicon-specific tests remain in `test/`.

## Repository layout

- `main.py` — original MLX implementation retained as reference
- `phoenix.py` — cross-platform entry point
- `app/config.py` — environment configuration
- `app/providers.py` — chat providers
- `app/speech.py` — Gemini TTS audio generation
- `app/assistant.py` — provider routing and conversation context
- `app/webui.py` — local API and static server
- `ui/` — ULTRON voice-only browser interface
- `tests/` — cross-platform tests

## Upgrade roadmap

1. Cross-platform hybrid AI core
2. OpenRouter/Gemini cloud chat and optional local Llama fallback
3. Voice-only ULTRON browser interface
4. Gemini-generated speech and pitch-reactive reactor
5. Improve microphone capture and interruption handling
6. Offline STT/TTS options
7. Vision, persistent memory and permission-controlled tools
8. Native Android and Windows packaging after platform validation

## Upstream acknowledgement

This project builds on [huwprosser/jarvis-mlx](https://github.com/huwprosser/jarvis-mlx). Check the upstream repository's license and preserve all required notices before redistributing or relicensing inherited code.