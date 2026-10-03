"""AI review tests. The Groq call is replaced by a fake, so no internet or API key is needed."""
import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import vision  # noqa: E402
from pipeline.runner import run_pipeline  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 100
MISREAD = "Total: 1200 | Paid: 1000 | Due: 280"      # the bill actually says Due: 200


def voter(true_values, calls):
    """Fake AI: always picks the option whose value is in true_values; records every question."""
    def fake(image, mime, prompt, temperature, max_tokens=2048):
        calls.append((image, prompt))
        options = dict(re.findall(r"^([AB])\) (\S+)$", prompt, re.M))
        for letter, value in options.items():
            if value in true_values:
                return letter
        return "C"
    return fake


class Review(unittest.TestCase):
    def test_fixes_one_misread_digit_when_ai_agrees_three_times(self):
        calls = []
        with mock.patch.object(vision, "_call_groq", side_effect=voter({"200", "1200"}, calls)):
            amounts = run_pipeline(MISREAD)["amounts"]
        self.assertEqual({a["type"]: a["value"] for a in amounts}, {"total_bill": 1200, "paid": 1000, "due": 200})
        self.assertGreaterEqual(len(calls), 6)          # 3 votes per candidate

    def test_edit_lowers_confidence(self):
        clean = run_pipeline("Total: 1200 | Paid: 1000 | Due: 200", upto=2)["normalization_confidence"]
        with mock.patch.object(vision, "_call_groq", side_effect=voter({"200", "1200"}, [])):
            edited = run_pipeline(MISREAD, upto=2)["normalization_confidence"]
        self.assertLess(edited, clean)

    def test_ai_saying_cannot_tell_changes_nothing(self):
        with mock.patch.object(vision, "_call_groq", return_value="C"):
            amounts = run_pipeline(MISREAD)["amounts"]
        self.assertEqual([a["value"] for a in amounts], [1200, 1000, 280])

    def test_one_dissenting_vote_changes_nothing(self):
        answers = iter(["A", "A", "B", "A", "A", "B"] * 3)     # the candidate is not picked every time
        with mock.patch.object(vision, "_call_groq", side_effect=lambda *a, **k: next(answers)):
            amounts = run_pipeline(MISREAD)["amounts"]
        self.assertEqual([a["value"] for a in amounts], [1200, 1000, 280])

    def test_no_ai_call_when_the_bill_balances(self):
        with mock.patch.object(vision, "_call_groq") as fake:
            run_pipeline("Total: 1200 | Paid: 1000 | Due: 200")
        fake.assert_not_called()

    def test_no_ai_call_when_no_single_digit_fix_exists(self):
        with mock.patch.object(vision, "_call_groq") as fake:
            amounts = run_pipeline("Total: 1200 | Paid: 1000 | Due: 300")["amounts"]
        fake.assert_not_called()
        self.assertEqual(amounts[2]["value"], 300)

    def test_ai_failure_changes_nothing(self):
        with mock.patch.object(vision, "_call_groq", side_effect=vision.VisionError("down")):
            amounts = run_pipeline(MISREAD)["amounts"]
        self.assertEqual(amounts[2]["value"], 280)

    def test_image_is_shown_to_the_ai_during_review(self):
        calls = []
        reader = voter({"200", "1200"}, calls)

        def fake(image, mime, prompt, temperature, max_tokens=2048):
            if "Transcribe" in prompt or "Read this document" in prompt:
                return MISREAD
            return reader(image, mime, prompt, temperature, max_tokens)

        with mock.patch.object(vision, "_call_groq", side_effect=fake):
            result = run_pipeline(image_bytes=PNG)
        self.assertEqual(result["amounts"][2]["value"], 200)
        self.assertTrue(calls and all(image == PNG for image, _ in calls))


if __name__ == "__main__":
    unittest.main()