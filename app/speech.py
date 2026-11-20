"""Cloud speech services for ULTRON: Gemini transcription + ULTRON Voice API TTS."""
from __future__ import annotations

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings
from app.providers import ProviderError


class GeminiSpeechProvider:
    """Use Gemini only for microphone transcription and ULTRON Voice API for speech."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def transcribe(self, audio_base64: str, mime_type: str) -> str:
        """Transcribe microphone audio through OpenRouter using the chat API key."""
        api_key = self.settings.cloud_api_key
        if not api_key:
            raise ProviderError(
                "OPENROUTER_API_KEY is not configured on the ULTRON server. "
                "The same OpenRouter key is used for chat and microphone transcription."
            )
        if not mime_type.startswith("audio/"):
            raise ProviderError("Unsupported microphone audio format.")
        try:
            audio_bytes = base64.b64decode(audio_base64, validate=True)
        except (ValueError, TypeError) as exc:
            raise ProviderError("Microphone audio is not valid base64 data.") from exc
        if not audio_bytes or len(audio_bytes) > 10 * 1024 * 1024:
            raise ProviderError("Microphone recording is empty or too large.")

        normalized_mime = mime_type.split(";")[0].strip().lower()
        format_by_mime = {
            "audio/webm": "webm",
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/mpeg": "mp3",
            "audio/mp3": "mp3",
            "audio/mp4": "m4a",
            "audio/x-m4a": "m4a",
            "audio/ogg": "ogg",
            "audio/flac": "flac",
            "audio/aac": "aac",
        }
        audio_format = format_by_mime.get(normalized_mime)
        if not audio_format:
            raise ProviderError(f"Unsupported microphone audio format: {normalized_mime}")

        base = self.settings.cloud_base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            base = base[: -len("/chat/completions")]
        endpoint = base + "/audio/transcriptions"
        payload = {
            "model": (self.settings.transcription_model or "openai/whisper-1").strip(),
            "input_audio": {"data": audio_base64, "format": audio_format},
        }
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=min(self.settings.request_timeout, 60)) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:900]
            raise ProviderError(
                f"OpenRouter transcription failed (HTTP {exc.code}): {detail}"
            ) from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise ProviderError(f"OpenRouter transcription connection failed: {exc}") from exc

        transcript = result.get("text") if isinstance(result, dict) else None
        if not isinstance(transcript, str) or not transcript.strip():
            raise ProviderError("OpenRouter returned an empty or invalid transcript.")
        return transcript.strip()

    def synthesize(self, text: str) -> tuple[str, str]:
        """Generate speech exclusively through the custom ULTRON Voice API."""
        text = text.strip()
        if not text:
            raise ProviderError("There is no response to speak.")

        if not self.settings.voice_api_url or not self.settings.voice_api_key:
            raise ProviderError(
                "SONIVOX is not configured. Set SONIVOX_API_URL and SONIVOX_API_KEY "
                "(legacy ULTRON_VOICE_API_* names are also accepted)."
            )

        gateway_url = self.settings.voice_api_url.rstrip("/") + "/speak"
        gateway_payload = {
            "text": text[:2000],
            "lang": "eng",
        }
        gateway_request = Request(
            gateway_url,
            data=json.dumps(gateway_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "audio/wav",
                "X-API-Key": self.settings.voice_api_key,
            },
            method="POST",
        )
        try:
            with urlopen(gateway_request, timeout=max(self.settings.request_timeout, 300)) as response:
                audio_bytes = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(detail)
                detail = parsed.get("detail") or detail
            except (ValueError, TypeError):
                pass
            detail = " ".join(str(detail).split())[:900]
            raise ProviderError(
                f"ULTRON Voice API failed (HTTP {exc.code}): {detail}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"ULTRON Voice API connection failed: {exc}") from exc

        if not audio_bytes or not audio_bytes.startswith(b"RIFF"):
            raise ProviderError("ULTRON Voice API returned invalid WAV audio.")
        return base64.b64encode(audio_bytes).decode("ascii"), "audio/wav"
