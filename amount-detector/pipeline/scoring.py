"""Shared helper that turns signals + weights into a confidence score."""
from __future__ import annotations

from typing import Optional


def weighted_score(weights: dict[str, float], signals: dict[str, Optional[float]]) -> float:
    """Weighted average of the signals, clamped to 0..1.

    A signal that is None is skipped and the remaining weights are rescaled, so the
    result is still on a 0..1 scale (used for the image-only 'stability' signal).
    """
    used = {name: w for name, w in weights.items() if signals.get(name) is not None}
    total_weight = sum(used.values())
    if total_weight == 0:
        return 0.0
    score = sum(w * signals[name] for name, w in used.items()) / total_weight
    return max(0.0, min(1.0, score))
