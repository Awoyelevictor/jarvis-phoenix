"""Small dependency-free adapters for local Ollama and OpenAI-compatible APIs."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings


class ProviderError(RuntimeError):
    """Raised when an AI provider cannot return a response."""


def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise ProviderError(str(exc)) from exc


class OllamaProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def chat(self, prompt: str) -> str:
        result = _post_json(
            f"{self.settings.local_base_url}/api/chat",
            {
                "model": self.settings.local_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            {},
            self.settings.request_timeout,
        )
        message = result.get("message", {}).get("content", "").strip()
        if not message:
            raise ProviderError("Ollama returned an empty response.")
        return message

    def check(self) -> str:
        request = Request(f"{self.settings.local_base_url}/api/tags")
        try:
            with urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            models = [item.get("name", "") for item in data.get("models", [])]
            if self.settings.local_model not in models:
                return f"Ollama is running; model '{self.settings.local_model}' is not listed. Pull it before use."
            return f"Ollama is running; model '{self.settings.local_model}' is available."
        except Exception as exc:
            return f"Ollama is not reachable at {self.settings.local_base_url}: {exc}"


class OpenAICompatibleProvider:
    """Optional cloud endpoint using the OpenAI chat-completions wire format."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.cloud_base_url and self.settings.cloud_api_key and self.settings.cloud_model)

    def chat(self, prompt: str) -> str:
        if not self.configured:
            raise ProviderError("Cloud provider is not fully configured.")
        base = self.settings.cloud_base_url
        url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        result = _post_json(
            url,
            {
                "model": self.settings.cloud_model,
                "messages": [{"role": "user", "content": prompt}],
            },
            {"Authorization": f"Bearer {self.settings.cloud_api_key}"},
            self.settings.request_timeout,
        )
        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Cloud endpoint returned an unexpected response format.") from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Cloud endpoint returned an empty response.")
        return content.strip()
