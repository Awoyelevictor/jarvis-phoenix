"""Environment-based configuration for ULTRON."""
from __future__ import annotations

import os
from dataclasses import dataclass


GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_OPENROUTER_MODEL = "openrouter/free"
DEFAULT_TTS_MODEL = "gemini-3.8-flash-tts"\nDEFAULT_OPENROUTER_TTS_MODEL = "x-ai/grok-voice-tts-1.0"\nDEFAULT_OPENROUTER_TTS_VOICE = "rex"
DEFAULT_TRANSCRIPTION_MODEL = DEFAULT_GEMINI_MODEL
DEFAULT_TTS_STYLE = "Speak in a deep, resonant masculine voice with a controlled, slightly gravelly rasp and a subtle metallic, synthetic edge. The voice should feel intelligent, composed, authoritative, and quietly intimidating, like a sophisticated machine speaking through a natural human voice. Use measured pacing, deliberate pauses, precise American English pronunciation, and steady low-register delivery. Keep the sound rich and grounded rather than exaggerated, harsh, shouted, or cartoonishly robotic. Preserve natural conversational flow while maintaining a cool, calculating confidence."


@dataclass(frozen=True)
class Settings:
    local_base_url: str = "http://localhost:11434"
    local_model: str = "llama3.2:1b"
    cloud_base_url: str = GEMINI_OPENAI_BASE_URL
    cloud_api_key: str = ""
    cloud_model: str = DEFAULT_GEMINI_MODEL
    tts_api_key: str = ""
    transcription_model: str = DEFAULT_TRANSCRIPTION_MODEL
    tts_model: str = DEFAULT_TTS_MODEL
    tts_voice: str = "Algenib"
    tts_style: str = DEFAULT_TTS_STYLE
    voice_api_url: str = ""
    voice_api_key: str = ""
    voice_api_path: str = "/v1/audio/speech"
    use_qwen_tts: bool = False
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
            transcription_model=os.getenv("PHOENIX_TRANSCRIPTION_MODEL", DEFAULT_TRANSCRIPTION_MODEL).strip() or DEFAULT_TRANSCRIPTION_MODEL,
            tts_model=os.getenv("PHOENIX_TTS_MODEL", DEFAULT_OPENROUTER_TTS_MODEL if "openrouter.ai" in cloud_base_url else DEFAULT_TTS_MODEL),
            tts_voice=os.getenv("PHOENIX_TTS_VOICE", DEFAULT_OPENROUTER_TTS_VOICE if "openrouter.ai" in cloud_base_url else "Algenib"),
            tts_style=os.getenv("PHOENIX_TTS_STYLE", DEFAULT_TTS_STYLE),
            voice_api_url=(os.getenv("ULTRON_VOICE_API_URL", "") or os.getenv("TTS_API_URL", "")).rstrip("/"),
            voice_api_key=os.getenv("ULTRON_VOICE_API_KEY", ""),
            voice_api_path=os.getenv("ULTRON_VOICE_API_PATH", "/synthesize" if os.getenv("TTS_API_URL") else "/v1/audio/speech").strip() or "/synthesize",
            use_qwen_tts=os.getenv("USE_QWEN_TTS", "false").strip().lower() in {"1", "true", "yes", "on"},
            request_timeout=float(os.getenv("PHOENIX_REQUEST_TIMEOUT", "90")),
            conversation_history_messages=max(2, int(os.getenv("PHOENIX_HISTORY_MESSAGES", "20"))),
            memory_db_path=os.getenv("ULTRON_MEMORY_DB", ""),
            memory_owner_id=os.getenv("ULTRON_OWNER_ID", ""),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
        )
