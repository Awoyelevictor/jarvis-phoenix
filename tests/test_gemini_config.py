from app.config import (
    DEFAULT_GEMINI_MODEL,
    GEMINI_OPENAI_BASE_URL,
    Settings,
)


def test_gemini_is_the_default_cloud_target(monkeypatch):
    for name in (
        "GEMINI_API_KEY",
        "PHOENIX_CLOUD_API_KEY",
        "PHOENIX_CLOUD_BASE_URL",
        "PHOENIX_CLOUD_MODEL",
        "PHOENIX_LOCAL_MODEL",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings.from_env()

    assert settings.cloud_base_url == GEMINI_OPENAI_BASE_URL
    assert settings.cloud_model == DEFAULT_GEMINI_MODEL
    assert settings.cloud_api_key == ""
    assert settings.local_model == "llama3.2:1b"


def test_gemini_api_key_is_loaded_without_exposing_it(monkeypatch):
    # Isolate this Gemini-specific test from a developer's active provider.
    # Termux/.env may configure OpenRouter globally.
    for name in (
        "PHOENIX_CLOUD_BASE_URL",
        "PHOENIX_CLOUD_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    settings = Settings.from_env()

    assert settings.cloud_api_key == "test-gemini-key"


def test_explicit_cloud_settings_can_override_gemini_defaults(monkeypatch):
    monkeypatch.setenv("PHOENIX_CLOUD_BASE_URL", "https://custom.example/v1/")
    monkeypatch.setenv("PHOENIX_CLOUD_MODEL", "custom-model")
    monkeypatch.setenv("PHOENIX_CLOUD_API_KEY", "custom-key")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    settings = Settings.from_env()

    assert settings.cloud_base_url == "https://custom.example/v1"
    assert settings.cloud_model == "custom-model"
    assert settings.cloud_api_key == "custom-key"
