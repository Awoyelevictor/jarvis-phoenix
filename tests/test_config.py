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
