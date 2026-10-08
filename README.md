# Medical Bill Amount Detector

**Pipeline:** input -> Step 1 extract -> Step 2 normalize -> Step 3 classify -> Step 4 final output
Text input needs no API key. Image input uses the Groq vision API and needs a key.

Quick start: run it on your own computer (Windows PowerShell)

Everything below is typed into PowerShell.

### Step 1. Open PowerShell in the project folder
Open the folder that contains `app.py` in File Explorer, click the address bar, type `powershell` and press Enter.

### Step 2. Install (once)
```
pip install -r requirements.txt
```
If `pip` is not recognised, use `python -m pip install -r requirements.txt`.

### Step 3. Add a Groq key (only for image input)
Create a free key at https://console.groq.com/keys, then run this, replacing `PASTE_YOUR_KEY_HERE`:
```
Set-Content -Path .env -Value "GROQ_API_KEY=PASTE_YOUR_KEY_HERE" -Encoding ascii
```
alternatively, if youre unsure about path, open the project folder, open powershell inside that folder, and do 
```
Set-Content .env "GROQ_API_KEY=your-key-here" -Encoding ascii
```
If you require my key for checking temporarily, feel free to email me at rayan.talukder@iitgn.ac.in.
The `.env` file is ignored by git and never uploaded. Skip this step if you only want to test text.

### Step 4. Test it. Choose Option A or Option B

#### Option A: no server (simplest, one window)

**Your own text.** Replace only what is inside the single quotes at the end:
```
python -c "import json,sys; from pipeline.runner import run_all as r; print(json.dumps(r(text=sys.argv[1]), indent=2))" 'Total: INR 1200 | Paid: 1000 | Due: 200'
```

**Your own image.** Put the image in the project folder and replace `bill.png` with its file name (or give a full path in quotes, e.g. `"C:\Users\You\Downloads\bill.png"`):
```
python -c "import json,sys; from pipeline.runner import run_all as r; print(json.dumps(r(image_bytes=open(sys.argv[1],'rb').read()), indent=2))" bill.png
```
Image input takes a few seconds (the model is called over the internet).

Both commands print the outputs of all four steps (`step1` to `step4`). For an image they also print `transcription`, the text that was read from the image, first. `step4` is the final answer.
#### Option B: run the web API (endpoints)

**Window 1: start the server and leave it open**
```
python -m uvicorn app:app
```
Wait until you see `Application startup complete`. This window stays busy; don't close it.

**Window 2: open a second PowerShell in the same project folder and send requests**

Your own text: replace only what is inside the quotes after `"text": `
```
Invoke-RestMethod -Method Post -Uri http://localhost:8000/process -ContentType "application/json" -Body '{"text": "Total: INR 1200 | Paid: 1000 | Due: 200"}' | ConvertTo-Json -Depth 5
```

Your own image: replace `bill.png` (use `curl.exe`, not `curl`; in PowerShell plain `curl` is a different tool):
```
curl.exe -X POST http://localhost:8000/process -F "file=@bill.png"
```

To see a single step, replace `/process` in the address with `/step1/extract`, `/step2/normalize` or `/step3/classify`.

**When finished:** click Window 1 and press `Ctrl+C`.
## 3. Live demo link

A demo is running at:

**https://washbasin-unleash-headset.ngrok-free.dev**

It is available while my computer is switched on and the server and tunnel are running (unlikely). But better to make your own ngrok demo and run from there. The steps are the same for both ways. Just make sure to use your own url wherever you see mine.

Open PowerShell (any folder) and set the link **once in each new window**:
```
$url = "https://washbasin-unleash-headset.ngrok-free.dev" or yours
```
If you open a new PowerShell window, run this line again; otherwise you will see `URL rejected: No host part in the URL`.

**Text** (replace only what is inside the quotes after `"text": `):
```
Invoke-RestMethod -Method Post -Uri "$url/process" -ContentType "application/json" -Headers @{"ngrok-skip-browser-warning"="true"} -Body '{"text": "Total: INR 1200 | Paid: 1000 | Due: 200"}' | ConvertTo-Json -Depth 5
```

**Image** (run it in the folder that contains your image; replace `bill.png`):
```
curl.exe -X POST "$url/process" -H "ngrok-skip-browser-warning: true" -F "file=@bill.png"
```

