"""Voice: speech-to-text (Gemini) and text-to-speech (gTTS) for English, Tamil and Hindi."""
import io
import re

from . import config, llm


def transcribe(audio_bytes, lang="en"):
    return llm.transcribe_audio(audio_bytes, lang, "audio/wav")


def _clean(text):
    text = re.sub(r"[*#_`>|]", "", text)
    return re.sub(r"\s+", " ", text).strip()[:1500]


def tts(text, lang="en"):
    """Return MP3 bytes or None (gTTS needs internet)."""
    try:
        from gtts import gTTS

        buf = io.BytesIO()
        gTTS(text=_clean(text), lang=config.TTS_CODES.get(lang, "en")).write_to_fp(buf)
        return buf.getvalue()
    except Exception:  # noqa: BLE001
        return None
