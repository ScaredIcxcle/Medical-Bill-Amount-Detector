# Medical Bill Amount Detector (work in progress)

Pipeline: text -> Step 1 extract -> Step 2 normalize -> Step 3 classify -> Step 4 final JSON.
Currently supports typed / simulated-OCR text. Image input (Groq vision) and AI review come next.

## Setup
    pip install -r requirements.txt
    uvicorn app:app --reload

## Try it
    curl -X POST localhost:8000/process -H "Content-Type: application/json" \
      -d '{"text": "T0tal: Rs l200 | Pald: 1000 | Due: 200"}'

Endpoints: /step1/extract, /step2/normalize, /step3/classify, /process (final output).
Every failure returns {"status": "no_amounts_found", "reason": "..."}.

## Tests
    python -m unittest discover -s tests -v
