"""Image-path tests. The Groq call is replaced by a fake, so no internet or API key is needed."""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from pipeline import vision  # noqa: E402
from pipeline.runner import run_pipeline  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100

INVOICE_SAME_LINE = """MEDICAL BILLING INVOICE
Kemba Harris
(555) 595-5999
11 Rosewood Drive,
Collingwood, NY 33580
INVOICE NUMBER: 12245
DATE: 07/01/23
Amount DUE: $1,745.00
Full Check Up: $745.00
Ear & Throat Examination: $1,000.00
SUB TOTAL: $745.00
TAX RATE: 9%
TAX: $157.05
TOTAL: $1,902.05"""

INVOICE_STACKED = """MEDICAL BILLING INVOICE
Kemba Harris
(555) 595-5999
11 Rosewood Drive,
Collingwood, NY 33580
INVOICE NUMBER
12245
Amount DUE
$1,745.00
SUB TOTAL
$745.00
TAX
$157.05
TOTAL
$1,902.05"""


def fake_reader(text):
    return mock.patch.object(vision, "_call_groq", return_value=text)


class ImagePipeline(unittest.TestCase):
    def test_spec_ocr_sample_from_image(self):
        with fake_reader("T0tal: Rs l200 | Pald: 1000 | Due: 200"):
            r = run_pipeline(image_bytes=PNG)
        self.assertEqual([(a["type"], a["value"]) for a in r["amounts"]],
                         [("total_bill", 1200), ("paid", 1000), ("due", 200)])

    def test_invoice_same_line_layout(self):
        with fake_reader(INVOICE_SAME_LINE):
            r = run_pipeline(image_bytes=PNG)
        self.assertEqual({a["type"]: a["value"] for a in r["amounts"]}, {"due": 1745, "total_bill": 1902.05})

    def test_invoice_stacked_layout(self):
        with fake_reader(INVOICE_STACKED):
            r = run_pipeline(image_bytes=PNG)
        self.assertEqual({a["type"]: a["value"] for a in r["amounts"]}, {"due": 1745, "total_bill": 1902.05})
        self.assertEqual(r["amounts"][0]["source"], "text: 'Amount DUE $1,745.00'")

    def test_noise_numbers_are_not_amounts(self):
        with fake_reader(INVOICE_SAME_LINE):
            raw = run_pipeline(image_bytes=PNG, upto=1)["raw_tokens"]
        for noise in ("555", "11", "33580", "12245"):
            self.assertNotIn(noise, raw)

    def test_identical_readings_give_full_stability(self):
        self.assertEqual(vision.reading_agreement("Total: 1200 Paid: 1000", "Total 1200 | Paid 1000"), 1.0)
        self.assertLess(vision.reading_agreement("Total: 1200", "Total: 1700"), 1.0)


class ImageGuardrails(unittest.TestCase):
    def test_not_an_image(self):
        self.assertEqual(run_pipeline(image_bytes=b"hello world"),
                         {"status": "no_amounts_found", "reason": "image could not be read"})

    def test_too_large(self):
        with mock.patch.object(config, "MAX_IMAGE_BYTES", 50):
            self.assertEqual(run_pipeline(image_bytes=PNG)["reason"], "image could not be read")

    def test_groq_failure(self):
        with mock.patch.object(vision, "_call_groq", side_effect=vision.VisionError("boom")):
            self.assertEqual(run_pipeline(image_bytes=PNG)["reason"], "image could not be read")

    def test_missing_api_key(self):
        with mock.patch.dict(os.environ, {}, clear=True), mock.patch.object(vision, "GROQ_API_KEY", ""):
            self.assertEqual(run_pipeline(image_bytes=PNG)["reason"], "image could not be read")

    def test_second_reading_failing_is_not_fatal(self):
        def flaky(image, mime, prompt, temperature):
            if prompt == vision.PROMPT_CHECK:
                raise vision.VisionError("second call failed")
            return "Total: 1200 | Paid: 1000 | Due: 200"
        with mock.patch.object(vision, "_call_groq", side_effect=flaky):
            self.assertEqual(run_pipeline(image_bytes=PNG)["status"], "ok")

    def test_image_with_no_amounts(self):
        with fake_reader("Thank you for visiting"):
            self.assertEqual(run_pipeline(image_bytes=PNG)["status"], "no_amounts_found")


try:
    from fastapi.testclient import TestClient
    from app import app
except ImportError:  # httpx / fastapi not installed: skip the API tests
    TestClient = None


@unittest.skipIf(TestClient is None, "fastapi test client not installed")
class Api(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_json_text(self):
        r = self.client.post("/process", json={"text": "Total: 1200 | Paid: 1000 | Due: 200"})
        self.assertEqual(r.json()["status"], "ok")

    def test_image_upload(self):
        with fake_reader("T0tal: Rs l200 | Pald: 1000 | Due: 200"):
            r = self.client.post("/process", files={"file": ("bill.png", PNG, "image/png")})
        self.assertEqual(r.json()["status"], "ok")
        self.assertEqual(r.json()["amounts"][0]["value"], 1200)

    def test_nothing_sent(self):
        self.assertEqual(self.client.post("/process", json={}).json(),
                         {"status": "no_amounts_found", "reason": "no input provided"})
        self.assertEqual(self.client.post("/process", content=b"garbage").json()["status"], "no_amounts_found")

    def test_step_endpoints(self):
        body = {"text": "Total: INR 1200 | Paid: 1000 | Due: 200 | Discount: 10%"}
        self.assertEqual(self.client.post("/step1/extract", json=body).json()["raw_tokens"], ["1200", "1000", "200", "10%"])
        self.assertEqual(self.client.post("/step2/normalize", json=body).json()["normalized_amounts"], [1200, 1000, 200])


if __name__ == "__main__":
    unittest.main()
