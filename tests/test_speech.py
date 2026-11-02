import json

from app.config import DEFAULT_TTS_STYLE, Settings
from app.speech import GeminiSpeechProvider
from app.providers import ProviderError


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_gemini_speech_returns_audio_and_applies_ultron_voice_direction(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["headers"] = request.headers
        return FakeResponse({
            "candidates": [{
                "content": {
                    "parts": [{
                        "inlineData": {
                            "mimeType": "audio/wav",
                            "data": "UklGRg==",
                        }
                    }]
                }
            }]
        })

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    settings = Settings(cloud_api_key="test-key", tts_voice="Algenib")
    audio, mime_type = GeminiSpeechProvider(settings).synthesize("Hello, I am ULTRON.")

    assert audio == "UklGRg=="
    assert mime_type == "audio/wav"
    assert captured["url"].endswith("/models/gemini-3.8-flash-tts:generateContent")
    assert captured["payload"]["generationConfig"]["speechConfig"]["voiceConfig"]["prebuiltVoiceConfig"]["voiceName"] == "Algenib"
    assert captured["payload"]["generationConfig"]["responseModalities"] == ["AUDIO"]
    prompt = captured["payload"]["contents"][0]["parts"][0]["text"]
    assert DEFAULT_TTS_STYLE in prompt
    assert "<response>\nHello, I am ULTRON.\n</response>" in prompt
    assert "speech_metadata" not in captured["payload"]["contents"][0]["parts"][0]


def test_gemini_speech_requires_api_key():
    provider = GeminiSpeechProvider(Settings(cloud_api_key=""))
    try:
        provider.synthesize("Hello")
    except ProviderError as exc:
        assert "API key" in str(exc)
    else:
        raise AssertionError("Expected ProviderError")
