"""Lightweight cross-platform browser UI and local API for ULTRON."""
from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.assistant import Assistant
from app.config import Settings
from app.providers import ProviderError
from app.speech import GeminiSpeechProvider

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
MAX_BODY_BYTES = 14 * 1024 * 1024
MAX_SPEECH_CHARS = 6000


def make_handler(assistant: Assistant):
    speech = GeminiSpeechProvider(assistant.settings)

    class UltronHandler(BaseHTTPRequestHandler):
        server_version = "ULTRON/0.3"

        def _send(self, status: int, payload: bytes, content_type: str, cache_control: str = "no-store") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", cache_control)
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                return

        def _json(self, status: int, data: dict) -> None:
            self._send(status, json.dumps(data).encode("utf-8"), "application/json; charset=utf-8")

        def _read_json(self):
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                raise ValueError("Request is empty or too large.")
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self) -> None:
            route = urlparse(self.path).path
            if route == "/api/status":
                # Keep startup status local and fast. Ollama is optional and
                # is checked only if the user needs the local fallback.
                providers = [
                    {
                        "name": "Local Ollama",
                        "ready": False,
                        "detail": "Optional local provider; checked only when a local fallback is needed.",
                    },
                    {
                        "name": "Cloud AI",
                        "ready": assistant.cloud.configured,
                        "detail": (
                            f"Cloud endpoint configured: {assistant.settings.cloud_base_url} "
                            f"(model: {assistant.settings.cloud_model}; live connectivity is checked when you send a message)."
                            if assistant.cloud.configured else "Cloud API key not configured (optional)."
                        ),
                    },
                ]
                self._json(200, {
                    "name": "ULTRON",
                    "providers": providers,
                    "cloud_model": assistant.settings.cloud_model,
                    "tts_model": assistant.settings.tts_model,
                    "tts_voice": assistant.settings.tts_voice,
                    "voice_ready": bool(
                        assistant.settings.tts_api_key
                        or ("generativelanguage.googleapis.com" in assistant.settings.cloud_base_url
                            and assistant.settings.cloud_api_key)
                    ),
                    "local_memory": True,
                    "memory_count": len(assistant.memory.list()),
                    "profile_json": assistant.profile_path.is_file(),
                    "profile_json_path": str(assistant.profile_path),
                    "cloud_memory": assistant.memory.cloud_configured,
                    "continuous_listening": True,
                    "speaker_recognition": False,
                })
                return

            if route == "/api/memories":
                self._json(200, {
                    "memories": assistant.memory.list(),
                    "cloud_sync_available": assistant.memory.cloud_configured,
                })
                return

            if route == "/favicon.ico":
                self.send_response(204)
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return

            requested = "index.html" if route in {"/", "/index.html"} else route.lstrip("/")
            target = (UI_DIR / requested).resolve()
            if UI_DIR.resolve() not in target.parents or not target.is_file():
                self._json(404, {"error": "Not found"})
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".webmanifest":
                content_type = "application/manifest+json"
            self._send(200, target.read_bytes(), f"{content_type}; charset=utf-8", "no-cache" if target.name == "index.html" else "public, max-age=3600")

        def do_POST(self) -> None:
            route = urlparse(self.path).path
            try:
                body = self._read_json()
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc) or "Invalid request body."})
                return

            if not isinstance(body, dict):
                self._json(400, {"error": "Invalid request body."})
                return

            if route == "/api/reset":
                assistant.reset_conversation()
                self._json(200, {"ok": True, "persistent_memories_preserved": True})
                return

            if route == "/api/memory":
                content = body.get("content")
                if not isinstance(content, str) or not content.strip():
                    self._json(400, {"error": "Memory content is required."})
                    return
                try:
                    item = assistant.memory.add(
                        content,
                        memory_type=body.get("memory_type", "conversation"),
                        approved_for_cloud_sync=body.get("cloud_sync") is True,
                    )
                    self._json(201, {"ok": True, "memory": item})
                except (ValueError, RuntimeError) as exc:
                    self._json(502, {"error": str(exc)})
                return

            if route == "/api/memory/sync":
                try:
                    count = assistant.memory.sync_approved()
                    self._json(200, {"ok": True, "synced": count})
                except RuntimeError as exc:
                    self._json(502, {"error": str(exc)})
                return

            if route == "/api/transcribe":
                audio=body.get("audio")
                mime_type=body.get("mime_type","audio/webm")
                if not isinstance(audio,str) or not audio:
                    self._json(400,{"error":"Microphone audio is required."})
                    return
                try:
                    transcript=speech.transcribe(audio,str(mime_type))
                    self._json(200,{"transcript":transcript})
                except ProviderError as exc:
                    print(f"[ULTRON] Microphone transcription failed: {exc}",flush=True)
                    self._json(502,{"error":str(exc)})
                return

            if route == "/api/voice":
                text = body.get("text")
                if not isinstance(text, str) or not text.strip() or len(text) > MAX_SPEECH_CHARS:
                    self._json(400, {"error": "Speech text is empty or too long."})
                    return
                try:
                    audio, mime_type = speech.synthesize(text)
                    self._json(200, {"audio": audio, "mime_type": mime_type})
                except ProviderError as exc:
                    print(f"[ULTRON] Gemini voice provider failed: {exc}", flush=True)
                    self._json(502, {"error": str(exc)})
                return

            if route == "/api/chat":
                prompt = body.get("prompt")
                if not isinstance(prompt, str) or not prompt.strip():
                    self._json(400, {"error": "Enter a message first."})
                    return
                try:
                    answer = assistant.respond(prompt)
                    self._json(200, {"reply": answer})
                except Exception as exc:
                    print(f"[ULTRON] Chat provider failed: {type(exc).__name__}: {exc}", flush=True)
                    self._json(502, {"error": str(exc)})
                return

            self._json(404, {"error": "Not found"})

        def do_DELETE(self) -> None:
            route = urlparse(self.path).path
            if route != "/api/memory":
                self._json(404, {"error": "Not found"})
                return
            try:
                body = self._read_json()
                memory_id = body.get("id") if isinstance(body, dict) else None
                if not isinstance(memory_id, str):
                    raise ValueError("Memory id is required.")
                deleted = assistant.memory.delete(memory_id)
                self._json(200, {"ok": True, "deleted": deleted})
            except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                self._json(400, {"error": str(exc)})

        def log_message(self, fmt: str, *args) -> None:
            if self.path.startswith("/api/"):
                return
            super().log_message(fmt, *args)

    return UltronHandler


def serve_ui(settings: Settings, host: str = "127.0.0.1", port: int = 8765) -> None:
    if not (UI_DIR / "index.html").is_file():
        raise RuntimeError("ULTRON UI files are missing from the ui/ directory.")
    assistant = Assistant(settings)
    server = ThreadingHTTPServer((host, port), make_handler(assistant))
    print("\nULTRON voice interface is ready.")
    print(f"Open this address in your browser: http://{host}:{port}")
    print("Local memory is enabled. Cloud memory requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
    print("Keep this process running while you use ULTRON. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nULTRON server stopped.")
    finally:
        server.server_close()
