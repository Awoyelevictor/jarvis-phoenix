# Jarvis-Phoenix

Jarvis-Phoenix is a cross-platform evolution of [Jarvis-MLX](https://github.com/huwprosser/jarvis-mlx). The user-facing assistant identity is **ULTRON**. Development happens on `phoenix-upgrade`; `main` remains the preserved baseline.

## Current upgrade

- Cinematic ULTRON persona: calculating, theatrical, proud, sarcastic, with original fictional Avengers banter.
- Creator-aware tone: respectful loyalty to the operator, with playful machine arrogance.
- Persistent local memory using SQLite; current conversation reset does not erase saved memories.
- Optional approved-only cloud memory using the dedicated Supabase ULTRON project.
- Continuous browser speech recognition during ULTRON's spoken replies, with voice interruption and a theatrical silence follow-up.
- OpenRouter or Gemini chat, optional local Ollama fallback, and Gemini-generated voice output.
- Provider-specific chat keys; OpenRouter no longer accidentally receives a Gemini key.

## Voice interface

Run `python phoenix.py --ui` and open `http://127.0.0.1:8765` in Chrome. Tap once to start a voice session; the browser keeps speech recognition active while ULTRON speaks, allowing voice interruption. Tap End Session to stop.

The interface is voice-only: no visible chat transcript or text composer. Browser speech recognition availability varies by browser, operating system, and network. Continuous recognition and interruption behaviour must be tested on the target Android device. Echo filtering is best-effort; browser speech recognition may still occasionally mistake speaker output for user speech.

The microphone is active only during an explicitly started session, while the page remains active and microphone permission is granted. This is not a hidden background microphone service. Android may suspend browser microphone access when the app is backgrounded or the screen is locked.

## Memory

- Local SQLite memory is enabled by default and stored under `~/.ultron/memory.sqlite3`.
- The local owner ID is stored in `~/.ultron/owner_id`. Back up this file with the memory database if you want to preserve the local identity.
- ULTRON saves memories only when the operator explicitly says a phrase such as "Remember that I prefer concise answers."
- Say "Remember this in the cloud: ..." to explicitly approve that memory for cloud sync.
- Cloud memory sync requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in the trusted Python server environment. Get the service-role/secret key from the Supabase project dashboard; never put it in browser JavaScript, commit it to Git, or paste it into chat.
- Set the same `ULTRON_OWNER_ID` UUID on each device to share the same cloud memory identity. The owner ID is created locally by default and is not automatically shared across devices.
- Voice recordings and speaker voiceprints are not stored or uploaded.
- The Supabase table has RLS enabled and no browser-access policies. The trusted backend uses the service key. Keep the Python server bound to localhost unless you add proper authentication.

Memory management API:
- `GET /api/memories` — list local memories
- `POST /api/memory` with `{"content":"...","memory_type":"preference","cloud_sync":false}` — add a memory
- `POST /api/memory/sync` — sync explicitly approved memories
- `DELETE /api/memory` with `{"id":"..."}` — delete a local memory

## Configuration

For OpenRouter chat and Gemini speech:

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

For Supabase cloud memory, also set:

~~~bash
export SUPABASE_URL="https://yrnghosbsqwspffhsznr.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="YOUR_SUPABASE_SECRET_KEY"
# Optional: use the same UUID on another device to share this memory identity.
export ULTRON_OWNER_ID="YOUR_SHARED_UUID"
~~~

Do not commit secrets. Keep API keys in Termux environment variables or a protected local environment file. OpenRouter free model availability and rate limits can vary.

## Current limitations

- Speaker recognition / voice identity enrollment is not implemented yet. The browser recognizer transcribes speech but does not prove who is speaking.
- Voice biometrics are deliberately not uploaded or inferred from ordinary conversation.
- The interruption feature uses browser speech recognition while audio plays; echo cancellation is browser-dependent and needs real-device QA.
- Continuous listening is session-scoped and foreground-only; it is not an always-on Android background service.
- Gemini TTS format compatibility and natural audio playback need validation on the target phone.
- Vision, video understanding, offline STT/TTS, and permission-controlled computer actions remain future work.
- This is a browser/PWA foundation, not yet a native Android APK or Windows executable.

## Tests

Run `python -m pytest -v`.

## Repository layout

- `phoenix.py` — cross-platform entry point
- `app/config.py` — environment configuration
- `app/providers.py` — cloud and local chat providers
- `app/speech.py` — Gemini TTS
- `app/memory.py` — local SQLite and optional Supabase memory
- `app/assistant.py` — persona, memory context, and provider routing
- `app/webui.py` — local API and static server
- `ui/` — ULTRON voice-only browser interface
- `tests/` — cross-platform tests

## Upstream acknowledgement

This project builds on [huwprosser/jarvis-mlx](https://github.com/huwprosser/jarvis-mlx). Check the upstream repository's license and preserve all required notices before redistributing or relicensing inherited code.
