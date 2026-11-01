# Jarvis-Phoenix

Jarvis-Phoenix is a cross-platform evolution of [Jarvis-MLX](https://github.com/huwprosser/jarvis-mlx). The assistant's user-facing identity is **ULTRON**. Development happens on `phoenix-upgrade`; `main` remains the preserved baseline.

## Current status

**Gemini-first hybrid assistant with a voice-only browser interface.** The interface uses browser speech recognition for microphone input and Gemini-generated TTS audio for ULTRON's spoken replies. It does not use the phone's built-in speech synthesizer.

### Voice interface

- Launch with `python phoenix.py --ui` and open `http://127.0.0.1:8765`
- Voice-only screen: no text composer or visible chat transcript
- Tap the central microphone to start a hands-free voice session; tap End Session to stop
- Browser speech recognition captures the user's speech; availability depends on the browser and its speech-recognition service
- Gemini 3.8 Flash TTS generates ULTRON's spoken audio using the configured voice persona
- Default voice: **Algenib**, with a deep, resonant, calm and authoritative delivery direction
- The red reactor analyses the generated playback audio for amplitude and estimated pitch, then animates in sync
- The browser does not fall back to Android or Windows device TTS
- Requires microphone permission, browser speech-recognition support, a working Gemini API key, and access to the configured Gemini chat and TTS models

### Hybrid AI engine

- Gemini cloud is preferred for conversational reasoning
- Automatic fallback to local Ollama when cloud chat fails
- Local model remains optional; default future model is `llama3.2:1b`
- In-session conversation context is held in memory and cleared when the server exits
- Python standard library used for HTTP server and Gemini REST calls

## Run on Android (Termux) or Windows

Keep the Gemini key in your current shell:

~~~bash
export GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
python phoenix.py --ui
~~~

PowerShell:

~~~powershell
$env:GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
python phoenix.py --ui
~~~

Open `http://127.0.0.1:8765` in a recent Chrome browser. Keep the Python server running. Grant microphone permission when prompted. On Android, use Chrome rather than an embedded browser if speech recognition is unavailable.

## Voice configuration

Environment overrides:

- `PHOENIX_TTS_MODEL` (default: `gemini-3.8-flash-tts`)
- `PHOENIX_TTS_VOICE` (default: `Algenib`)
- `PHOENIX_TTS_STYLE` (default: deep, resonant, calm, authoritative cinematic delivery)
- `PHOENIX_CLOUD_MODEL` (default: `gemini-3.8-flash`)
- `PHOENIX_REQUEST_TIMEOUT` (default: `90` seconds)

The chat model and TTS model are separate. A key being configured does not prove either model is reachable; a real voice turn tests both services. Gemini API usage, model availability and quota depend on the Google AI Studio project.

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
2. Gemini chat and optional local Llama fallback
3. Voice-only ULTRON browser interface
4. Gemini-generated speech and pitch-reactive reactor
5. Improve microphone capture and interruption handling
6. Offline STT/TTS options
7. Vision, persistent memory and permission-controlled tools
8. Native Android and Windows packaging after platform validation

## Upstream acknowledgement

This project builds on [huwprosser/jarvis-mlx](https://github.com/huwprosser/jarvis-mlx). Check the upstream repository's license and preserve all required notices before redistributing or relicensing inherited code.
