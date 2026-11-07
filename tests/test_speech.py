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


def test_openrouter_whisper_transcribes_browser_audio(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode())
        captured["authorization"] = request.get_header("Authorization")
        return FakeResponse({"text": "  Hello ULTRON  ", "usage": {"cost": 0.0001}})

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    provider = GeminiSpeechProvider(Settings(
        cloud_base_url="https://openrouter.ai/api/v1",
        cloud_api_key="openrouter-test",
        transcription_model="openai/whisper-1",
    ))
    transcript = provider.transcribe(base64.b64encode(b"fake-audio").decode(), "audio/webm")

    assert transcript == "Hello ULTRON"
    assert captured["url"] == "https://openrouter.ai/api/v1/audio/transcriptions"
    assert captured["authorization"] == "Bearer openrouter-test"
    assert captured["payload"]["model"] == "openai/whisper-1"
    assert captured["payload"]["input_audio"]["format"] == "webm"


def test_openrouter_transcription_requires_openrouter_key():
    provider = GeminiSpeechProvider(Settings(
        cloud_base_url="https://openrouter.ai/api/v1",
        cloud_api_key="",
    ))
    with pytest.raises(ProviderError, match="OpenRouter API key"):
        provider.transcribe(base64.b64encode(b"audio").decode(), "audio/webm")


def test_elevenlabs_speech_returns_mp3(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode())
        captured["api_key"] = request.get_header("Xi-api-key")
        return FakeResponse(b"ID3fake-mp3", "audio/mpeg")

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    provider = GeminiSpeechProvider(Settings(
        elevenlabs_api_key="eleven-test",
        elevenlabs_voice_id="voice-123",
        elevenlabs_model_id="eleven_turbo_v2_5",
    ))
    audio, mime_type = provider.synthesize("Systems online.")

    assert base64.b64decode(audio) == b"ID3fake-mp3"
    assert mime_type == "audio/mpeg"
    assert captured["url"].startswith("https://api.elevenlabs.io/v1/text-to-speech/voice-123")
    assert captured["api_key"] == "eleven-test"
    assert captured["payload"]["text"] == "Systems online."
    assert captured["payload"]["model_id"] == "eleven_turbo_v2_5"


def test_elevenlabs_speech_requires_api_key():
    with pytest.raises(ProviderError, match="ELEVENLABS_API_KEY"):
        GeminiSpeechProvider(Settings()).synthesize("Hello")
