from app.config import Settings


def test_default_settings_are_cross_platform():
    settings = Settings.from_env()
    assert settings.local_base_url.startswith("http")
    assert settings.local_model
    assert settings.request_timeout > 0
    assert settings.conversation_history_messages >= 2



def test_explicit_ultron_voice_url_takes_precedence_over_legacy_url(monkeypatch):
    monkeypatch.setenv("ULTRON_VOICE_API_URL", "https://qwen-tunnel.example")
    monkeypatch.setenv("TTS_API_URL", "https://old-tunnel.example")
    monkeypatch.setenv("PHOENIX_TRANSCRIPTION_MODEL", "gemini-3.8-flash")

    settings = Settings.from_env()

    assert settings.voice_api_url == "https://qwen-tunnel.example"
    assert settings.transcription_model == "gemini-3.8-flash"


def test_openrouter_is_the_default_chat_provider(monkeypatch):
    monkeypatch.delenv("PHOENIX_CLOUD_BASE_URL", raising=False)
    monkeypatch.delenv("PHOENIX_CLOUD_MODEL", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-test-key")

    settings = Settings.from_env()

    assert settings.cloud_base_url == "https://openrouter.ai/api/v1"
    assert settings.cloud_api_key == "router-test-key"
    assert settings.cloud_model == "openrouter/free"


def test_sonivox_credentials_take_precedence_over_legacy_voice_names(monkeypatch):
    monkeypatch.setenv("SONIVOX_API_URL", "https://sonivox.example")
    monkeypatch.setenv("SONIVOX_API_KEY", "sonivox-test-key")
    monkeypatch.setenv("ULTRON_VOICE_API_URL", "https://legacy.example")
    monkeypatch.setenv("ULTRON_VOICE_API_KEY", "legacy-key")

    settings = Settings.from_env()

    assert settings.voice_api_url == "https://sonivox.example"
    assert settings.voice_api_key == "sonivox-test-key"
