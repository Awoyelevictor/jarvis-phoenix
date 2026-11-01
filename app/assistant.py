"""Provider orchestration and automatic fallback."""
from __future__ import annotations

from app.config import Settings
from app.providers import OllamaProvider, OpenAICompatibleProvider, ProviderError


class Assistant:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.local = OllamaProvider(settings)
        self.cloud = OpenAICompatibleProvider(settings)

    def respond(self, prompt: str) -> str:
        failures = []
        if self.cloud.configured:
            try:
                return self.cloud.chat(prompt)
            except ProviderError as exc:
                failures.append(f"cloud: {exc}")

        try:
            return self.local.chat(prompt)
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
            cloud_detail = f"Configured endpoint: {self.settings.cloud_base_url}"
        else:
            cloud_detail = "Not configured (optional)."
        return [
            ("Local Ollama", local_ok, local_detail),
            ("Optional cloud", self.cloud.configured, cloud_detail),
        ]
