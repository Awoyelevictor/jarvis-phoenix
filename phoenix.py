"""Jarvis-Phoenix cross-platform hybrid AI entry point."""
from __future__ import annotations

import argparse

from app.assistant import Assistant
from app.config import Settings
from app.webui import serve_ui


def main() -> int:
    parser = argparse.ArgumentParser(description="ULTRON cross-platform AI assistant")
    parser.add_argument("--check", action="store_true", help="Check configured AI providers")
    parser.add_argument("--ui", action="store_true", help="Launch the ULTRON browser interface")
    parser.add_argument("--host", default="127.0.0.1", help="UI bind address (default: localhost only)")
    parser.add_argument("--port", type=int, default=8765, help="UI port (default: 8765)")
    args = parser.parse_args()

    settings = Settings.from_env()
    if args.ui:
        serve_ui(settings, host=args.host, port=args.port)
        return 0

    assistant = Assistant(settings)
    if args.check:
        for name, ok, detail in assistant.check_providers():
            print(f"[{'OK' if ok else 'NOT READY'}] {name}: {detail}")
        return 0

    print("\nULTRON")
    print("Gemini-first hybrid AI assistant")
    print("Gemini cloud is preferred; local Ollama/Llama is an optional fallback.")
    print("Conversation context lasts for this session only.")
    print("Type 'exit' or 'quit' to close. For the graphical interface, run: python phoenix.py --ui\n")

    while True:
        try:
            prompt = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if prompt.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break
        if not prompt:
            continue
        try:
            print(f"ULTRON: {assistant.respond(prompt)}\n")
        except Exception as exc:
            print(f"ULTRON: I couldn't reach an AI provider. {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
