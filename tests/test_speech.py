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



class FakeBinaryResponse(FakeResponse):
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return self.payload


def test_qwen_speech_returns_wav_from_voice_api(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["authorization"] = request.get_header("Authorization")
        return FakeBinaryResponse(b"RIFF" + b"test-wav-data")

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    settings = Settings(
        use_qwen_tts=True,
        voice_api_url="https://voice.example",
        voice_api_key="private-test-key",
    )
    audio, mime_type = GeminiSpeechProvider(settings).synthesize("Systems online.")

    import base64
    assert base64.b64decode(audio) == b"RIFFtest-wav-data"
    assert mime_type == "audio/wav"
    assert captured["url"] == "https://voice.example/v1/audio/speech"
    assert captured["payload"] == {"text": "Systems online.", "language": "English"}
    assert captured["authorization"] == "Bearer private-test-key"


def test_qwen_failure_falls_back_to_gemini(monkeypatch):
    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            from urllib.error import URLError
            raise URLError("GPU endpoint unavailable")
        return FakeResponse({
            "candidates": [{
                "content": {
                    "parts": [{
                        "inlineData": {"mimeType": "audio/wav", "data": "UklGRg=="}
                    }]
                }
            }]
        })

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    settings = Settings(
        tts_api_key="gemini-test-key",
        use_qwen_tts=True,
        voice_api_url="https://voice.example",
        voice_api_key="qwen-test-key",
    )
    audio, mime_type = GeminiSpeechProvider(settings).synthesize("Fallback test.")

    assert calls["count"] == 2
    assert audio == "UklGRg=="
    assert mime_type == "audio/wav"



def test_qwen_speech_supports_custom_colab_route(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeBinaryResponse(b"RIFF" + b"colab-wav")

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    settings = Settings(
        use_qwen_tts=True,
        voice_api_url="https://voice-tunnel.example",
        voice_api_path="/synthesize",
        voice_api_key="private-test-key",
    )
    audio, mime_type = GeminiSpeechProvider(settings).synthesize("Systems online.")

    import base64
    assert captured["url"] == "https://voice-tunnel.example/synthesize"
    assert base64.b64decode(audio) == b"RIFFcolab-wav"
    assert mime_type == "audio/wav"



def test_microphone_transcription_uses_configured_gemini_model(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({
            "candidates": [{
                "content": {"parts": [{"text": "Hello ULTRON"}]}
            }]
        })

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    provider = GeminiSpeechProvider(Settings(
        tts_api_key="test-key",
        transcription_model="gemini-3.8-flash",
    ))
    transcript = provider.transcribe("UklGRg==", "audio/webm")

    assert transcript == "Hello ULTRON"
    assert captured["url"].endswith("/models/gemini-3.8-flash:generateContent")



def test_voicebox_speech_posts_generation_and_downloads_audio(monkeypatch):
    import base64
    from app.config import Settings

    captured = []

    def fake_urlopen(request, timeout):
        captured.append((request.get_method(), request.full_url, request.data))
        if request.get_method() == "POST":
            return FakeResponse({"id": "generation-123"})
        return FakeBinaryResponse(b"RIFFvoicebox-wav")

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    settings = Settings(
        voicebox_api_url="http://127.0.0.1:17493",
        voicebox_profile_id="profile-123",
        voicebox_engine="kokoro",
        voicebox_language="en",
    )
    audio, mime_type = GeminiSpeechProvider(settings).synthesize("Systems online.")

    assert base64.b64decode(audio) == b"RIFFvoicebox-wav"
    assert mime_type == "audio/wav"
    assert captured[0][0:2] == ("POST", "http://127.0.0.1:17493/generate")
    assert json.loads(captured[0][2].decode("utf-8")) == {
        "profile_id": "profile-123",
        "text": "Systems online.",
        "language": "en",
        "engine": "kokoro",
    }
    assert captured[1][0:2] == ("GET", "http://127.0.0.1:17493/audio/generation-123")


def test_voicebox_failure_falls_back_to_gemini(monkeypatch):
    from urllib.error import URLError

    calls = {"count": 0}

    def fake_urlopen(request, timeout):
        calls["count"] += 1
        if calls["count"] == 1:
            raise URLError("Voicebox is offline")
        return FakeResponse({
            "candidates": [{
                "content": {
                    "parts": [{
                        "inlineData": {"mimeType": "audio/wav", "data": "UklGRg=="}
                    }]
                }
            }]
        })

    monkeypatch.setattr("app.speech.urlopen", fake_urlopen)
    settings = Settings(
        voicebox_api_url="http://127.0.0.1:17493",
        voicebox_profile_id="profile-123",
        tts_api_key="gemini-test-key",
    )
    audio, mime_type = GeminiSpeechProvider(settings).synthesize("Fallback test.")

    assert calls["count"] == 2
    assert audio == "UklGRg=="
    assert mime_type == "audio/wav"


def test_voicebox_configuration_is_read_from_environment(monkeypatch):
    monkeypatch.setenv("VOICEBOX_API_URL", "http://127.0.0.1:17493/")
    monkeypatch.setenv("VOICEBOX_PROFILE_ID", "profile-123")
    monkeypatch.setenv("VOICEBOX_ENGINE", "kokoro")
    monkeypatch.setenv("VOICEBOX_LANGUAGE", "en")
    settings = Settings.from_env()

    assert settings.voicebox_api_url == "http://127.0.0.1:17493"
    assert settings.voicebox_profile_id == "profile-123"
    assert settings.voicebox_engine == "kokoro"
    assert settings.voicebox_language == "en"
