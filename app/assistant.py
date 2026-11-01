"""Hybrid provider orchestration with in-session conversation context."""
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

        # Both providers receive the same pending conversation. Only commit it
        # to memory after a provider successfully responds.
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
            "No AI provider responded. Start Ollama and download the configured model, "
            "or configure an optional OpenAI-compatible cloud endpoint. Details: "
            + " | ".join(failures)
        )

    def check_providers(self) -> list[tuple[str, bool, str]]:
        local_detail = self.local.check()
        local_ok = "is available." in local_detail
        if self.cloud.configured:
            cloud_detail = (
                f"Configured endpoint: {self.settings.cloud_base_url} "
                "(connectivity is checked when you send a message)."
            )
        else:
            cloud_detail = "Not configured (optional)."
        return [
            ("Local Ollama", local_ok, local_detail),
            ("Optional cloud", self.cloud.configured, cloud_detail),
        ]
