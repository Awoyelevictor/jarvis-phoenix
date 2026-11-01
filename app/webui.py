"""Lightweight cross-platform browser UI for ULTRON."""
from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.assistant import Assistant
from app.config import Settings

UI_DIR = Path(__file__).resolve().parent.parent / "ui"
MAX_BODY_BYTES = 64 * 1024


def make_handler(assistant: Assistant):
    class UltronHandler(BaseHTTPRequestHandler):
        server_version = "ULTRON/0.1"

        def _send(self, status: int, payload: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def _json(self, status: int, data: dict) -> None:
            self._send(
                status,
                json.dumps(data).encode("utf-8"),
                "application/json; charset=utf-8",
            )

        def do_GET(self) -> None:
            route = urlparse(self.path).path
            if route == "/api/status":
                providers = [
                    {"name": name, "ready": ready, "detail": detail}
                    for name, ready, detail in assistant.check_providers()
                ]
                self._json(200, {
                    "name": "ULTRON",
                    "providers": providers,
                    "cloud_model": assistant.settings.cloud_model,
                    "local_model": assistant.settings.local_model,
                })
                return

            requested = "index.html" if route in {"/", "/index.html"} else route.lstrip("/")
            target = (UI_DIR / requested).resolve()
            if UI_DIR.resolve() not in target.parents or not target.is_file():
                self._json(404, {"error": "Not found"})
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if target.suffix == ".webmanifest":
                content_type = "application/manifest+json"
            self._send(200, target.read_bytes(), f"{content_type}; charset=utf-8")

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/api/chat":
                self._json(404, {"error": "Not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_BODY_BYTES:
                    self._json(413, {"error": "Message is empty or too large."})
                    return
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                prompt = body.get("prompt") if isinstance(body, dict) else None
                if not isinstance(prompt, str) or not prompt.strip():
                    self._json(400, {"error": "Enter a message first."})
                    return
                answer = assistant.respond(prompt)
                self._json(200, {"reply": answer})
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._json(400, {"error": "Invalid request body."})
            except Exception as exc:
                self._json(502, {"error": str(exc)})

        def log_message(self, fmt: str, *args) -> None:
            # Keep normal chat content out of the terminal log.
            if self.path.startswith("/api/"):
                return
            super().log_message(fmt, *args)

    return UltronHandler


def serve_ui(settings: Settings, host: str = "127.0.0.1", port: int = 8765) -> None:
    if not (UI_DIR / "index.html").is_file():
        raise RuntimeError("ULTRON UI files are missing from the ui/ directory.")
    assistant = Assistant(settings)
    server = ThreadingHTTPServer((host, port), make_handler(assistant))
    print("\nULTRON interface is ready.")
    print(f"Open this address in your browser: http://{host}:{port}")
    print("Keep this process running while you use ULTRON. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nULTRON server stopped.")
    finally:
        server.server_close()
