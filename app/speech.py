"""Speech providers for ULTRON.

Gemini remains the default. Chatterbox is an optional hosted provider so
speech generation stays separate from chat and persistent memory.
"""
from __future__ import annotations

import base64
import io
import json
import mimetypes
import os
import wave
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
    """Call ULTRON's public Gradio Chatterbox Space and return base64 WAV audio."""

    MAX_TEXT_CHARS = 1200
    CHUNK_CHARS = 280

    def __init__(self, settings: Settings):
        self.settings = settings

    @classmethod
    def _chunks(cls, text: str) -> list[str]:
        words = text.split()
        chunks: list[str] = []
        current = ""
        for word in words:
            while len(word) > cls.CHUNK_CHARS:
                if current:
                    chunks.append(current)
                    current = ""
                chunks.append(word[:cls.CHUNK_CHARS])
                word = word[cls.CHUNK_CHARS:]
            candidate = f"{current} {word}".strip()
            if len(candidate) > cls.CHUNK_CHARS and current:
                chunks.append(current)
                current = word
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    @staticmethod
    def _audio_path(result) -> str | None:
        if isinstance(result, str):
            return result
        if isinstance(result, dict):
            return result.get("path") or result.get("name")
        if isinstance(result, (tuple, list)) and result:
            first = result[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                return first.get("path") or first.get("name")
        return None

    @staticmethod
    def _join_wav_files(paths: list[str]) -> bytes:
        output = io.BytesIO()
        params = None
        frames = []
        for path in paths:
            with wave.open(path, "rb") as source:
                current = source.getparams()
                signature = (current.nchannels, current.sampwidth, current.framerate, current.comptype)
                if params is None:
                    params = current
                    expected = signature
                elif signature != expected:
                    raise ProviderError("Chatterbox returned audio chunks with incompatible formats.")
                frames.append(source.readframes(source.getnframes()))
        if not params:
            raise ProviderError("Chatterbox returned no audio.")
        with wave.open(output, "wb") as target:
            target.setparams(params)
            target.writeframes(b"".join(frames))
        return output.getvalue()

    def synthesize(self, text: str) -> tuple[str, str]:
        text = text.strip()
        if not text:
            raise ProviderError("There is no response to speak.")
        if len(text) > self.MAX_TEXT_CHARS:
            raise ProviderError(
                f"Chatterbox speech is limited to {self.MAX_TEXT_CHARS} characters per response."
            )
        space_url = self.settings.chatterbox_space_url.strip()
        if not space_url:
            raise ProviderError("Set PHOENIX_CHATTERBOX_SPACE_URL to your Hugging Face Space URL.")

        try:
            from gradio_client import Client

            client = Client(space_url, verbose=False)
            paths = []
            for chunk in self._chunks(text):
                result = client.predict(
                    chunk,
                    0.42,  # restrained expressiveness
                    0.35,  # guidance strength
                    api_name="/generate",
                )
                path = self._audio_path(result)
                if not path or not os.path.isfile(path):
                    raise ProviderError("Chatterbox returned no downloadable audio file.")
                paths.append(path)
            audio_bytes = self._join_wav_files(paths)
            return base64.b64encode(audio_bytes).decode("ascii"), "audio/wav"
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Chatterbox voice generation failed: {type(exc).__name__}: {exc}") from exc
