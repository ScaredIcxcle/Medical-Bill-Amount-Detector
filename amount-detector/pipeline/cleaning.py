"""Cleaning helpers: split text into segments, spot number-like tokens, match labels.

Everything here is plain Python (re only). Nothing in this file calls an AI model.
"""
from __future__ import annotations

import re

import config
from pipeline.models import LabelMatch, Segment, Token

# Characters that separate segments. Commas are NOT here because they appear inside numbers.
_SEGMENT_SPLIT = re.compile(r"[|\n;]+")
# Separator between a label and its value.
_LABEL_SEP = re.compile(r"[:=]")
_CURRENCY_WORDS = ("rupees", "rupee", "inr", "rs")
_CURRENCY_SUFFIX = re.compile(r"(?:/-|/=)$")
_ALLOWED_NUMBER_CHARS = set("0123456789,.") | set(config.DIGIT_FIXES)
# Any word-like piece of the document (used for counting tokens in the confidence score).
WORD_PATTERN = re.compile(r"[A-Za-z0-9₹$][A-Za-z0-9₹$.,%/-]*")

_FOLD_TABLE = str.maketrans(config.LABEL_FOLD)


# ---------------------------------------------------------------------------
# Label folding and matching
# ---------------------------------------------------------------------------
def fold(text: str) -> str:
    """Lowercase and collapse OCR lookalikes so 'Pald' == 'Paid' and 'T0tal' == 'Total'."""
    return text.lower().translate(_FOLD_TABLE)


