"""Plain data containers shared by all steps."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

Number = Union[int, float]


@dataclass
class LabelMatch:
    type: Optional[str] = None   # "total_bill" / "paid" / "due" / None
    quality: float = 0.0
    method: str = "none"         # "exact" / "folded" / "fuzzy" / "none"
    near_tie: bool = False       # another type matched almost equally well


@dataclass
class Token:
    raw: str                     # exactly as read, e.g. "12o0" or "10%"
    is_percent: bool
    segment_index: int = -1
    value: Optional[Number] = None   # filled in by Step 2
    repaired: bool = False
    quality: float = 1.0


@dataclass
class Segment:
    raw: str                     # the original piece of text, used as provenance
    label_text: str
    has_separator: bool          # label and value were split by ':' or '='
    label_match: LabelMatch
    tokens: list[Token] = field(default_factory=list)


@dataclass
class Context:
    """One object that travels through the whole pipeline; every step can read all of it."""
    text: str
    source_type: str = "text"            # "text" now; "image" when OCR input is added
    stability: Optional[float] = None    # image transcription agreement (images only)
    ai_edits: int = 0                    # number of AI corrections applied
    image_bytes: Optional[bytes] = None  # the original image (images only), used by the AI review step
    image_mime: Optional[str] = None
    segments: list[Segment] = field(default_factory=list)
    outputs: dict[int, dict] = field(default_factory=dict)

    def all_tokens(self) -> list[Token]:
        return [t for s in self.segments for t in s.tokens]

    def amount_tokens(self) -> list[Token]:
        """Tokens that were successfully converted to a number (percentages excluded)."""
        return [t for t in self.all_tokens() if not t.is_percent and t.value is not None]
