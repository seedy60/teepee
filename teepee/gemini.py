"""Minimal Google Gemini client for describing media.

Uses the Generative Language REST API directly via urllib so no extra
dependency is needed. Media is sent inline as base64, which the API accepts
for requests up to roughly 20 MB total.
"""
import base64
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)

_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "{model}:generateContent?key={key}"
)

_MODELS_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models"
    "?key={key}&pageSize=1000"
)

# Curated fallback list shown before (or instead of) a live fetch. Newest /
# recommended first. All accept image and video input.
COMMON_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

# The API rejects inline request bodies larger than ~20 MB. Base64 inflates
# the payload by about a third, so cap the raw file at 14 MB to stay safe.
INLINE_LIMIT_BYTES = 14 * 1024 * 1024

_IMAGE_PROMPT = (
    "You are helping a blind or visually impaired person understand an image "
    "they received in a chat. Describe it clearly and concisely in a short "
    "paragraph. Include any visible text verbatim. Do not start with phrases "
    "like 'this image shows'; just describe it."
)

_VIDEO_PROMPT = (
    "You are helping a blind or visually impaired person understand a video "
    "they received in a chat. Summarize what happens, the setting, who or what "
    "appears, and read out any important on-screen text. Keep it to a short "
    "paragraph."
)


class GeminiError(Exception):
    """Raised for any failure while requesting a description."""


def is_configured(api_key):
    return bool(api_key and api_key.strip())


def list_models(api_key, timeout=30):
    """Return the model names available to this key that support
    generateContent (i.e. usable for descriptions), newest first.

    Follows pagination so newer models are never cut off by the page size,
    and sorts descending so the highest version numbers appear at the top.
    Raises GeminiError on any failure.
    """
    if not is_configured(api_key):
        raise GeminiError("No Gemini API key is configured.")
    key = api_key.strip()
    names = []
    page_token = None
    for _ in range(20):  # safety cap on the number of pages
        url = _MODELS_ENDPOINT.format(key=key)
        if page_token:
            url += "&pageToken=" + urllib.parse.quote(page_token)
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                err = json.loads(e.read().decode("utf-8", "replace"))
                detail = err.get("error", {}).get("message", "")
            except Exception:
                pass
            if e.code in (400, 403):
                raise GeminiError(
                    "Gemini rejected the API key. Check it in Settings."
                )
            raise GeminiError(
                f"Gemini API error {e.code}" + (f": {detail}" if detail else "")
            )
        except urllib.error.URLError as e:
            raise GeminiError(f"Could not reach Gemini: {e.reason}")
        except Exception as e:  # pragma: no cover - defensive
            raise GeminiError(f"Unexpected error contacting Gemini: {e}")

        for m in payload.get("models", []):
            methods = m.get("supportedGenerationMethods") or []
            if "generateContent" not in methods:
                continue
            name = m.get("name", "")
            if name.startswith("models/"):
                name = name[len("models/"):]
            if name:
                names.append(name)

        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    # De-duplicate, then sort so newer Gemini versions surface first. Gemini
    # is named so that reverse-alphabetical order tracks version (2.5 > 2.0 >
    # 1.5), with "gemini" models ahead of others.
    unique = sorted(set(names), reverse=True)
    unique.sort(key=lambda n: (0 if n.startswith("gemini") else 1))
    return unique


def describe_media(api_key, file_path, mime_type, is_video=False,
                   model="gemini-2.5-flash", timeout=120):
    """Return a text description of the media at file_path.

    Raises GeminiError on any problem (no key, file too large, network or API
    error, empty response).
    """
    if not is_configured(api_key):
        raise GeminiError(
            "No Gemini API key is configured. Add one in Settings under "
            "AI descriptions."
        )

    try:
        size = os.path.getsize(file_path)
    except OSError as e:
        raise GeminiError(f"Could not read the downloaded media: {e}")

    if size > INLINE_LIMIT_BYTES:
        raise GeminiError(
            "This file is too large to describe (over 14 MB)."
        )

    try:
        with open(file_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("ascii")
    except OSError as e:
        raise GeminiError(f"Could not read the downloaded media: {e}")

    prompt = _VIDEO_PROMPT if is_video else _IMAGE_PROMPT
    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inline_data": {
                            "mime_type": mime_type or "application/octet-stream",
                            "data": encoded,
                        }
                    },
                ]
            }
        ]
    }

    url = _ENDPOINT.format(model=model or "gemini-2.5-flash", key=api_key.strip())
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            err = json.loads(e.read().decode("utf-8", "replace"))
            detail = err.get("error", {}).get("message", "")
        except Exception:
            pass
        if e.code in (400, 403) and "API key" in detail:
            raise GeminiError("Gemini rejected the API key. Check it in Settings.")
        raise GeminiError(
            f"Gemini API error {e.code}" + (f": {detail}" if detail else "")
        )
    except urllib.error.URLError as e:
        raise GeminiError(f"Could not reach Gemini: {e.reason}")
    except Exception as e:  # pragma: no cover - defensive
        raise GeminiError(f"Unexpected error contacting Gemini: {e}")

    text = _extract_text(payload)
    if not text:
        blocked = _blocked_reason(payload)
        if blocked:
            raise GeminiError(f"Gemini declined to describe this media: {blocked}")
        raise GeminiError("Gemini returned an empty description.")
    return text


def _extract_text(payload):
    try:
        candidates = payload.get("candidates") or []
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip()
    except (AttributeError, IndexError, KeyError):
        return ""


def _blocked_reason(payload):
    feedback = payload.get("promptFeedback") or {}
    reason = feedback.get("blockReason")
    if reason:
        return str(reason)
    candidates = payload.get("candidates") or []
    if candidates:
        finish = candidates[0].get("finishReason")
        if finish and finish not in ("STOP", "MAX_TOKENS"):
            return str(finish)
    return ""
