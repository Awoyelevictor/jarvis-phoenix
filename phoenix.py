"""Jarvis-Phoenix cross-platform hybrid AI entry point."""
from __future__ import annotations

import argparse

from app.assistant import Assistant
from app.config import Settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Jarvis-Phoenix AI assistant")
    parser.add_argument("--check", action="store_true", help="Check configured AI providers")
    args = parser.parse_args()

    settings = Settings.from_env()
    assistant = Assistant(settings)

    if args.check:
        for name, ok, detail in assistant.check_providers():
            print(f"[{'OK' if ok else 'NOT READY'}] {name}: {detail}")
        return 0

    print("\nJARVIS-PHOENIX")
    print("Gemini-first hybrid AI assistant")
    print("Gemini cloud is preferred; local Ollama/Llama is an optional fallback.")
    print("Conversation context lasts for this session only.")
    print("Type 'exit' or 'quit' to close.\n")

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
            print(f"Jarvis: {assistant.respond(prompt)}\n")
        except Exception as exc:
            print(f"Jarvis: I couldn't reach an AI provider. {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
