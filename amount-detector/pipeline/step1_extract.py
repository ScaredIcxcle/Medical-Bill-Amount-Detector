"""Step 1 - extract raw numeric tokens and report how confidently the input was read."""
from __future__ import annotations

import config
from pipeline.cleaning import WORD_PATTERN, parse_segments
from pipeline.errors import GuardrailExit
from pipeline.models import Context
from pipeline.scoring import weighted_score


def _confidence(ctx: Context) -> float:
    words = WORD_PATTERN.findall(ctx.text)
    total_words = max(len(words), 1)

    # Words that needed an OCR-style fix: numbers containing letters, labels matched only by folding/fuzzing.
    fixes = 0
    for segment in ctx.segments:
        fixes += sum(1 for t in segment.tokens if not t.is_percent and any(c.isalpha() for c in t.raw))
        if segment.label_match.method in ("folded", "fuzzy"):
            fixes += 1
    cleanliness = 1 - min(fixes, total_words) / total_words

    amount_segments = [s for s in ctx.segments if any(not t.is_percent for t in s.tokens)]
    if amount_segments:
        label_recognition = sum(s.label_match.quality for s in amount_segments) / len(amount_segments)
        structure = sum(1.0 if s.has_separator else 0.5 for s in amount_segments) / len(amount_segments)
    else:
        label_recognition, structure = 0.0, 0.0

    return weighted_score(
        config.STEP1_WEIGHTS,
        {
            "cleanliness": cleanliness,
            "label_recognition": label_recognition,
            "structure": structure,
            "stability": ctx.stability,   # None for typed text
        },
    )


def run(ctx: Context) -> dict:
    text = (ctx.text or "").strip()
    if not text:
        raise GuardrailExit("no numeric amounts found")
    if len(text) > config.MAX_TEXT_CHARS:
        raise GuardrailExit("input too long")

    ctx.segments = parse_segments(text)
    tokens = ctx.all_tokens()
    if not tokens:
        raise GuardrailExit("no numeric amounts found")

    confidence = _confidence(ctx)
    if confidence < config.NOISY_THRESHOLD:
        raise GuardrailExit("document too noisy")

    return {
        "raw_tokens": [t.raw for t in tokens],
        "currency_hint": config.CURRENCY,
        "confidence": round(confidence, 2),
    }
