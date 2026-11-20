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


def test_openrouter_transcribes_browser_audio_with_same_chat_key(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode())
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return FakeResponse({"text": "  Hello ULTRON  "})

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    provider = GeminiSpeechProvider(Settings(
        cloud_base_url="https://openrouter.ai/api/v1",
        cloud_api_key="openrouter-test",
        transcription_model="openai/whisper-1",
    ))
    transcript = provider.transcribe(base64.b64encode(b"fake-audio").decode(), "audio/webm;codecs=opus")

    assert transcript == "Hello ULTRON"
    assert captured["url"] == "https://openrouter.ai/api/v1/audio/transcriptions"
    assert captured["authorization"] == "Bearer openrouter-test"
    assert captured["payload"]["model"] == "openai/whisper-1"
    assert captured["payload"]["input_audio"]["format"] == "webm"
    assert captured["payload"]["input_audio"]["data"] == base64.b64encode(b"fake-audio").decode()
    assert captured["timeout"] <= 60


def test_openrouter_transcription_requires_the_openrouter_key():
    provider = GeminiSpeechProvider(Settings(cloud_api_key=""))
    with pytest.raises(ProviderError, match="OPENROUTER_API_KEY"):
        provider.transcribe(base64.b64encode(b"audio").decode(), "audio/webm")


def test_openrouter_empty_transcript_is_reported(monkeypatch):
    monkeypatch.setattr(
        "app.speech.urlopen",
        lambda request, timeout: FakeResponse({"text": " "}),
    )
    provider = GeminiSpeechProvider(Settings(cloud_api_key="router-test"))
    with pytest.raises(ProviderError, match="empty or invalid transcript"):
        provider.transcribe(base64.b64encode(b"audio").decode(), "audio/webm")


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
    with pytest.raises(ProviderError, match="SONIVOX_API_KEY"):
        GeminiSpeechProvider(Settings()).synthesize("Hello")
