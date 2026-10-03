"""AI review - a careful second look, used only when total != paid + due.

How it stays safe:
  * Code (not the AI) proposes the alternatives: a number with exactly one misread digit
    (0/8, 1/7, 3/8 ...) that would make total = paid + due.
  * The AI is NOT told about the arithmetic. It only answers "which value is printed there?"
    (looking at the image when there is one) and may answer "I cannot tell".
  * It is asked three times, with the options in different orders. Anything other than the
    alternative three times in a row means no change.
  * If more than one alternative gets unanimous votes, nothing is changed.
  * At most one number is changed, and the bill must balance afterwards.
"""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import config
from pipeline import vision
from pipeline.labeling import labeled_amounts, reconciliation_score
from pipeline.models import Context, Segment, Token
from pipeline.numbers import to_number

log = logging.getLogger("amount-detector.review")

_CONFUSABLE: dict[str, list[str]] = {}
for _a, _b in config.REVIEW_PAIRS:
    _CONFUSABLE.setdefault(_a, []).append(_b)
    _CONFUSABLE.setdefault(_b, []).append(_a)


def candidate_values(token: Token) -> list:
    """Other numbers this token could be if exactly one digit was misread."""
    digits = "".join(config.DIGIT_FIXES.get(ch, ch) for ch in token.raw)
    seen = {token.value}
    found = []
    for i, ch in enumerate(digits):
        for alternative in sorted(_CONFUSABLE.get(ch, [])):
            parsed = to_number(digits[:i] + alternative + digits[i + 1:])
            if parsed is None or parsed[0] in seen:
                continue
            seen.add(parsed[0])
            found.append(parsed[0])
    return found


def find_fixes(ctx: Context) -> list[tuple[Segment, Token, object]]:
    """Single-digit alternatives that would make total = paid + due."""
    picked = {}
    for segment, token in labeled_amounts(ctx):
        picked.setdefault(segment.label_match.type, (segment, token))
    if not {"total_bill", "paid", "due"} <= picked.keys():
        return []
    fixes = []
    for kind, (segment, token) in picked.items():
        for candidate in candidate_values(token):
            values = {k: picked[k][1].value for k in picked}
            values[kind] = candidate
            if abs(values["total_bill"] - (values["paid"] + values["due"])) <= config.RECON_TOLERANCE:
                fixes.append((segment, token, candidate))
    return fixes


def _question(ctx: Context, segment: Segment, token: Token, options: list) -> str:
    if ctx.image_bytes:
        intro = "Look carefully at this document image."
    else:
        intro = f"Here is text that was read from a scanned bill:\n{ctx.text}\n"
    listed = "\n".join(f"{letter}) {value}" for letter, value in zip("AB", options))
    return (
        f"{intro}\n"
        f'Next to the label "{segment.label_text}" there is an amount. '
        f'The scan read it as "{token.raw}", but one digit may have been misread.\n'
        f"Which amount is actually printed there?\n{listed}\nC) I cannot tell\n"
        "Answer with one letter only: A, B or C."
    )


def _vote(ctx: Context, segment: Segment, token: Token, candidate, flipped: bool) -> bool:
    """True only if the AI clearly picked the candidate."""
    options = [candidate, token.value] if flipped else [token.value, candidate]
    try:
        answer = vision._call_groq(ctx.image_bytes, ctx.image_mime, _question(ctx, segment, token, options), 0.3, 32)
    except vision.VisionError as error:
        log.warning("review vote failed: %s", error)
        return False
    match = re.match(r"\W*([ABC])\b", answer.strip())
    if not match or match.group(1) == "C":
        return False
    return options["AB".index(match.group(1))] == candidate


def try_fix(ctx: Context) -> bool:
    """Apply one AI-confirmed correction if every condition holds. Returns True if a number changed."""
    fixes = find_fixes(ctx)
    if not fixes or len(fixes) > config.REVIEW_MAX_FIXES:
        return False

    confirmed = []
    for segment, token, candidate in fixes:
        flips = [i % 2 == 1 for i in range(config.REVIEW_VOTES)]   # option order: AB, BA, AB
        with ThreadPoolExecutor(max_workers=config.REVIEW_VOTES) as pool:
            votes = list(pool.map(lambda flip: _vote(ctx, segment, token, candidate, flip), flips))
        if all(votes):
            confirmed.append((segment, token, candidate))
    if len(confirmed) != 1:
        return False

    _, token, candidate = confirmed[0]
    before = (token.value, token.quality, token.repaired)
    token.value, token.quality, token.repaired = candidate, config.TOKEN_AI_FIXED, True
    ctx.ai_edits = 1
    if reconciliation_score(ctx) != config.RECON_PASS:     # safety net: must balance after the change
        token.value, token.quality, token.repaired = before
        ctx.ai_edits = 0
        return False
    log.info("AI review changed %s -> %s", before[0], candidate)
    return True