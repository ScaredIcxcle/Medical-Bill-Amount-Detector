"""Runs the four steps in order. Any step may stop the run with the single guardrail."""
from __future__ import annotations

from typing import Optional

import config
from pipeline import step1_extract, step2_normalize, step3_classify, step4_assemble, vision
from pipeline.errors import GuardrailExit
from pipeline.models import Context

STEPS = [step1_extract, step2_normalize, step3_classify, step4_assemble]


def guardrail(reason: str) -> dict:
    return {"status": "no_amounts_found", "reason": reason}


def _make_context(text: Optional[str], image_bytes: Optional[bytes]) -> Context:
    """Read the image (if any) into text and build the context that travels through the steps."""
    if image_bytes:
        text, stability = vision.transcribe_image(image_bytes)
        return Context(
            text=text, source_type=config.IMAGE_SOURCE_LABEL, stability=stability,
            image_bytes=image_bytes, image_mime=vision.detect_image_type(image_bytes),
        )
    return Context(text=text or "", source_type="text")


def run_pipeline(text: Optional[str] = None, upto: int = 4, image_bytes: Optional[bytes] = None) -> dict:
    """Run steps 1..upto and return the output of the last step run (or the guardrail JSON).

    Give either `text` (typed or simulated-OCR text) or `image_bytes` (a scanned bill).
    An image is first read into text with the Groq vision model, then follows the same steps.
    """
    try:
        ctx = _make_context(text, image_bytes)
        output: dict = {}
        for number, step in enumerate(STEPS, start=1):
            output = step.run(ctx)
            ctx.outputs[number] = output
            if number == upto:
                break
        return output
    except GuardrailExit as stop:
        return guardrail(stop.reason)


def run_all(text: Optional[str] = None, image_bytes: Optional[bytes] = None) -> dict:
    """Run every step once and return all the outputs together (handy for demos and debugging)."""
    result: dict = {}
    try:
        ctx = _make_context(text, image_bytes)
        if image_bytes:
            result["transcription"] = ctx.text
        for number, step in enumerate(STEPS, start=1):
            result[f"step{number}"] = step.run(ctx)
    except GuardrailExit as stop:
        result["stopped"] = guardrail(stop.reason)
    return result