"""Step 3 - label each amount (total_bill / paid / due) using the words around it."""
from __future__ import annotations

import config
from pipeline.errors import GuardrailExit
from pipeline.labeling import labeled_amounts, reconciliation_score
from pipeline.models import Context
from pipeline.scoring import weighted_score


def run(ctx: Context) -> dict:
    classified = labeled_amounts(ctx)
    if not classified:
        raise GuardrailExit("no labeled amounts found")

    total_amounts = max(len(ctx.amount_tokens()), 1)
    matches = [segment.label_match for segment, _ in classified]

    confidence = weighted_score(
        config.STEP3_WEIGHTS,
        {
            "match_quality": sum(m.quality for m in matches) / len(matches),
            "uniqueness": sum(0.0 if m.near_tie else 1.0 for m in matches) / len(matches),
            "coverage": len(classified) / total_amounts,
            "consistency": reconciliation_score(ctx),
        },
    )
    return {
        "amounts": [{"type": seg.label_match.type, "value": amount.value} for seg, amount in classified],
        "confidence": round(confidence, 2),
    }
