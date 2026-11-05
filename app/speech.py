"""Gemini-generated speech output for ULTRON (never device TTS)."""
from __future__ import annotations

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings
from app.providers import ProviderError


class GeminiSpeechProvider:
    """Generate ULTRON's directed voice with Google's Gemini TTS API."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def transcribe(self, audio_base64: str, mime_type: str) -> str:
        """Transcribe a browser-recorded microphone clip with Gemini Flash."""
        api_key=self.settings.tts_api_key
        if not api_key: raise ProviderError("Gemini API key is not configured for microphone transcription.")
        if not mime_type.startswith("audio/"): raise ProviderError("Unsupported microphone audio format.")
        try: audio_bytes=base64.b64decode(audio_base64,validate=True)
        except (ValueError,TypeError) as exc: raise ProviderError("Microphone audio is not valid base64 data.") from exc
        if not audio_bytes or len(audio_bytes)>10*1024*1024: raise ProviderError("Microphone recording is empty or too large.")
        payload={"contents":[{"role":"user","parts":[
            {"text":"Transcribe the speech in this audio. Return only the exact spoken words, without commentary. If no speech is intelligible, return an empty response."},
            {"inlineData":{"mimeType":mime_type,"data":audio_base64}}
        ]}],"generationConfig":{"temperature":0}}
        request=Request("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            data=json.dumps(payload).encode("utf-8"),headers={"Content-Type":"application/json","x-goog-api-key":api_key},method="POST")
        try:
            with urlopen(request,timeout=self.settings.request_timeout) as response: result=json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail=exc.read().decode("utf-8",errors="replace")[:1000]
            raise ProviderError(f"Gemini transcription failed (HTTP {exc.code}): {detail}") from exc
        except (URLError,TimeoutError,OSError,ValueError) as exc: raise ProviderError(f"Gemini transcription connection failed: {exc}") from exc
        try: return " ".join(part.get("text","") for part in result["candidates"][0]["content"]["parts"]).strip()
        except (KeyError,IndexError,TypeError) as exc:
            raise ProviderError(result.get("error",{}).get("message","Gemini returned no transcript.")) from exc

    def synthesize(self, text: str) -> tuple[str, str]:
        text = text.strip()
        if not text:
            raise ProviderError("There is no response to speak.")

        if self.settings.use_qwen_tts and self.settings.voice_api_url:
            try:
                return self._synthesize_qwen(text)
            except ProviderError:
                # Keep speech available if the remote GPU is cold or unavailable.
                pass

        return self._synthesize_gemini(text)

    def _synthesize_qwen(self, text: str) -> tuple[str, str]:
        base_url = self.settings.voice_api_url.rstrip("/")
        api_path = (self.settings.voice_api_path or "/v1/audio/speech").strip()
        if not api_path.startswith("/"):
            api_path = "/" + api_path
        endpoint = base_url if base_url.endswith(api_path) else f"{base_url}{api_path}"
        request = Request(
            endpoint,
            data=json.dumps({"text": text, "language": "English"}).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Accept": "audio/wav",
                **({"Authorization": f"Bearer {self.settings.voice_api_key}"}
                   if self.settings.voice_api_key else {}),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.request_timeout) as response:
                audio_bytes = response.read()
        except HTTPError as exc:
            raise ProviderError(f"Qwen voice API returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ProviderError("Qwen voice API connection failed.") from exc

        if not audio_bytes or not audio_bytes.startswith(b"RIFF"):
            raise ProviderError("Qwen voice API did not return a valid WAV file.")
        return base64.b64encode(audio_bytes).decode("ascii"), "audio/wav"

    def _synthesize_gemini(self, text: str) -> tuple[str, str]:
        api_key = self.settings.tts_api_key
        # Preserve compatibility for direct Gemini-only Settings instances.
        if not api_key and "generativelanguage.googleapis.com" in self.settings.cloud_base_url:
            api_key = self.settings.cloud_api_key
        if not api_key:
            raise ProviderError("Gemini API key is not configured for voice generation.")
        text = text.strip()
        if not text:
            raise ProviderError("There is no response to speak.")

        # Gemini TTS takes vocal direction as natural-language prompt text.
        # Keep the spoken response clearly separated so the instructions are
        # performed, not read aloud.
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
            "contents": [{
                "role": "user",
                "parts": [{"text": speech_prompt}],
            }],
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