**Single steps:** replace `/process` with `/step1/extract`, `/step2/normalize` or `/step3/classify`.

The `ngrok-skip-browser-warning` header only stops ngrok's free plan from showing a warning page instead of JSON.

---
## 5. Writing your own input

### Text
- Separate amounts with `|`, a new line, or `;`. A single line such as `Total: 1200 Paid: 1000 Due: 200` also works, as does a table-like layout (`Total   1200`).
- Recognised labels include Total, Grand Total, Paid, Amount Paid, Advance, Received, Due, Balance, Balance Due, Outstanding, Pending and similar.
- OCR slips are tolerated: `T0tal`, `Pald`, `Rs l200`, `12o0`, `1NR12o0`, `Tptol`.
- Currency markers (`Rs`, `INR`, `$`, `₹`, `/-`) are optional.
- In Option A keep the single quotes around the text. If the text itself contains a single quote, type it twice (`''`).
- In JSON (Option B and the live link), write line breaks as `\n`: `{"text": "Total: 1200\nPaid: 1000\nDue: 200"}`.

### Image
- PNG, JPEG or WebP, up to about 3 MB.
- Printed bills, invoices and photographed receipts work best when the text is readable.
- If both an image and text are sent, the image is used.

---

## 6. API reference and output formats

Every endpoint accepts **either** JSON `{"text": "..."}` **or** a multipart form with an image in the field `file`.

| Endpoint | Method | Returns |
|---|---|---|
| `/step1/extract` | POST | Step 1 output |
| `/step2/normalize` | POST | Step 2 output |
| `/step3/classify` | POST | Step 3 output |
| `/process` | POST | Step 4 (final) output |
| `/health` | GET | `{"status": "ok"}` |

Each endpoint runs the pipeline from the start up to its step.

### Step 1: extract (raw numeric tokens)
```json
{
  "raw_tokens": ["1200", "1000", "200", "10%"],
  "currency_hint": "INR",
  "confidence": 1.0
}
```
Tokens are returned exactly as read (so `12o0` stays `12o0`). Percentages appear only here. `confidence` = how well the input was read.

### Step 2: normalize (fix OCR digits, convert to numbers)
```json
{
  "normalized_amounts": [1200, 1000, 200],
  "normalization_confidence": 1.0
}
```
`normalization_confidence` = how sure the conversion to numbers is.

### Step 3: classify (label by context)
```json
{
  "amounts": [
    {"type": "total_bill", "value": 1200},
    {"type": "paid", "value": 1000},
    {"type": "due", "value": 200}
  ],
  "confidence": 1.0
}
```
`confidence` = how sure the labelling is.

### Step 4: final output (with provenance)
```json
{
  "currency": "INR",
  "amounts": [
    {"type": "total_bill", "value": 1200, "source": "text: 'Total: INR 1200'"},
    {"type": "paid", "value": 1000, "source": "text: 'Paid: 1000'"},
    {"type": "due", "value": 200, "source": "text: 'Due: 200'"}
  ],
  "status": "ok"
}
```
`source` is the exact text the amount was taken from. For images it is the text read from the image.

### Example: messy OCR text
Input `T0tal: Rs l200 | Pald: 1000 | Due: 200` gives the same final output as above: `1200`, `1000`, `200` with sources `'T0tal: Rs l200'`, `'Pald: 1000'`, `'Due: 200'`.

### Example: a scanned invoice
A two-column invoice image with subtotal, tax, discount, dates, phone numbers and routing numbers returns only the three requested labels:
```json
{
  "currency": "INR",
  "amounts": [
    {"type": "total_bill", "value": 8480, "source": "text: 'Total: USD 8,480.00'"},
    {"type": "paid", "value": 0, "source": "text: 'Amount paid: USD 0.00'"},
    {"type": "due", "value": 8480, "source": "text: 'Balance Due: USD 8,480.00'"}
  ],
  "status": "ok"
}
```

---

## 7. Failure response

There is exactly one failure shape, always returned with HTTP 200:
```json
{"status": "no_amounts_found", "reason": "document too noisy"}
```

| `reason` | When |
|---|---|
| `no input provided` | Nothing was sent, or the request was malformed |
| `no numeric amounts found` | Empty text, or no usable numbers in it |
| `document too noisy` | Step 1 confidence below 0.35 |
| `no labeled amounts found` | Numbers exist but none follows a Total / Paid / Due style label |
| `image could not be read` | Unsupported or oversized image, missing or invalid key, or the model could not be reached |
| `input too long` | Text over 20,000 characters |

