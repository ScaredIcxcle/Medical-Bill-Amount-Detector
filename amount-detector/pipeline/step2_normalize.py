"""Step 2 - fix OCR digit errors and convert tokens to numbers."""
from __future__ import annotations

import config
from pipeline import review
from pipeline.errors import GuardrailExit
from pipeline.labeling import reconciliation_score
from pipeline.models import Context
from pipeline.numbers import to_number
from pipeline.scoring import weighted_score


def run(ctx: Context) -> dict:
    amounts = []
    for token in ctx.all_tokens():
        if token.is_percent:           # percentages are dropped from here onwards
            continue
        parsed = to_number(token.raw)
        if parsed is None:
            continue
        token.value, token.repaired = parsed
        token.quality = config.TOKEN_RULE_FIXED if token.repaired else config.TOKEN_UNTOUCHED
        amounts.append(token)

    if not amounts:
        raise GuardrailExit("no numeric amounts found")

    # Only when the bill does not add up: let the AI take a careful second look (see review.py).
    if config.REVIEW_ENABLED and reconciliation_score(ctx) == config.RECON_FAIL:
        review.try_fix(ctx)

    confidence = weighted_score(
        config.STEP2_WEIGHTS,
        {
            "token_quality": sum(t.quality for t in amounts) / len(amounts),
            "reconciliation": reconciliation_score(ctx),   # a mismatch lowers confidence, it never exits
            "edit_penalty": 1.0 if ctx.ai_edits == 0 else config.AI_EDIT_PENALTY,
        },
    )
    return {
        "normalized_amounts": [t.value for t in amounts],
        "normalization_confidence": round(confidence, 2),
    }