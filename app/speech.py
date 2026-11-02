"""Speech providers for ULTRON.

Gemini remains the default. Chatterbox is an optional hosted provider so
speech generation stays separate from chat and persistent memory.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings
from app.providers import ProviderError


class GeminiSpeechProvider:
    """Generate ULTRON's directed voice with Google's Gemini TTS API."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def synthesize(self, text: str) -> tuple[str, str]:
        api_key = self.settings.tts_api_key
        if not api_key and "generativelanguage.googleapis.com" in self.settings.cloud_base_url:
            api_key = self.settings.cloud_api_key
        if not api_key:
            raise ProviderError("Gemini API key is not configured for voice generation.")
        text = text.strip()
        if not text:
            raise ProviderError("There is no response to speak.")

        style = self.settings.tts_style.strip()
        speech_prompt = (
            f"{style}\n\n"
            "Speak the following response exactly as written. Do not speak these "
            "voice instructions, add an introduction, or omit any words:\n"
            f"<response>\n{text}\n</response>"
        )
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.tts_model}:generateContent"
        )
        payload = {
            "contents": [{"role": "user", "parts": [{"text": speech_prompt}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": self.settings.tts_voice}
                    }
                },
            },
        }
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
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


class ChatterboxSpeechProvider:
    """Call ULTRON's public Gradio Chatterbox Space and return base64 audio."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def synthesize(self, text: str) -> tuple[str, str]:
        text = text.strip()
        if not text:
            raise ProviderError("There is no response to speak.")
        if len(text) > 300:
            raise ProviderError("Chatterbox voice requests are limited to 300 characters.")
        space_url = self.settings.chatterbox_space_url.strip()
        if not space_url:
            raise ProviderError("Set PHOENIX_CHATTERBOX_SPACE_URL to your Hugging Face Space URL.")

        try:
            from gradio_client import Client

            client = Client(space_url, verbose=False)
            result = client.predict(
                text,
                0.42,  # restrained expressiveness
                0.35,  # guidance strength
                api_name="/generate",
            )
            audio_path = None
            if isinstance(result, str):
                audio_path = result
            elif isinstance(result, dict):
                audio_path = result.get("path") or result.get("name")
            elif isinstance(result, (tuple, list)) and result:
                candidate = result[0]
                if isinstance(candidate, str):
                    audio_path = candidate
                elif isinstance(candidate, dict):
                    audio_path = candidate.get("path") or candidate.get("name")
            if not audio_path or not os.path.isfile(audio_path):
                raise ProviderError("Chatterbox returned no downloadable audio file.")
            with open(audio_path, "rb") as audio_file:
                audio_bytes = audio_file.read()
            if not audio_bytes:
                raise ProviderError("Chatterbox returned an empty audio file.")
            mime_type = mimetypes.guess_type(audio_path)[0] or "audio/wav"
            if not mime_type.startswith("audio/"):
                mime_type = "audio/wav"
            return base64.b64encode(audio_bytes).decode("ascii"), mime_type
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Chatterbox voice generation failed: {type(exc).__name__}: {exc}") from exc
