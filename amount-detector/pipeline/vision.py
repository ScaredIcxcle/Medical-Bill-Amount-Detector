"""Image -> text using the Groq vision API. Uses only the Python standard library."""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import config
from pipeline.cleaning import clean_chunk, is_numeric_like
from pipeline.errors import GuardrailExit

log = logging.getLogger("amount-detector.vision")

# Two differently worded prompts, so the second reading is a genuinely independent check.
PROMPT_PRIMARY = (
    "Transcribe all the text in this image exactly as it is printed or written, in reading order, "
    "one visual line per line of output.\n"
    "Rules:\n"
    "1. Do not correct, interpret, summarize or reformat anything. Copy numbers and letters exactly "
    "as they appear, even if they look wrong or misspelled.\n"
    "2. If a label and its amount belong together (for example 'Total' and the number beside or below it), "
    "write them on the same line separated by a colon, like 'Total: 1200'.\n"
    "3. Keep currency symbols, commas and decimals.\n"
    "4. Write every piece of text exactly once. Never repeat a line or a section.\n"
    "5. If the page has columns, read one column completely before the next, and never join text "
    "from different columns on one line.\n"
    "6. Output only the transcribed text, nothing else."
)
PROMPT_CHECK = (
    "Read this document image and list every line of text it contains, from top to bottom. "
    "Copy the characters exactly as shown - do not fix typos or digits. "
    "Where a heading and its value belong together, put them on one line separated by a colon. "
    "Reply with only those lines."
)


class VisionError(Exception):
    """The image could not be read (bad key, network problem, empty answer, ...)."""


def detect_image_type(data: bytes) -> Optional[str]:
    """Identify PNG / JPEG / WebP from the first bytes (the file name or label can't be trusted)."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _clean_answer(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    text = re.sub(r"^```[a-zA-Z]*\n|\n```$", "", text.strip())
    return text.strip()


def _call_groq(image_bytes: bytes, mime: str, prompt: str, temperature: float, max_tokens: int = 2048) -> str:
    """One vision request. Retries once on timeouts, rate limits and server errors."""
    api_key = (os.environ.get("GROQ_API_KEY") or GROQ_API_KEY).strip()
    if not api_key:
        raise VisionError("GROQ_API_KEY is not set (create the .env file)")

    if image_bytes:
        data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
    else:                                  # text-only question (used by the review step)
        content = prompt
    payload = {
        "model": config.GROQ_VISION_MODEL,
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if config.GROQ_REASONING_EFFORT:
        payload["reasoning_effort"] = config.GROQ_REASONING_EFFORT

    request = urllib.request.Request(
        config.GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "amount-detector/1.0",   # the default Python agent is sometimes blocked
        },
        method="POST",
    )

    error: Exception = VisionError("no attempt made")
    for attempt in range(config.GROQ_RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=config.GROQ_TIMEOUT_SECONDS) as response:
                body = json.loads(response.read().decode("utf-8"))
            answer = _clean_answer(body["choices"][0]["message"]["content"])
            if answer:
                return answer
            error = VisionError("Groq returned an empty answer")
        except urllib.error.HTTPError as http_error:
            detail = http_error.read().decode("utf-8", "replace")[:300]
            error = VisionError(f"Groq returned HTTP {http_error.code}: {detail}")
            if http_error.code not in (429, 500, 502, 503, 504):
                break                                   # e.g. 401 bad key, 400 bad request: retrying won't help
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError) as exc:
            error = VisionError(f"Groq request failed: {exc}")
        if attempt < config.GROQ_RETRIES:
            time.sleep(1.5)
    raise error


def _number_tokens(text: str) -> Counter:
    tokens = Counter()
    for chunk in text.split():
        cleaned, _ = clean_chunk(chunk)
        if is_numeric_like(cleaned):
            tokens[cleaned] += 1
    return tokens


def reading_agreement(first: str, second: str) -> float:
    """How much two readings of the same image agree on their numbers: 1.0 identical, 0.0 nothing shared."""
    a, b = _number_tokens(first), _number_tokens(second)
    union = sum((a | b).values())
    return sum((a & b).values()) / union if union else 0.0


def transcribe_image(image_bytes: bytes):
    """Return (text, stability). Raises GuardrailExit if the image cannot be used.

    `stability` is the agreement between two independent readings, or None if the second one failed.
    """
    mime = detect_image_type(image_bytes or b"")
    if mime is None:
        raise GuardrailExit("image could not be read")
    if len(image_bytes) > config.MAX_IMAGE_BYTES:
        raise GuardrailExit("image could not be read")

    with ThreadPoolExecutor(max_workers=2) as pool:
        primary = pool.submit(_call_groq, image_bytes, mime, PROMPT_PRIMARY, 0.2)
        check = pool.submit(_call_groq, image_bytes, mime, PROMPT_CHECK, 0.3)
        try:
            text = primary.result()
        except VisionError as error:
            log.warning("image transcription failed: %s", error)
            raise GuardrailExit("image could not be read")
        try:
            stability: Optional[float] = reading_agreement(text, check.result())
        except VisionError as error:
            log.warning("second reading failed (continuing without it): %s", error)
            stability = None
    return text, stability
