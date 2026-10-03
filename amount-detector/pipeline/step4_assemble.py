"""Step 4 - final output: labelled amounts with currency and provenance."""
from __future__ import annotations

import config
from pipeline.labeling import labeled_amounts
from pipeline.models import Context


def run(ctx: Context) -> dict:
    amounts = [
        {
            "type": segment.label_match.type,
            "value": amount.value,
            "source": f"{ctx.source_type}: '{segment.raw}'",
        }
        for segment, amount in labeled_amounts(ctx)
    ]
    return {"currency": config.CURRENCY, "amounts": amounts, "status": "ok"}
