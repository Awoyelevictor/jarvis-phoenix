"""Cloud speech services for ULTRON: OpenRouter Whisper STT + ElevenLabs TTS."""
from __future__ import annotations

import base64
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings
from app.providers import ProviderError


class GeminiSpeechProvider:
    """Compatibility name retained for existing imports; Gemini is not used."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def transcribe(self, audio_base64: str, mime_type: str) -> str:
        """Transcribe a browser-recorded clip using OpenRouter's audio endpoint."""
        if "openrouter.ai" not in self.settings.cloud_base_url:
            raise ProviderError("Voice input requires PHOENIX_CLOUD_BASE_URL=https://openrouter.ai/api/v1.")
        if not self.settings.cloud_api_key:
            raise ProviderError("OpenRouter API key is not configured for speech transcription.")
        if not mime_type.startswith("audio/"):
            raise ProviderError("Unsupported microphone audio format.")
        try:
            audio_bytes = base64.b64decode(audio_base64, validate=True)
        except (ValueError, TypeError) as exc:
            raise ProviderError("Microphone audio is not valid base64 data.") from exc
        if not audio_bytes or len(audio_bytes) > 10 * 1024 * 1024:
            raise ProviderError("Microphone recording is empty or too large.")

        audio_format = {
            "audio/webm": "webm", "audio/mp4": "m4a", "audio/mpeg": "mp3",
            "audio/wav": "wav", "audio/ogg": "ogg", "audio/flac": "flac",
            "audio/aac": "aac",
        }.get(mime_type.split(";")[0].strip().lower(), "webm")
        model = (self.settings.transcription_model or "openai/whisper-1").strip()
        payload = {
            "model": model,
            "input_audio": {"data": audio_base64, "format": audio_format},
            "language": "en",
        }
        request = Request(
            "https://openrouter.ai/api/v1/audio/transcriptions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.cloud_api_key}",
                "HTTP-Referer": "https://github.com/Awoyelevictor/jarvis-phoenix",
                "X-Title": "ULTRON",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.request_timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise ProviderError(f"OpenRouter transcription failed (HTTP {exc.code}): {detail}") from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise ProviderError(f"OpenRouter transcription connection failed: {exc}") from exc
        transcript = result.get("text")
        if not isinstance(transcript, str):
            raise ProviderError("OpenRouter returned no transcript.")
        usage = result.get("usage") or {}
        if usage.get("cost") is not None:
            print("[ULTRON] STT usage reported by provider: $" + str(usage["cost"]), flush=True)
        return transcript.strip()

    def synthesize(self, text: str) -> tuple[str, str]:
        """Generate speech using ElevenLabs; never silently fall back to Gemini."""
        text = text.strip()
        if not text:
            raise ProviderError("There is no response to speak.")
        if not self.settings.elevenlabs_api_key:
            raise ProviderError("ELEVENLABS_API_KEY is not configured on the ULTRON server.")
        if not self.settings.elevenlabs_voice_id:
            raise ProviderError("ELEVENLABS_VOICE_ID is not configured.")

        url = (
            "https://api.elevenlabs.io/v1/text-to-speech/"
            f"{self.settings.elevenlabs_voice_id}?output_format=mp3_44100_128"
        )
        payload = {
            "text": text[:6000],
            "model_id": self.settings.elevenlabs_model_id or "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.58,
                "similarity_boost": 0.82,
                "style": 0.35,
                "use_speaker_boost": True,
            },
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
                "xi-api-key": self.settings.elevenlabs_api_key,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.request_timeout) as response:
                audio_bytes = response.read()
                mime_type = response.headers.get_content_type() or "audio/mpeg"
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(detail)
                detail = parsed.get("detail", {}).get("message") or parsed.get("detail") or detail
            except (ValueError, TypeError):
                pass
            detail = " ".join(str(detail).split())[:900]
            raise ProviderError(f"ElevenLabs TTS failed (HTTP {exc.code}): {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"ElevenLabs TTS connection failed: {exc}") from exc
        if not audio_bytes:
            raise ProviderError("ElevenLabs returned an empty audio response.")
        if not mime_type.startswith("audio/"):
            raise ProviderError(f"ElevenLabs returned an unexpected content type: {mime_type}.")
        return base64.b64encode(audio_bytes).decode("ascii"), mime_type