def edit_distance(a: str, b: str) -> int:
    """Number of single-character changes (wrong, missing or extra letter) needed to turn a into b."""
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _normalize_label(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


_EXCLUDED_FOLDED = {fold(w) for w in config.EXCLUDED_LABEL_WORDS}
_ID_FOLDED = {fold(w) for w in config.ID_LABEL_WORDS}


def is_identifier_label(label_text: str) -> bool:
    words = _normalize_label(label_text).split()
    return any(fold(w) in _ID_FOLDED for w in words)


def _score_phrase(label_words: list[str], phrase: str):
    """How well does `phrase` match somewhere inside the label?

    Returns (quality, method, end_index) or None. end_index is the word position where the
    match ends (used so that 'Total Amount Paid' favours 'paid' over 'total').
    """
    p_words = phrase.split()
    n = len(p_words)
    best = None
    for start in range(len(label_words) - n + 1):
        window = label_words[start:start + n]
        if window == p_words:
            cand = (config.LABEL_EXACT, "exact", start + n)
        elif [fold(w) for w in window] == [fold(w) for w in p_words]:
            cand = (config.LABEL_FOLDED, "folded", start + n)
        else:
            continue
        if best is None or cand[0] > best[0] or (cand[0] == best[0] and cand[2] > best[2]):
            best = cand
    if best:
        return best

    # Fuzzy fallback: allow a few wrong, missing or extra characters (see config.MAX_LABEL_DIFFS).
    best = None  # (differences, end_index)
    for start in range(len(label_words) - n + 1):
        window = " ".join(label_words[start:start + n])
        diffs = edit_distance(fold(window), fold(phrase))
        if best is None or diffs < best[0]:
            best = (diffs, start + n)
    if best is None:
        return None
    allowed = config.MAX_LABEL_DIFFS if len(phrase) >= config.SHORT_PHRASE_LENGTH else config.MAX_LABEL_DIFFS_SHORT
    if best[0] <= allowed:
        quality = min(1 - best[0] / len(phrase), config.LABEL_FUZZY_MAX)
        return (quality, "fuzzy", best[1])
    return None


def match_label(label_text: str) -> LabelMatch:
    """Map a label like 'T0tal' or 'Balance Due' to total_bill / paid / due."""
    label = _normalize_label(label_text)
    if not label:
        return LabelMatch()
    label_words = label.split()
    if any(fold(w) in _EXCLUDED_FOLDED for w in label_words):
        return LabelMatch()

    per_type = {}  # type -> (quality, phrase_len, end, method)
    for type_, phrases in config.LABEL_VOCAB.items():
        for phrase in phrases:
            scored = _score_phrase(label_words, phrase)
            if scored is None:
                continue
            quality, method, end = scored
            candidate = (quality, len(phrase.split()), end, method)
            if type_ not in per_type or candidate[:3] > per_type[type_][:3]:
                per_type[type_] = candidate
    if not per_type:
        return LabelMatch()

    ranked = sorted(per_type.items(), key=lambda kv: kv[1][:3], reverse=True)
    best_type, best = ranked[0]
    near_tie = False
    if len(ranked) > 1:
        runner = ranked[1][1]
        near_tie = (
            abs(best[0] - runner[0]) < config.NEAR_TIE and best[1] == runner[1] and best[2] == runner[2]
        )
    return LabelMatch(type=best_type, quality=best[0], method=best[3], near_tie=near_tie)


# ---------------------------------------------------------------------------
# Number-like tokens
# ---------------------------------------------------------------------------
_CURRENCY_SYMBOLS = ("₹", "$")


def _strip_currency_prefix(chunk: str):
    """Remove a leading currency marker. Returns (rest, found).

    Handles ₹, $, Rs, Rs., INR, rupees - even when OCR garbled the letters (1NR, lNR, R5).
    """
    for symbol in _CURRENCY_SYMBOLS:
        if chunk.startswith(symbol):
            return chunk[len(symbol):], True
    for word in _CURRENCY_WORDS:
        if fold(chunk[:len(word)]) == fold(word):
            rest = chunk[len(word):]
            return (rest[1:] if rest.startswith(".") else rest), True
    return chunk, False


def clean_chunk(chunk: str):
    """Strip brackets, currency markers and '/-'. Returns (cleaned_text, had_currency_marker)."""
    chunk = chunk.strip("()[]{}<>\"'")
    chunk, had_currency = _strip_currency_prefix(chunk)
    if _CURRENCY_SUFFIX.search(chunk):
        chunk, had_currency = _CURRENCY_SUFFIX.sub("", chunk), True
    return chunk.strip("()[]{}<>\"'").rstrip(",;."), had_currency


def is_numeric_like(token: str) -> bool:
    """True for tokens that are mostly digits, e.g. '1200', 'l200', '12o0', '1,20,000', '10%'.

    Words such as 'T0tal' are rejected because they contain letters that are not digit lookalikes,
    and tokens with more letters than digits (e.g. 'Sol') are rejected.
    """
    if not token:
        return False
    core = token[:-1] if token.endswith("%") else token
    if not core or not (core[0].isalnum() and core[-1].isalnum()):
        return False
    if any(ch not in _ALLOWED_NUMBER_CHARS for ch in core):
        return False
    alnum = [ch for ch in core if ch.isalnum()]
    if len(alnum) > config.MAX_AMOUNT_DIGITS:
        return False
    digits = sum(ch.isdigit() for ch in alnum)
    letters = len(alnum) - digits
    return digits >= 1 and digits >= letters


# ---------------------------------------------------------------------------
# Segments
# ---------------------------------------------------------------------------
_MONTH = re.compile(
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
    r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)",
    re.IGNORECASE,
)
_ORDINAL = re.compile(r"\d{1,2}(?:st|nd|rd|th)", re.IGNORECASE)
_DOTTED_DATE = re.compile(r"\d{1,2}\.\d{1,2}\.\d{2,4}")


def _is_date_word(chunk: str) -> bool:
    word = chunk.strip(".,;:()")
    return bool(_MONTH.fullmatch(word) or _ORDINAL.fullmatch(word))