Any step may stop the run with this response. A bill whose amounts do not add up is **not** rejected; it only lowers the confidence.

---

## 8. Architecture

```
image --> Groq vision (two independent readings) --> text
text  --> cleaner --> Step 1 --> Step 2 (+ AI review if needed) --> Step 3 --> Step 4
```

One context object travels through the steps, so each step can use anything produced earlier.

| File | Job |
|---|---|
| `app.py` | FastAPI endpoints |
| `config.py` | All settings: label vocabulary, OCR lookalikes, confidence weights, thresholds |
| `pipeline/runner.py` | Runs the steps in order; handles the single failure response |
| `pipeline/vision.py` | Reads an image into text with the Groq vision API |
| `pipeline/cleaning.py` | Splits text into label/value segments, finds number-like tokens, fuzzy-matches labels |
| `pipeline/numbers.py` | Converts tokens such as `12o0` or `1,20,000` into numbers |
| `pipeline/step1_extract.py` ... `step4_assemble.py` | The four steps from the specification |
| `pipeline/review.py` | AI second look, only when total != paid + due |
| `pipeline/labeling.py`, `scoring.py` | Shared helpers (labelled amounts, reconciliation, weighted scores) |
| `tests/` | Automated tests |

Image reading uses `qwen/qwen3.8-27b` on Groq (change it with `GROQ_VISION_MODEL` in `.env` or `config.py`). The image is read twice with two differently worded prompts, in parallel. The second reading is used only to measure how stable the reading is.

---

## 9. How OCR errors and noise are handled

**Numbers.** Letters that look like digits are converted only inside tokens that are mostly digits: `l200` -> 1200, `12o0` -> 1200, `S0` -> 50. Words such as `T0tal` are never treated as numbers. Indian grouping (`1,20,000`), decimals (`1200.50`), `/-` suffixes and OCR'd separators (`1.200`) are understood.

**Labels.** Lookalike characters are folded to one symbol on both sides before comparing, so `Pald` matches `Paid` and `T0tal` matches `Total`. Genuine typos are tolerated by counting wrong, missing or extra characters: up to 2 for longer words (total, balance, outstanding) and 1 for short ones (paid, due). Two wrong characters in a three-letter word would match almost anything, so short words stay strict.

**Currency markers.** `Rs`, `Rs.`, `INR`, `$`, `₹` and `/-` are stripped, including garbled forms (`1NR`, `lNR`, `R5`).

**Not amounts.** The following are ignored:
- dates (`Feb 13th, 2021`, `13 Feb 2021`, `13.02.2021`)
- lines labelled invoice, phone, date, address, routing, account and similar
- street numbers, zip codes and numbers longer than 9 digits that merely sit in the text
- `Sub Total`, `Tax`, `GST` and `Discount` lines, which are never labelled as the Total

A number is kept only if its label is recognised, it carries a currency marker, or it follows a `label:`.

**Layouts.** A value on the line below its label (`Amount DUE` then `$1,745.00`) is paired with that label. Two-column layouts, repeated lines and `Bank Transfer Total` next to `Total` are handled; if the same type and value is stated twice it is reported once.

---

## 10. AI review step

Runs only when total != paid + due; clean bills cost no extra calls. It is designed so that the AI cannot invent a number:

1. **Code proposes the alternatives**, not the AI: numbers with exactly one misread digit (0/8, 1/7, 3/8, 4/9, 5/6, 6/8 and so on) that would make the bill balance.
2. The AI is **not told about the arithmetic**. It only answers "which amount is actually printed there?" (looking at the image when there is one) and may answer "I cannot tell".
3. It is asked **three times**, with the options in different orders. A change needs the same answer all three times.
4. A change is applied only if **exactly one** alternative is confirmed, **at most one number** changes, and the bill **balances afterwards**.

Otherwise the numbers stay as read and the confidence drops. For typed text (no image) the AI has no extra evidence, so it rarely changes anything. The review does its real work on images. An AI-corrected value lowers the Step 2 confidence, and `source` still quotes what the document said.

---

## 11. Confidence scores

Each score measures its own step. It is a weighted sum of signals between 0 and 1, rounded to 2 decimals. All weights are in `config.py`. They are hand-set heuristics, not calibrated probabilities.

