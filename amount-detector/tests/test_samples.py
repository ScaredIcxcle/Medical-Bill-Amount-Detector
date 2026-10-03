"""Run with:  python -m unittest discover -s tests -v   (from the amount-detector folder)"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.runner import run_pipeline  # noqa: E402

TEXT_SAMPLE = "Total: INR 1200 | Paid: 1000 | Due: 200 | Discount: 10%"
OCR_SAMPLE = "T0tal: Rs l200 | Pald: 1000 | Due: 200"
NO_AMOUNTS = {"status": "no_amounts_found"}


def guardrail_status(result):
    return result.get("status") == "no_amounts_found"


class SpecSamples(unittest.TestCase):
    def test_text_sample_step1(self):
        r = run_pipeline(TEXT_SAMPLE, upto=1)
        self.assertEqual(r["raw_tokens"], ["1200", "1000", "200", "10%"])
        self.assertEqual(r["currency_hint"], "INR")

    def test_text_sample_step2(self):
        self.assertEqual(run_pipeline(TEXT_SAMPLE, upto=2)["normalized_amounts"], [1200, 1000, 200])

    def test_text_sample_step3(self):
        r = run_pipeline(TEXT_SAMPLE, upto=3)
        self.assertEqual(
            r["amounts"],
            [{"type": "total_bill", "value": 1200}, {"type": "paid", "value": 1000}, {"type": "due", "value": 200}],
        )

    def test_text_sample_final(self):
        r = run_pipeline(TEXT_SAMPLE)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["currency"], "INR")
        self.assertEqual(
            [a["source"] for a in r["amounts"]],
            ["text: 'Total: INR 1200'", "text: 'Paid: 1000'", "text: 'Due: 200'"],
        )

    def test_ocr_sample(self):
        self.assertEqual(run_pipeline(OCR_SAMPLE, upto=1)["raw_tokens"], ["l200", "1000", "200"])
        self.assertEqual(run_pipeline(OCR_SAMPLE, upto=2)["normalized_amounts"], [1200, 1000, 200])
        final = run_pipeline(OCR_SAMPLE)
        self.assertEqual([(a["type"], a["value"]) for a in final["amounts"]],
                         [("total_bill", 1200), ("paid", 1000), ("due", 200)])
        self.assertEqual(final["amounts"][0]["source"], "text: 'T0tal: Rs l200'")

    def test_letter_o_inside_number(self):
        self.assertEqual(run_pipeline("Total: 12o0 | Paid: 1000 | Due: 200", upto=1)["raw_tokens"][0], "12o0")
        self.assertEqual(run_pipeline("Total: 12o0 | Paid: 1000 | Due: 200", upto=2)["normalized_amounts"][0], 1200)


class Formats(unittest.TestCase):
    def test_no_pipes(self):
        r = run_pipeline("Total: 1200 Paid: 1000 Due: 200")
        self.assertEqual([a["value"] for a in r["amounts"]], [1200, 1000, 200])

    def test_newlines_and_tabular(self):
        r = run_pipeline("Total   1200\nPaid   1000\nBalance   200")
        self.assertEqual([(a["type"], a["value"]) for a in r["amounts"]],
                         [("total_bill", 1200), ("paid", 1000), ("due", 200)])

    def test_indian_formats(self):
        r = run_pipeline("Total: Rs. 1,20,000/- | Paid: ₹1,00,000 | Due: 20,000.00")
        self.assertEqual([a["value"] for a in r["amounts"]], [120000, 100000, 20000])

    def test_decimals(self):
        r = run_pipeline("Total: 1200.50 | Paid: 1000.25 | Due: 200.25")
        self.assertEqual([a["value"] for a in r["amounts"]], [1200.5, 1000.25, 200.25])


class Tolerance(unittest.TestCase):
    def test_garbled_currency_prefix(self):
        r = run_pipeline("Total: 1NR12o0 | Paid: 1000 | Due: 200")
        self.assertEqual(run_pipeline("Total: 1NR12o0 | Paid: 1000 | Due: 200", upto=1)["raw_tokens"][0], "12o0")
        self.assertEqual([a["value"] for a in r["amounts"]], [1200, 1000, 200])

    def test_two_wrong_characters_in_a_label(self):
        r = run_pipeline("Tptol: 1200 | Pxid: 1000 | Due: 200")
        self.assertEqual([(a["type"], a["value"]) for a in r["amounts"]],
                         [("total_bill", 1200), ("paid", 1000), ("due", 200)])

    def test_unrelated_words_still_do_not_match(self):
        self.assertEqual(run_pipeline("Dose: 500")["status"], "no_amounts_found")
        self.assertEqual(run_pipeline("Consultation: 500")["status"], "no_amounts_found")


class Guardrails(unittest.TestCase):
    def test_empty(self):
        self.assertTrue(guardrail_status(run_pipeline("")))
        self.assertTrue(guardrail_status(run_pipeline("   \n ")))

    def test_no_numbers(self):
        r = run_pipeline("Thank you for visiting the hospital")
        self.assertEqual(r["status"], "no_amounts_found")

    def test_identifier_numbers_are_not_amounts(self):
        r = run_pipeline("Phone: 9876543210 | Invoice No: 4521 | Date: 12 05 2024")
        self.assertEqual(r["status"], "no_amounts_found")

    def test_unlabeled_numbers(self):
        r = run_pipeline("Consultation: 500")
        self.assertEqual(r, {"status": "no_amounts_found", "reason": "no labeled amounts found"})

    def test_guardrail_shape_only_has_status_and_reason(self):
        r = run_pipeline("")
        self.assertEqual(set(r), {"status", "reason"})

    def test_mismatch_does_not_exit_but_lowers_confidence(self):
        good = run_pipeline("Total: 1200 | Paid: 1000 | Due: 200", upto=2)
        bad = run_pipeline("Total: 1200 | Paid: 1000 | Due: 300", upto=2)
        self.assertEqual(bad["normalized_amounts"], [1200, 1000, 300])
        self.assertLess(bad["normalization_confidence"], good["normalization_confidence"])

    def test_subtotal_is_not_total(self):
        r = run_pipeline("Sub Total: 1000 | Total: 1180")
        self.assertEqual([(a["type"], a["value"]) for a in r["amounts"]], [("total_bill", 1180)])


if __name__ == "__main__":
    unittest.main()
