"""Gemini wrapper (google-genai SDK): text, JSON, vision, audio transcription, translation.
Every call has an offline fallback. KISAN_MOCK=1 forces offline mode (used by tests)."""
import json
import os
import re
import time

from dotenv import load_dotenv

from .config import LANG_NAMES

load_dotenv()
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_client = None
_tcache = {}
status = {"last_error": None, "fallbacks": 0, "calls": 0}


def set_api_key(key):
    global _client
    if key:
        os.environ["GEMINI_API_KEY"] = key.strip()
        _client = None


def _get_client():
    global _client
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key or os.getenv("KISAN_MOCK") == "1":
        return None
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=key)
    return _client


def ai_available():
    return _get_client() is not None


def _generate(contents, system="", json_mode=False, temperature=0.4):
    from google.genai import types

    cfg = types.GenerateContentConfig(system_instruction=system or None, temperature=temperature,
                                      response_mime_type="application/json" if json_mode else None)
    last = None
    for _ in range(2):
        try:
            status["calls"] += 1
            return _get_client().models.generate_content(model=MODEL, contents=contents, config=cfg).text
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.2)
    raise last


def _parse_json(text):
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", t, re.S)
        if not m:
            raise
        return json.loads(m.group(1))


def ask_text(prompt, system="", fallback="", temperature=0.4):
    if not ai_available():
        status["fallbacks"] += 1
        return fallback
    try:
        return (_generate(prompt, system, False, temperature) or fallback).strip()
    except Exception as e:  # noqa: BLE001
        status["last_error"] = str(e)
        status["fallbacks"] += 1
        return fallback


def ask_json(prompt, system="", fallback=None, temperature=0.3, image=None):
    """image: optional (bytes, mime) for vision. Returns parsed JSON or fallback."""
    if not ai_available():
        status["fallbacks"] += 1
        return fallback
    try:
        contents = prompt
        if image:
            from google.genai import types

            contents = [prompt, types.Part.from_bytes(data=image[0], mime_type=image[1])]
        return _parse_json(_generate(contents, system, True, temperature))
    except Exception as e:  # noqa: BLE001
        status["last_error"] = str(e)
        status["fallbacks"] += 1
        return fallback


def transcribe_audio(audio_bytes, lang="en", mime="audio/wav"):
    """Speech-to-text with Gemini audio understanding. Returns None when unavailable."""
    if not ai_available():
        return None
    try:
        from google.genai import types

        part = types.Part.from_bytes(data=audio_bytes, mime_type=mime)
        prompt = (f"This is a farmer speaking, most likely in {LANG_NAMES.get(lang, 'English')} "
                  "(it may also be English, Tamil or Hindi). Transcribe exactly what was said, in the original "
                  "language and script. Output only the transcript.")
        return (_generate([prompt, part], temperature=0.0) or "").strip() or None
    except Exception as e:  # noqa: BLE001
        status["last_error"] = str(e)
        return None


def translate(text, lang):
    """Translate English text to Tamil/Hindi (cached). Returns the original text when offline or lang == en."""
    if lang == "en" or not text.strip() or not ai_available():
        return text
    key = (text, lang)
    if key not in _tcache:
        out = ask_text(f"Translate into simple, spoken {LANG_NAMES[lang]} that a farmer understands. Keep numbers, "
                       f"units and product names. Output only the translation.\n\n{text}", fallback="", temperature=0.1)
        if not out:
            return text
        _tcache[key] = out
    return _tcache[key]


def to_english(text):
    """Translate a farmer's question to English for retrieval (only if it contains non-ASCII letters)."""
    if text.isascii() or not ai_available():
        return text
    return ask_text(f"Translate to English. Output only the translation.\n\n{text}", fallback=text, temperature=0.0)
