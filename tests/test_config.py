from app.config import Settings


def test_default_settings_are_cross_platform():
    settings = Settings.from_env()
    assert settings.local_base_url.startswith("http")
    assert settings.local_model
    assert settings.request_timeout > 0
