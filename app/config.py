"""Environment-based configuration for ULTRON."""
from __future__ import annotations

import os
from dataclasses import dataclass


GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_OPENROUTER_MODEL = "openrouter/free"
DEFAULT_TTS_MODEL = "gemini-3.8-flash-tts"


@dataclass(frozen=True)
class Settings:
    local_base_url: str = "http://localhost:11434"
    local_model: str = "llama3.2:1b"
    cloud_base_url: str = GEMINI_OPENAI_BASE_URL
    cloud_api_key: str = ""
    cloud_model: str = DEFAULT_GEMINI_MODEL
    tts_api_key: str = ""
    tts_model: str = DEFAULT_TTS_MODEL
    tts_voice: str = "Algenib"
    tts_style: str = "Deep, resonant, calm and authoritative cinematic delivery. Natural human cadence, measured pace, subtle warmth, clear articulation, and thoughtful pauses."
    request_timeout: float = 90.0
    conversation_history_messages: int = 20
    memory_db_path: str = ""
    memory_owner_id: str = ""
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        cloud_base_url = os.getenv("PHOENIX_CLOUD_BASE_URL", GEMINI_OPENAI_BASE_URL).rstrip("/")
        if "openrouter.ai" in cloud_base_url:
            cloud_api_key = os.getenv("OPENROUTER_API_KEY", "") or os.getenv("PHOENIX_CLOUD_API_KEY", "")
        else:
            cloud_api_key = os.getenv("PHOENIX_CLOUD_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        return cls(
            local_base_url=os.getenv("PHOENIX_LOCAL_BASE_URL", "http://localhost:11434").rstrip("/"),
            local_model=os.getenv("PHOENIX_LOCAL_MODEL", "llama3.2:1b"),
            cloud_base_url=cloud_base_url,
            cloud_api_key=cloud_api_key,
            cloud_model=os.getenv(
                "PHOENIX_CLOUD_MODEL",
                DEFAULT_OPENROUTER_MODEL if "openrouter.ai" in cloud_base_url else DEFAULT_GEMINI_MODEL,
            ),
            tts_api_key=os.getenv("PHOENIX_TTS_API_KEY", "") or os.getenv("GEMINI_API_KEY", ""),
            tts_model=os.getenv("PHOENIX_TTS_MODEL", DEFAULT_TTS_MODEL),
            tts_voice=os.getenv("PHOENIX_TTS_VOICE", "Algenib"),
            tts_style=os.getenv(
                "PHOENIX_TTS_STYLE",
                "Deep, resonant, calm and authoritative cinematic delivery. Natural human cadence, measured pace, subtle warmth, clear articulation, and thoughtful pauses.",
            ),
            request_timeout=float(os.getenv("PHOENIX_REQUEST_TIMEOUT", "90")),
            conversation_history_messages=max(2, int(os.getenv("PHOENIX_HISTORY_MESSAGES", "20"))),
            memory_db_path=os.getenv("ULTRON_MEMORY_DB", ""),
            memory_owner_id=os.getenv("ULTRON_OWNER_ID", ""),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        )
