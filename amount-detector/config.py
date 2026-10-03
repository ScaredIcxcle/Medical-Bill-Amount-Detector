"""All tunable settings live here: vocabulary, OCR lookalikes, confidence weights, thresholds."""
import os
from pathlib import Path


def _load_env_file() -> None:
    """Read KEY=VALUE lines from a .env file next to this file (keeps the API key out of the code)."""
    path = Path(__file__).resolve().parent / ".env"
    if not path.exists():
        return
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeError:
            continue
    else:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env_file()

CURRENCY = "INR"  # the task guarantees INR, so this is fixed

# ---- Input limits ----------------------------------------------------------
MAX_TEXT_CHARS = 20000
MAX_AMOUNT_DIGITS = 9  # a token with more digit characters (e.g. a phone number) is not an amount

# ---- OCR lookalikes ----------------------------------------------------------
# Used ONLY inside tokens that are mostly digits (so "l200" -> 1200, "T0tal" is never touched).
DIGIT_FIXES = {
    "l": "1", "I": "1", "i": "1",
    "O": "0", "o": "0",
    "S": "5", "s": "5",
    "B": "8",
    "Z": "2", "z": "2",
}

# Used ONLY on labels: lookalike characters are folded to one shared symbol on BOTH sides
# before comparing, so "Pald" and "Paid" fold to the same text.
LABEL_FOLD = {"1": "l", "i": "l", "0": "o", "5": "s", "8": "b", "2": "z"}

# ---- Label vocabulary (maps label text -> the spec's three types) ------------
LABEL_VOCAB = {
    "total_bill": [
        "total", "total bill", "grand total", "bill total", "bill amount",
        "net total", "net amount", "gross total", "total amount",
    ],
    "paid": [
        "paid", "amount paid", "paid amount", "received", "amount received",
        "advance", "advance paid", "payment received",
    ],
    "due": [
        "due", "amount due", "balance", "balance due", "outstanding",
        "pending", "remaining", "total due", "amount payable", "payable",
    ],
}

# Labels containing these words are never matched to a type (a "Sub Total" is not the Total).
EXCLUDED_LABEL_WORDS = {
    "sub", "subtotal", "tax", "gst", "cgst", "sgst", "igst",
    "discount", "concession", "rebate", "refund", "round", "roundoff",
}

# Segments labelled with these words hold identifiers, not money, and are skipped entirely.
ID_LABEL_WORDS = {
    "invoice", "receipt", "phone", "mobile", "tel", "date", "gstin",
    "uhid", "mrn", "id", "no", "age", "pin", "pincode",
    "address", "zip", "zipcode", "fax", "ph", "email",
    "routing", "aba", "account", "acct", "swift", "iban", "ifsc", "track",
}

# ---- Label matching quality ----------------------------------------------------
LABEL_EXACT = 1.0        # label matches a vocabulary phrase as written
LABEL_FOLDED = 0.9       # matches only after lookalike folding (e.g. "Pald")
LABEL_FUZZY_MAX = 0.89   # fuzzy matches never score above this

# How many characters may be wrong, missing or extra in a label and it still counts as a match.
# (Lookalike swaps such as 0/o, 1/l/i, 5/s are handled separately and cost nothing.)
MAX_LABEL_DIFFS = 2          # for vocabulary words of SHORT_PHRASE_LENGTH letters or more
MAX_LABEL_DIFFS_SHORT = 1    # for shorter words such as "paid" and "due"
SHORT_PHRASE_LENGTH = 5
NEAR_TIE = 0.05          # two types this close in quality (and equally specific) are a near-tie

# ---- Per-token quality (Step 2) ------------------------------------------------
TOKEN_UNTOUCHED = 1.0
TOKEN_RULE_FIXED = 0.85
TOKEN_AI_FIXED = 0.70    # used when the AI review layer is added
AI_EDIT_PENALTY = 0.70   # edit_penalty signal when one AI edit was made

# ---- Reconciliation signal (total = paid + due) ----------------------------------
RECON_PASS = 1.0
RECON_UNTESTABLE = 0.5   # not all of total/paid/due present
RECON_FAIL = 0.0
RECON_TOLERANCE = 0.01

# ---- Confidence weights (each set sums to 1.0) -----------------------------------
# Step 1: input read correctly. 'stability' only exists for images; for text it is
# skipped and the other weights are rescaled automatically.
STEP1_WEIGHTS = {"cleanliness": 0.35, "label_recognition": 0.30, "structure": 0.15, "stability": 0.20}
# Step 2: normalisation correct
STEP2_WEIGHTS = {"token_quality": 0.45, "reconciliation": 0.30, "edit_penalty": 0.25}
# Step 3: classification correct
STEP3_WEIGHTS = {"match_quality": 0.35, "uniqueness": 0.20, "coverage": 0.20, "consistency": 0.25}

# Step 1 confidence below this means the document is too noisy to continue.
NOISY_THRESHOLD = 0.35


# ---- Image input (Groq vision) -----------------------------------------------------
# The API key is NOT stored here. Put it in a file named .env next to this file:  GROQ_API_KEY=...
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_VISION_MODEL = os.environ.get("GROQ_VISION_MODEL", "qwen/qwen3.8-27b")
GROQ_REASONING_EFFORT = os.environ.get("GROQ_REASONING_EFFORT", "none")  # "none" = plain reading mode; "" = don't send
GROQ_TIMEOUT_SECONDS = 30
GROQ_RETRIES = 1                    # one extra attempt on a timeout / rate limit / server error
MAX_IMAGE_BYTES = 3_000_000         # Groq allows ~4 MB of base64, which is about 3 MB of image
IMAGE_SOURCE_LABEL = "text"         # provenance prefix for text read from an image (spec shows "text:")



# ---- AI review step (Step 2) --------------------------------------------------------
# Runs ONLY when total != paid + due. The AI never writes a number: it chooses between the
# value as read and a code-generated alternative (one misread digit), and must give the same
# answer three times in a row. At most one number is changed per document.
REVIEW_ENABLED = True
REVIEW_VOTES = 3
REVIEW_MAX_FIXES = 3     # if more than this many single-digit fixes would balance the bill, it is too ambiguous
# Digits that OCR commonly mixes up (each pair works in both directions).
REVIEW_PAIRS = ["08", "06", "17", "27", "38", "49", "56", "68", "89", "35"]