"""Turn a raw token such as '12o0', 'l200' or '1,20,000' into a number."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

import config
from pipeline.models import Number


def to_number(raw: str) -> Optional[Tuple[Number, bool]]:
    """Return (value, repaired) or None if the token cannot be read as a number.

    `repaired` is True when a letter had to be swapped for a digit or a separator was guessed.
    """
    text = raw.strip()
    repaired = any(ch.isalpha() for ch in text)
    text = "".join(config.DIGIT_FIXES.get(ch, ch) for ch in text)
    if not re.fullmatch(r"[0-9.,]+", text):
        return None

    text = text.replace(",", "")           # thousands separators (1,200 or 1,20,000)
    if text.count(".") > 1:                 # 1.20.000 -> separators only
        text, repaired = text.replace(".", ""), True
    elif "." in text:
        whole, fraction = text.split(".")
        if len(fraction) == 3 and 1 <= len(whole) <= 3 and whole != "0":
            text, repaired = whole + fraction, True   # "1.200" is almost surely an OCR'd "1,200"

    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    number: Number = int(value) if value == value.to_integral_value() else float(value)
    return number, repaired
