"""Gemini-generated speech output for ULTRON (never device TTS)."""
from __future__ import annotations

import base64
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings, DEFAULT_TRANSCRIPTION_MODEL
from app.providers import ProviderError


class GeminiSpeechProvider:
    """Generate ULTRON's directed voice with Google's Gemini TTS API."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def transcribe(self, audio_base64: str, mime_type: str) -> str:
        """Transcribe a browser-recorded clip through the configured cloud provider."""
        import os

        if os.getenv("ULTRON_ENABLE_CLOUD_TRANSCRIPTION", "false").strip().lower() not in {"1", "true", "yes", "on"}:
            raise ProviderError(
                "Cloud speech transcription is disabled to prevent unexpected API charges. "
                "Enable ULTRON_ENABLE_CLOUD_TRANSCRIPTION=true after approving transcription usage."
            )
        if not mime_type.startswith("audio/"):
            raise ProviderError("Unsupported microphone audio format.")
        try:
            audio_bytes = base64.b64decode(audio_base64, validate=True)
        except (ValueError, TypeError) as exc:
            raise ProviderError("Microphone audio is not valid base64 data.") from exc
        if not audio_bytes or len(audio_bytes) > 10 * 1024 * 1024:
            raise ProviderError("Microphone recording is empty or too large.")

        if "openrouter.ai" in self.settings.cloud_base_url:
            api_key = self.settings.cloud_api_key
            if not api_key:
                raise ProviderError("OpenRouter API key is not configured for speech transcription.")
            audio_format = {
                "audio/webm": "webm", "audio/mp4": "m4a", "audio/mpeg": "mp3",
                "audio/wav": "wav", "audio/ogg": "ogg", "audio/flac": "flac",
                "audio/aac": "aac",
            }.get(mime_type.split(";")[0].strip().lower(), "webm")
            model = os.getenv("ULTRON_STT_MODEL", "openai/whisper-1").strip()
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
                    "Authorization": f"Bearer {api_key}",
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

        api_key = self.settings.tts_api_key or self.settings.cloud_api_key
        if not api_key:
            raise ProviderError("Gemini API key is not configured for microphone transcription.")
        payload = {"contents": [{"role": "user", "parts": [
            {"text": "Transcribe the speech in this audio. Return only the exact spoken words, without commentary. If no speech is intelligible, return an empty response."},
            {"inlineData": {"mimeType": mime_type, "data": audio_base64}},
        ]}], "generationConfig": {"temperature": 0}}
        model = (self.settings.transcription_model or DEFAULT_TRANSCRIPTION_MODEL).strip()
        request = Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.voicebox_request_timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise ProviderError(f"Gemini transcription failed (HTTP {exc.code}): {detail}") from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise ProviderError(f"Gemini transcription connection failed: {exc}") from exc
        try:
            return " ".join(part.get("text", "") for part in result["candidates"][0]["content"]["parts"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(result.get("error", {}).get("message", "Gemini returned no transcript.")) from exc
    def synthesize(self, text: str) -> tuple[str, str]:
        text = text.strip()
        if not text:
            raise ProviderError("There is no response to speak.")

        voicebox_error = None
        if self.settings.voicebox_api_url and self.settings.voicebox_profile_id:
            try:
                audio = self._synthesize_voicebox(text)
                print("[ULTRON] Speech generated by Voicebox.", flush=True)
                return audio
            except ProviderError as exc:
                voicebox_error = exc
                print(f"[ULTRON] Voicebox failed; trying configured fallback: {exc}", flush=True)

        qwen_error = None
        if self.settings.use_qwen_tts and self.settings.voice_api_url:
            try:
                audio = self._synthesize_qwen(text)
                print("[ULTRON] Speech generated by Qwen3-TTS.", flush=True)
                return audio
            except ProviderError as exc:
                qwen_error = exc
                print(f"[ULTRON] Qwen3-TTS failed; trying Gemini fallback: {exc}", flush=True)

        if "openrouter.ai" in self.settings.cloud_base_url and self.settings.cloud_api_key:
            try:
                audio = self._synthesize_openrouter(text)
                print("[ULTRON] Speech generated by OpenRouter Grok Voice TTS.", flush=True)
                return audio
            except ProviderError as exc:
                print(f"[ULTRON] OpenRouter TTS failed: {exc}", flush=True)
                if not self.settings.tts_api_key and "generativelanguage.googleapis.com" not in self.settings.cloud_base_url:
                    if qwen_error:
                        raise ProviderError(f"Qwen3-TTS failed: {qwen_error} OpenRouter TTS also failed: {exc}") from exc
                    raise

        try:
            audio = self._synthesize_gemini(text)
            print("[ULTRON] Speech generated by Gemini TTS fallback.", flush=True)
            return audio
        except ProviderError as exc:
            if qwen_error or voicebox_error:
                failures = " ".join(
                    part for part in (
                        f"Voicebox failed: {voicebox_error}" if voicebox_error else "",
                        f"Qwen3-TTS failed: {qwen_error}" if qwen_error else "",
                        f"Gemini TTS fallback also failed: {exc}",
                    ) if part
                )
                raise ProviderError(failures) from exc
            raise

    def _synthesize_voicebox(self, text: str) -> tuple[str, str]:
        """Generate speech through a Voicebox REST API and download its WAV/audio result."""
        if len(text) > 5000:
            raise ProviderError("Voicebox accepts up to 5,000 characters per generation.")
        base_url = self.settings.voicebox_api_url.rstrip("/")
        payload = {
            "profile_id": self.settings.voicebox_profile_id,
            "text": text,
            "language": self.settings.voicebox_language or "en",
            "engine": self.settings.voicebox_engine or "kokoro",
        }
        if self.settings.voicebox_instruct and self.settings.voicebox_engine == "qwen_custom_voice":
            payload["instruct"] = self.settings.voicebox_instruct
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.settings.voicebox_api_key:
            headers["Authorization"] = f"Bearer {self.settings.voicebox_api_key}"
        request = Request(
            f"{base_url}/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.request_timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = " ".join(exc.read().decode("utf-8", errors="replace").split())[:700]
            raise ProviderError(f"Voicebox generation failed (HTTP {exc.code}). {detail}") from exc
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise ProviderError(f"Voicebox generation connection failed: {exc}") from exc
        generation_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(generation_id, str) or not generation_id.strip():
            raise ProviderError("Voicebox did not return a generation ID.")

        audio_request = Request(
            f"{base_url}/audio/{generation_id}",
            headers={**({"Authorization": f"Bearer {self.settings.voicebox_api_key}"} if self.settings.voicebox_api_key else {}), "Accept": "audio/*"},
            method="GET",
        )
        try:
            with urlopen(audio_request, timeout=self.settings.voicebox_request_timeout) as response:
                audio_bytes = response.read()
                mime_type = response.headers.get_content_type() if hasattr(response, "headers") else "audio/wav"
        except HTTPError as exc:
            detail = " ".join(exc.read().decode("utf-8", errors="replace").split())[:500]
            raise ProviderError(f"Voicebox audio download failed (HTTP {exc.code}). {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ProviderError("Voicebox audio download connection failed.") from exc
        if not audio_bytes:
            raise ProviderError("Voicebox returned an empty audio file.")
        if not mime_type or not mime_type.startswith("audio/"):
            mime_type = "audio/wav" if audio_bytes.startswith(b"RIFF") else "application/octet-stream"
        if not mime_type.startswith("audio/"):
            raise ProviderError("Voicebox returned an unsupported audio format.")
        return base64.b64encode(audio_bytes).decode("ascii"), mime_type

    def _synthesize_openrouter(self, text: str) -> tuple[str, str]:
        """Generate speech through the same OpenRouter key used for cloud chat."""
        model = (self.settings.tts_model or "x-ai/grok-voice-tts-1.0").strip()
        voice = (self.settings.tts_voice or "rex").strip()
        payload = {
            "model": model,
            "input": (f"[deep, low-pitched masculine voice; resonant chest tone; calm, deliberate pacing; crisp diction; controlled authority; subtle synthetic metallic edge] {text.strip()}"),
            "voice": voice,
            "response_format": "wav",
        }
        request = Request(
            "https://openrouter.ai/api/v1/audio/speech",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.settings.cloud_api_key}",
                "HTTP-Referer": "https://github.com/Awoyelevictor/jarvis-phoenix",
                "X-Title": "ULTRON",
                "Accept": "audio/*",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.request_timeout) as response:
                audio_bytes = response.read()
                mime_type = response.headers.get_content_type() or "audio/wav"
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace").strip()
            detail = " ".join(detail.split())[:700]
            raise ProviderError(f"OpenRouter TTS returned HTTP {exc.code}. {detail}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"OpenRouter TTS connection failed: {exc}") from exc
        if not audio_bytes:
            raise ProviderError("OpenRouter TTS returned an empty audio response.")
        if not mime_type.startswith("audio/"):
            try:
                detail = audio_bytes.decode("utf-8", errors="replace")[:500]
            except Exception:
                detail = "Unexpected non-audio response."
            raise ProviderError(f"OpenRouter TTS returned {mime_type}: {detail}")
        return base64.b64encode(audio_bytes).decode("ascii"), mime_type

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
                "Bypass-Tunnel-Reminder": "true",
                **({"Authorization": f"Bearer {self.settings.voice_api_key}"}
                   if self.settings.voice_api_key else {}),
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.settings.request_timeout) as response:
                audio_bytes = response.read()
        except HTTPError as exc:
            # Include the upstream response body to diagnose 403 tunnel/auth failures.
            detail = exc.read().decode("utf-8", errors="replace").strip()
            detail = " ".join(detail.split())[:500]
            suffix = f" Response: {detail}" if detail else ""
            raise ProviderError(f"Qwen voice API returned HTTP {exc.code}.{suffix}") from exc
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
