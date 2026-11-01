"""Hybrid Gemini-first provider orchestration with local fallback."""
from __future__ import annotations

from app.config import Settings
from app.providers import OllamaProvider, OpenAICompatibleProvider, ProviderError


class Assistant:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.local = OllamaProvider(settings)
        self.cloud = OpenAICompatibleProvider(settings)
        self.messages: list[dict[str, str]] = []

    def reset_conversation(self) -> None:
        """Clear the in-memory conversation history."""
        self.messages.clear()

    def _remember(self, messages: list[dict[str, str]]) -> None:
        limit = max(2, self.settings.conversation_history_messages)
        self.messages = messages[-limit:]

    def respond(self, prompt: str) -> str:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Prompt cannot be empty.")

        pending = [*self.messages, {"role": "user", "content": prompt}]
        failures = []

        if self.cloud.configured:
            try:
                answer = self.cloud.chat(pending)
                self._remember([*pending, {"role": "assistant", "content": answer}])
                return answer
            except ProviderError as exc:
                failures.append(f"cloud: {exc}")

        try:
            answer = self.local.chat(pending)
            self._remember([*pending, {"role": "assistant", "content": answer}])
            return answer
        except ProviderError as exc:
            failures.append(f"local: {exc}")

        raise ProviderError(
            "No AI provider responded. Check your Gemini API key and model access, "
            "or start Ollama with the configured local model. Details: "
            + " | ".join(failures)
        )

    def check_providers(self) -> list[tuple[str, bool, str]]:
        local_detail = self.local.check()
        local_ok = "is available." in local_detail
        if self.cloud.configured:
            cloud_detail = (
                f"Gemini-compatible endpoint configured: {self.settings.cloud_base_url} "
                "(live connectivity is checked when you send a message)."
            )
        else:
            cloud_detail = "Gemini API key not configured (optional)."
        return [
            ("Local Ollama", local_ok, local_detail),
            ("Gemini cloud", self.cloud.configured, cloud_detail),
        ]