def _numeric_chunks(text: str):
    """(start, end, cleaned, has_currency) for every whitespace-separated chunk that looks like an amount.

    Numbers that belong to a date ("Feb 13th, 2021", "13 Feb 2021", "13.02.2021") are left out.
    """
    items = []
    for m in re.finditer(r"\S+", text):
        cleaned, had_currency = clean_chunk(m.group())
        numeric = is_numeric_like(cleaned) and not _DOTTED_DATE.fullmatch(cleaned)
        items.append((m.start(), m.end(), cleaned, had_currency, _is_date_word(m.group()), numeric))

    in_date = [False] * len(items)      # a number next to a month/ordinal, or right after a date number
    for i, item in enumerate(items):
        if item[5]:
            in_date[i] = (
                (i > 0 and items[i - 1][4]) or (i + 1 < len(items) and items[i + 1][4]) or (i > 0 and in_date[i - 1])
            )

    found = []
    previous_was_bare_marker = False   # e.g. "Rs" or "$" standing alone before the number
    for i, (start, end, cleaned, had_currency, _, numeric) in enumerate(items):
        if numeric and not in_date[i]:
            found.append((start, end, cleaned, had_currency or previous_was_bare_marker))
        previous_was_bare_marker = had_currency and cleaned == ""
    return found


def _take_segment(text: str, borrowed_label: str = ""):
    """Read one 'label: value' segment from the start of `text`.

    Returns (segment or None, leftover_text). Leftover text begins a new segment, which is how
    'Total: 1200 Paid: 1000 Due: 200' (no pipes) is still split correctly.
    `borrowed_label` is the text line just above, used when a value stands alone under its label
    (a stacked layout such as 'Amount DUE' on one line and '$1,745.00' on the next).
    """
    sep = _LABEL_SEP.search(text)
    if sep:
        label_text, value_start, has_sep = text[:sep.start()], sep.end(), True
    else:
        first = _numeric_chunks(text)
        if not first:
            return None, ""
        value_start = first[0][0]
        label_text, has_sep = text[:value_start], False

    value_text = text[value_start:]
    numbers = _numeric_chunks(value_text)
    if not numbers:
        return None, ""

    first_end = numbers[0][1]
    remainder = value_text[first_end:]
    if _LABEL_SEP.search(remainder):      # another "label:" follows on the same line
        end, leftover, used = first_end, remainder.strip(), [numbers[0]]
    else:
        end, leftover, used = len(value_text), "", numbers

    raw = text[:value_start + end].strip()
    label_blank = clean_chunk(label_text.strip())[0] == ""   # nothing, or just "Rs" / "$"
    if label_blank and borrowed_label:
        label_text, raw = borrowed_label, f"{borrowed_label} {raw}".strip()
        label_blank = False
        has_sep = False

    if is_identifier_label(label_text):   # invoice no, phone, date ... are not money
        return None, leftover

    match = match_label(label_text)
    anchored = has_sep and not label_blank   # "Something: <number>" is a labelled value
    # Keep a number only if its label is known, it carries a currency marker, or it follows "label:".
    # This drops street numbers, zip codes and phone numbers that merely sit in the text.
    kept = [c for (_, _, c, has_currency) in used if match.type is not None or has_currency or anchored]
    if not kept:
        return None, leftover

    segment = Segment(
        raw=raw,
        label_text=label_text.strip(),
        has_separator=has_sep,
        label_match=match,
        tokens=[Token(raw=c, is_percent=c.endswith("%")) for c in kept],
    )
    return segment, leftover


def parse_segments(text: str) -> list[Segment]:
    segments: list[Segment] = []
    pending = ""   # the last short text-only line, a possible label for a value on the next line
    for part in _SEGMENT_SPLIT.split(text):
        part = part.strip()
        if not part:
            continue
        if not _numeric_chunks(part):
            pending = part if len(part.split()) <= 6 and not re.search(r"\d", part) else ""
            continue
        rest, first_piece = part, True
        while rest:
            segment, rest = _take_segment(rest, pending if first_piece else "")
            first_piece = False
            if segment is not None:
                segments.append(segment)
        pending = ""
    for index, segment in enumerate(segments):
        for token in segment.tokens:
            token.segment_index = index
    return segments
