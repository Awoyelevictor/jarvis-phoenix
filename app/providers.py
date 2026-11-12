"""Small dependency-free adapters for local Ollama and OpenAI-compatible APIs."""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings


class ProviderError(RuntimeError):
    """Raised when an AI provider cannot return a response."""


def _post_json(url: str, payload: dict, headers: dict, timeout: float) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            result: Any = json.loads(response.read().decode("utf-8"))
        if not isinstance(result, dict):
            raise ProviderError("Provider returned an unexpected response format.")
        return result
    except ProviderError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        raise ProviderError(str(exc)) from exc


class OllamaProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    def chat(self, messages: list[dict[str, str]]) -> str:
        result = _post_json(
            f"{self.settings.local_base_url.rstrip('/')}/api/chat",
            {
                "model": self.settings.local_model,
                "messages": messages,
                "stream": False,
            },
            {},
            self.settings.request_timeout,
        )
        message = result.get("message")
        if not isinstance(message, dict):
            raise ProviderError("Ollama returned an unexpected response format.")
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Ollama returned an empty or invalid response.")
        return content.strip()

    def check(self) -> str:
        request = Request(f"{self.settings.local_base_url.rstrip('/')}/api/tags")
        try:
            with urlopen(request, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Unexpected response format")
            model_items = data.get("models", [])
            if not isinstance(model_items, list):
                raise ValueError("Unexpected models list")
            models = [
                item.get("name", "")
                for item in model_items
                if isinstance(item, dict)
            ]
            if self.settings.local_model not in models:
                return (
                    f"Ollama is running; model '{self.settings.local_model}' "
                    "is not listed. Pull it before use."
                )
            return f"Ollama is running; model '{self.settings.local_model}' is available."
        except Exception as exc:
            return f"Ollama is not reachable at {self.settings.local_base_url}: {exc}"


class OpenAICompatibleProvider:
    """Optional cloud endpoint using the OpenAI chat-completions wire format."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.cloud_base_url
            and self.settings.cloud_api_key
            and self.settings.cloud_model
        )

    def chat(self, messages: list[dict[str, str]]) -> str:
        if not self.configured:
            raise ProviderError("Cloud provider is not fully configured.")
        base = self.settings.cloud_base_url.rstrip("/")
        url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        result = _post_json(
            url,
            {
                "model": self.settings.cloud_model,
                "messages": messages,
            },
            {"Authorization": f"Bearer {self.settings.cloud_api_key}"},
            self.settings.request_timeout,
        )
        try:
            choices = result["choices"]
            if not isinstance(choices, list) or not choices:
                raise TypeError("Missing choices")
            choice = choices[0]
            if not isinstance(choice, dict):
                raise TypeError("Invalid choice")
            message = choice["message"]
            if not isinstance(message, dict):
                raise TypeError("Invalid message")
            content = message["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                "Cloud endpoint returned an unexpected response format."
            ) from exc
        if not isinstance(content, str) or not content.strip():
            raise ProviderError("Cloud endpoint returned an empty or invalid response.")
        return content.strip()


    def stream_chat(self, messages: list[dict[str, str]]):
        """Yield OpenAI-compatible content deltas as they arrive from the provider."""
        if not self.configured:
            raise ProviderError("Cloud provider is not fully configured.")
        base = self.settings.cloud_base_url.rstrip("/")
        url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
        payload = {
            "model": self.settings.cloud_model,
            "messages": messages,
            "stream": True,
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.cloud_api_key}",
                "Accept": "text/event-stream",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.request_timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or line.startswith(":"):
                        continue
                    if line.startswith("data:"):
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            event = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        choices = event.get("choices", [])
                        if not isinstance(choices, list) or not choices:
                            continue
                        choice = choices[0]
                        delta = choice.get("delta", {}) if isinstance(choice, dict) else {}
                        content = delta.get("content") if isinstance(delta, dict) else None
                        if isinstance(content, str) and content:
                            yield content
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ProviderError(str(exc)) from exc