### Step 1: input read correctly
`confidence = 0.35*cleanliness + 0.30*label_recognition + 0.15*structure + 0.20*stability`

| Signal | Meaning |
|---|---|
| cleanliness | 1 - (words that needed a repair / all words) |
| label_recognition | average label match quality over the lines containing amounts |
| structure | share of lines that read as a clean `label: value` pair (0.5 if no separator) |
| stability | images only: agreement between two independent readings of the image. For text it is skipped and the other weights are rescaled |

Below **0.35** the run stops with `document too noisy`.

### Step 2: normalization correct
`normalization_confidence = 0.45*token_quality + 0.30*reconciliation + 0.25*edit_penalty`

| Signal | Values |
|---|---|
| token_quality (average) | 1.0 untouched, 0.85 repaired by rules, 0.70 corrected by AI |
| reconciliation | 1.0 if total = paid + due, 0.5 if it cannot be tested, 0.0 if the amounts disagree |
| edit_penalty | 1.0 with no AI edit, 0.7 with one |

### Step 3: classification correct
`confidence = 0.35*match_quality + 0.20*uniqueness + 0.20*coverage + 0.25*consistency`

| Signal | Meaning |
|---|---|
| match_quality | average label match: 1.0 exact, 0.9 after lookalike folding, lower for typo matches |
| uniqueness | share of labels that did not match two types equally well |
| coverage | labelled amounts / all detected amounts |
| consistency | the same reconciliation score as Step 2 |

---

## 12. Assumptions and limits

- Currency is always reported as `INR`, as specified, even if the bill shows another symbol. This is beacause it was difficult to identify currencies like dollar where it can be USD or CAD, and i read about Plum and it seemed like they only function in India. This is visible in the test image in the folder, where the currency is dollar but returned as INR. 
- Only `total_bill`, `paid` and `due` are labelled. Other amounts (subtotal, tax, line items) appear in Steps 1-2 but are not labelled.
- Percentages appear in Step 1 only.
- Reconciliation can only be checked when all three of total, paid and due are present.
- Image quality matters: very blurry or cropped images depend on the vision model's reading, and an image request can occasionally fail on the first attempt (rate limit or timeout); retrying works.
- The vision model is a Groq preview model and may change; update `GROQ_VISION_MODEL` if it is retired.
- The image model API limits make it so that you can only give an input every 20 seconds. If you get the error {"status":"no_amounts_found","reason":"image could not be read"}, please wait for 30 seconds and run it again to see if it really is an error or API limits
- Amounts across multiple receipts are summed, not itemized. If a person has several receipts, the agent reports combined totals (e.g. total due across all receipts) rather than a per-receipt breakdown. A question like "which receipt still has a balance" or "is receipt #2 paid off" isn't answerable with the current aggregation — only the combined figure is.
---

## 13. Tests

```
python -m unittest discover -s tests
```
The image and review tests use a fake model, so no key or internet is needed. All tests should pass; lines such as `review vote failed: down` in the output are expected (they come from a test that simulates the model being unavailable).

---

## 14. Troubleshooting

| Message | Meaning and fix |
|---|---|
| `uvicorn is not recognized` | Use `python -m uvicorn app:app` (with `python -m`) |
| `python is not recognized` | Try `py` instead of `python`, or reinstall Python and tick "Add to PATH" |
| `Failed to connect to localhost:8000` | The server is not running. Start Window 1 first (Option B) |
| `address already in use` | A server is already running on port 8000. Close it, or use that one |
| `URL rejected: No host part in the URL` | `$url` is not set in this window. Run the `$url = "..."` line first (Section 3) |
| `{"detail":"Not Found"}` | Wrong endpoint name. Use `/step1/extract`, `/step2/normalize`, `/step3/classify` or `/process` |
| `"reason": "image could not be read"` | Missing or invalid Groq key in `.env`, unsupported or oversized image, or a temporary Groq error. The server window prints the exact cause on a line beginning `image transcription failed`. Retry once |
| `"reason": "no labeled amounts found"` | Numbers were found but none follows a Total / Paid / Due style label |
| `"reason": "document too noisy"` | The input was too garbled to trust |
| The live link returns HTML or does not respond | The author's tunnel is offline. Use Section 2 to run locally |
