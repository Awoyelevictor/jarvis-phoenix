import json

import pytest

from app.config import Settings
from app.providers import (
    OllamaProvider,
    OpenAICompatibleProvider,
    ProviderError,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def fake_urlopen_for(payload, monkeypatch):
    def fake_urlopen(*args, **kwargs):
        return FakeResponse(payload)

    monkeypatch.setattr("app.providers.urlopen", fake_urlopen)


def test_ollama_returns_trimmed_message(monkeypatch):
    fake_urlopen_for({"message": {"content": "  Hello from local AI  "}}, monkeypatch)
    provider = OllamaProvider(Settings())

    assert provider.chat([{"role": "user", "content": "Hello"}]) == "Hello from local AI"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": None},
        {"message": []},
        {"message": {"content": None}},
        {"message": {"content": "   "}},
    ],
)
def test_ollama_rejects_malformed_or_empty_response(payload, monkeypatch):
    fake_urlopen_for(payload, monkeypatch)
    provider = OllamaProvider(Settings())

    with pytest.raises(ProviderError):
        provider.chat([{"role": "user", "content": "Hello"}])


def test_cloud_returns_trimmed_message(monkeypatch):
    fake_urlopen_for(
        {"choices": [{"message": {"content": "  Hello from cloud AI  "}}]},
        monkeypatch,
    )
    settings = Settings(
        cloud_base_url="https://example.test/v1",
        cloud_api_key="test-key",
        cloud_model="test-model",
    )
    provider = OpenAICompatibleProvider(settings)

    assert provider.chat([{"role": "user", "content": "Hello"}]) == "Hello from cloud AI"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"choices": []},
        {"choices": [None]},
        {"choices": [{"message": None}]},
        {"choices": [{"message": {"content": ""}}]},
        {"choices": [{"message": {"content": 123}}]},
    ],
)
def test_cloud_rejects_malformed_or_empty_response(payload, monkeypatch):
    fake_urlopen_for(payload, monkeypatch)
    settings = Settings(
        cloud_base_url="https://example.test/v1",
        cloud_api_key="test-key",
        cloud_model="test-model",
    )
    provider = OpenAICompatibleProvider(settings)

    with pytest.raises(ProviderError):
        provider.chat([{"role": "user", "content": "Hello"}])
