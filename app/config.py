"""Environment-based configuration for Jarvis-Phoenix."""
from __future__ import annotations

import os
from dataclasses import dataclass


GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"


@dataclass(frozen=True)
class Settings:
    local_base_url: str = "http://localhost:11434"
    local_model: str = "llama3.2:1b"
    cloud_base_url: str = GEMINI_OPENAI_BASE_URL
    cloud_api_key: str = ""
    cloud_model: str = DEFAULT_GEMINI_MODEL
    request_timeout: float = 90.0
    conversation_history_messages: int = 20

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            local_base_url=os.getenv(
                "PHOENIX_LOCAL_BASE_URL", "http://localhost:11434"
            ).rstrip("/"),
            local_model=os.getenv("PHOENIX_LOCAL_MODEL", "llama3.2:1b"),
            cloud_base_url=os.getenv(
                "PHOENIX_CLOUD_BASE_URL", GEMINI_OPENAI_BASE_URL
            ).rstrip("/"),
            cloud_api_key=(
                os.getenv("GEMINI_API_KEY", "")
                or os.getenv("PHOENIX_CLOUD_API_KEY", "")
            ),
            cloud_model=os.getenv("PHOENIX_CLOUD_MODEL", DEFAULT_GEMINI_MODEL),
            request_timeout=float(os.getenv("PHOENIX_REQUEST_TIMEOUT", "90")),
            conversation_history_messages=max(
                2, int(os.getenv("PHOENIX_HISTORY_MESSAGES", "20"))
            ),
        )
