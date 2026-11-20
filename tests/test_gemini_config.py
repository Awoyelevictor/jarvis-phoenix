from app.config import (
    DEFAULT_OPENROUTER_MODEL,
    DEFAULT_TRANSCRIPTION_MODEL,
    OPENROUTER_BASE_URL,
    Settings,
)


def test_openrouter_is_the_default_chat_and_transcription_provider(monkeypatch):
    for name in (
        "GEMINI_API_KEY",
        "OPENROUTER_API_KEY",
        "PHOENIX_CLOUD_API_KEY",
        "PHOENIX_CLOUD_BASE_URL",
        "PHOENIX_CLOUD_MODEL",
        "PHOENIX_LOCAL_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.cloud_base_url == OPENROUTER_BASE_URL
    assert settings.cloud_model == DEFAULT_OPENROUTER_MODEL
    assert settings.transcription_model == DEFAULT_TRANSCRIPTION_MODEL == "openai/whisper-1"
    assert settings.cloud_api_key == ""
    assert settings.local_model == "llama3.2:1b"


def test_single_openrouter_key_is_loaded_for_chat_and_transcription(monkeypatch):
    monkeypatch.delenv("PHOENIX_CLOUD_BASE_URL", raising=False)
    monkeypatch.delenv("PHOENIX_CLOUD_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-test-key")

    settings = Settings.from_env()

    assert settings.cloud_api_key == "router-test-key"
    assert settings.gemini_api_key == ""


def test_explicit_cloud_settings_can_override_openrouter_defaults(monkeypatch):
    monkeypatch.setenv("PHOENIX_CLOUD_BASE_URL", "https://custom.example/v1/")
    monkeypatch.setenv("PHOENIX_CLOUD_MODEL", "custom-model")
    monkeypatch.setenv("PHOENIX_CLOUD_API_KEY", "custom-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    settings = Settings.from_env()

    assert settings.cloud_base_url == "https://custom.example/v1"
    assert settings.cloud_model == "custom-model"
    assert settings.cloud_api_key == "custom-key"
