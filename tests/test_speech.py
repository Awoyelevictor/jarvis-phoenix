import base64
import json
from email.message import Message

import pytest

from app.config import Settings
from app.providers import ProviderError
from app.speech import GeminiSpeechProvider


class FakeResponse:
    def __init__(self, payload, content_type="application/json"):
        self.payload = payload
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload if isinstance(self.payload, bytes) else json.dumps(self.payload).encode()


def test_gemini_transcribes_browser_audio(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode())
        captured["api_key"] = request.get_header("X-goog-api-key")
        return FakeResponse({"candidates": [{"content": {"parts": [{"text": "  Hello ULTRON  "}]}}]})

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    provider = GeminiSpeechProvider(Settings(
        gemini_api_key="gemini-test",
        transcription_model="gemini-3.5-flash-lite",
    ))
    transcript = provider.transcribe(base64.b64encode(b"fake-audio").decode(), "audio/webm")

    assert transcript == "Hello ULTRON"
    assert captured["url"] == "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
    assert captured["api_key"] == "gemini-test"
    parts = captured["payload"]["contents"][0]["parts"]
    assert parts[1]["inline_data"]["mime_type"] == "audio/webm"
    assert parts[1]["inline_data"]["data"] == base64.b64encode(b"fake-audio").decode()


def test_gemini_transcription_requires_api_key():
    provider = GeminiSpeechProvider(Settings(gemini_api_key=""))
    with pytest.raises(ProviderError, match="GEMINI_API_KEY"):
        provider.transcribe(base64.b64encode(b"audio").decode(), "audio/webm")


def test_gemini_empty_transcript_is_reported():
    provider = GeminiSpeechProvider(Settings(gemini_api_key="gemini-test"))
    import app.speech as speech_module
    original = speech_module.urlopen
    speech_module.urlopen = lambda request, timeout: FakeResponse({"candidates": [{"content": {"parts": [{"text": " "}]}}]})
    try:
        with pytest.raises(ProviderError, match="empty transcript"):
            provider.transcribe(base64.b64encode(b"audio").decode(), "audio/webm")
    finally:
        speech_module.urlopen = original


def test_ultron_voice_api_returns_wav(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode())
        captured["api_key"] = request.get_header("X-api-key")
        return FakeResponse(b"RIFFfake-wav-data", "audio/wav")

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    provider = GeminiSpeechProvider(Settings(
        voice_api_url="https://voice.example.test",
        voice_api_key="voice-test",
    ))
    audio, mime_type = provider.synthesize("Systems online.")

    assert base64.b64decode(audio) == b"RIFFfake-wav-data"
    assert mime_type == "audio/wav"
    assert captured["url"] == "https://voice.example.test/speak"
    assert captured["api_key"] == "voice-test"
    assert captured["payload"]["text"] == "Systems online."
    assert captured["payload"]["lang"] == "eng"


def test_ultron_voice_api_requires_configuration():
    with pytest.raises(ProviderError, match="ULTRON_VOICE_API_KEY"):
        GeminiSpeechProvider(Settings()).synthesize("Hello")
