"""Web API. Start with:  python -m uvicorn app:app --reload

Every endpoint accepts EITHER
  * JSON:            {"text": "Total: 1200 | Paid: 1000 | Due: 200"}
  * multipart form:  file=<bill image>   (and/or text=...)   - an image wins if both are sent
"""
from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from pipeline.runner import guardrail, run_pipeline

app = FastAPI(title="Medical Bill Amount Detector")


@app.exception_handler(RequestValidationError)
async def bad_request(request: Request, exc: RequestValidationError):
    # Even malformed requests answer with the spec's single guardrail shape.
    return JSONResponse(guardrail("no input provided"))


async def read_input(request: Request):
    """Return (text, image_bytes); either may be None."""
    content_type = request.headers.get("content-type", "")
    try:
        if "multipart/form-data" in content_type:
            form = await request.form()
            upload = form.get("file") or form.get("image")
            image = await upload.read() if upload is not None and hasattr(upload, "read") else None
            text = form.get("text")
            return (text if isinstance(text, str) else None), (image or None)
        body = await request.json()
    except Exception:
        return None, None
    text = body.get("text") if isinstance(body, dict) else None
    return (text if isinstance(text, str) else None), None


async def handle(request: Request, upto: int):
    text, image = await read_input(request)
    if text is None and image is None:
        return guardrail("no input provided")
    # run in a worker thread so a slow vision call never blocks other requests
    return await run_in_threadpool(run_pipeline, text, upto, image)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/step1/extract")
async def step1(request: Request):
    return await handle(request, 1)


@app.post("/step2/normalize")
async def step2(request: Request):
    return await handle(request, 2)


@app.post("/step3/classify")
async def step3(request: Request):
    return await handle(request, 3)


@app.post("/process")
async def process(request: Request):
    return await handle(request, 4)
