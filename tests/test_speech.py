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


def test_sonivox_developer_api_returns_audio_from_signed_url(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, request.get_method(), timeout))
        if request.full_url == "https://sonivox.example.test/health":
            return FakeResponse({"status": "ok"})
        if request.get_method() == "POST":
            assert request.get_header("Authorization") == "Bearer voice-test"
            assert request.get_header("Accept") == "application/json"
            assert json.loads(request.data.decode()) == {"text": "Systems online.", "lang": "eng"}
            return FakeResponse({"audio_url": "https://storage.example.test/signed.wav"})
        return FakeResponse(b"RIFFfake-wav-data", "audio/wav")

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    provider = GeminiSpeechProvider(Settings(
        voice_api_url="https://sonivox.example.test",
        voice_api_key="voice-test",
        voice_api_path="/v1/speech",
    ))
    audio, mime_type = provider.synthesize("Systems online.")
    assert base64.b64decode(audio) == b"RIFFfake-wav-data"
    assert mime_type == "audio/wav"
    assert calls[0][0] == "https://sonivox.example.test/health"
    assert calls[1][0] == "https://sonivox.example.test/v1/speech"
    assert calls[2][0] == "https://storage.example.test/signed.wav"
    assert calls[1][2] >= 300 and calls[2][2] >= 300


def test_settings_load_sonivox_environment(monkeypatch):
    monkeypatch.setenv("SONIVOX_API_URL", "https://sonivox.example.test")
    monkeypatch.setenv("SONIVOX_API_KEY", "voice-test")
    settings = Settings.from_env()
    assert settings.voice_api_url == "https://sonivox.example.test"
    assert settings.voice_api_key == "voice-test"
    assert settings.voice_api_path == "/v1/speech"
