"""Gemini-generated speech output for ULTRON (never device TTS)."""
from __future__ import annotations

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings
from app.providers import ProviderError


class GeminiSpeechProvider:
    """Generate natural speech audio with Google's Gemini TTS API."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def synthesize(self, text: str) -> tuple[str, str]:
        api_key = self.settings.tts_api_key
        # Preserve compatibility for direct Gemini-only Settings instances.
        if not api_key and "generativelanguage.googleapis.com" in self.settings.cloud_base_url:
            api_key = self.settings.cloud_api_key
        if not api_key:
            raise ProviderError("Gemini API key is not configured for voice generation.")
        text = text.strip()
        if not text:
            raise ProviderError("There is no response to speak.")

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.tts_model}:generateContent"
        )
        payload = {
            "contents": [{
                "role": "user",
                "parts": [{
                    "text": text,
                    "speech_metadata": {
                        "style": self.settings.tts_style
                    },
                }],
            }],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self.settings.tts_voice}}
                },
            },
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.request_timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1200]
            raise ProviderError(f"Gemini voice generation failed (HTTP {exc.code}): {detail}") from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise ProviderError(f"Gemini voice connection failed: {exc}") from exc

        try:
            parts = result["candidates"][0]["content"]["parts"]
            audio = next(part["inlineData"] for part in parts if "inlineData" in part)
            encoded = audio["data"]
            mime_type = audio.get("mimeType", "audio/wav")
            base64.b64decode(encoded, validate=True)
        except (KeyError, IndexError, StopIteration, TypeError, ValueError) as exc:
            message = result.get("error", {}).get("message", "Gemini returned no audio data.")
            raise ProviderError(str(message)) from exc
        if not mime_type.startswith("audio/"):
            raise ProviderError("Gemini returned an unsupported audio format.")
        return encoded, mime_type
