"""Helpers shared by Steps 2-4: which amounts carry a total/paid/due label, and do they add up?"""
from __future__ import annotations

import config
from pipeline.models import Context, Segment, Token


def labeled_amounts(ctx: Context) -> list[tuple[Segment, Token]]:
    """The first amount of every segment whose label matched total_bill, paid or due.

    If the same type and value is stated more than once (a repeated line, or "Bank Transfer Total"
    next to "Total"), only the best-matching, shortest-labelled one is kept.
    """
    best = {}     # (type, value) -> (segment, amount)
    order = []    # keys in order of first appearance
    for segment in ctx.segments:
        if segment.label_match.type is None:
            continue
        amount = next((t for t in segment.tokens if not t.is_percent and t.value is not None), None)
        if amount is None:
            continue
        key = (segment.label_match.type, amount.value)
        if key not in best:
            best[key] = (segment, amount)
            order.append(key)
        else:
            old = best[key][0]
            if (-segment.label_match.quality, len(segment.label_text)) < (-old.label_match.quality, len(old.label_text)):
                best[key] = (segment, amount)
    return [best[key] for key in order]


def reconciliation_score(ctx: Context) -> float:
    """1.0 if total = paid + due, 0.5 if that can't be tested, 0.0 if the numbers disagree."""
    found = {}
    for segment, amount in labeled_amounts(ctx):
        found.setdefault(segment.label_match.type, amount.value)
    if {"total_bill", "paid", "due"} <= found.keys():
        difference = abs(found["total_bill"] - (found["paid"] + found["due"]))
        return config.RECON_PASS if difference <= config.RECON_TOLERANCE else config.RECON_FAIL
    return config.RECON_UNTESTABLE
