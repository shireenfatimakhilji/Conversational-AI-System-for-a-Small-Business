"""
test_calendar_unit.py
=====================
Component-level (unit) tests for CalendarTool.
Directly calls the tool — no LLM involved.

Tests cover:
  Layer 1 — Correct delivery date calculations
  Layer 2 — Long-order note (> 7 processing days)
  Layer 3 — Date format validation
  Layer 4 — Edge cases (leap years, year-end crossover)

Run:
    cd nlp_3
    python -m pytest evals/test_calendar_unit.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.calendar import CalendarTool


# def run(coro):
#     return asyncio.get_event_loop().run_until_complete(coro)
def run(coro):
    return asyncio.run(coro)


CAL = CalendarTool()


# ══════════════════════════════════════════════════════════════════════════════
# Layer 1 — Delivery date calculation correctness
# ══════════════════════════════════════════════════════════════════════════════

class TestCalendarDeliveryDate(unittest.TestCase):

    def _estimate(self, order_date: str, days: int) -> dict:
        return run(CAL.run({"order_date": order_date, "processing_days": days}))

    def test_standard_7_day_delivery(self):
        result = self._estimate("2026-04-20", 7)
        self.assertEqual(result["estimated_delivery_date"], "2026-04-27")

    def test_1_day_processing(self):
        result = self._estimate("2026-01-01", 1)
        self.assertEqual(result["estimated_delivery_date"], "2026-01-02")

    def test_30_day_processing(self):
        result = self._estimate("2026-01-01", 30)
        self.assertEqual(result["estimated_delivery_date"], "2026-01-31")

    def test_result_contains_order_date(self):
        result = self._estimate("2026-05-10", 7)
        self.assertEqual(result["order_date"], "2026-05-10")

    def test_result_contains_processing_days(self):
        result = self._estimate("2026-05-10", 5)
        self.assertEqual(result["processing_days"], 5)

    def test_message_contains_dates(self):
        result = self._estimate("2026-06-01", 7)
        msg = result["message"]
        self.assertIn("2026-06-01", msg)
        self.assertIn("2026-06-08", msg)

    def test_result_fields_present(self):
        result = self._estimate("2026-04-01", 7)
        for field in ("order_date", "processing_days", "estimated_delivery_date", "message"):
            self.assertIn(field, result)

    def test_crochetzies_standard_order(self):
        """Simulate the standard Crochetzies 7-day processing flow."""
        order_date = "2026-04-20"
        result = self._estimate(order_date, 7)
        expected_delivery = (date(2026, 4, 20) + timedelta(days=7)).strftime("%Y-%m-%d")
        self.assertEqual(result["estimated_delivery_date"], expected_delivery)

    def test_processing_days_in_message(self):
        result = self._estimate("2026-05-01", 5)
        self.assertIn("5", result["message"])


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2 — Long-order note (> 7 processing days)
# ══════════════════════════════════════════════════════════════════════════════

class TestCalendarLongOrderNote(unittest.TestCase):

    def test_note_present_for_8_days(self):
        result = run(CAL.run({"order_date": "2026-04-20", "processing_days": 8}))
        self.assertIsNotNone(result["note"])
        self.assertIn("custom order", result["note"].lower())

    def test_note_present_for_14_days(self):
        result = run(CAL.run({"order_date": "2026-04-20", "processing_days": 14}))
        self.assertIsNotNone(result["note"])

    def test_no_note_for_7_days(self):
        result = run(CAL.run({"order_date": "2026-04-20", "processing_days": 7}))
        self.assertIsNone(result["note"])

    def test_no_note_for_1_day(self):
        result = run(CAL.run({"order_date": "2026-04-20", "processing_days": 1}))
        self.assertIsNone(result["note"])

    def test_note_in_message_for_long_order(self):
        result = run(CAL.run({"order_date": "2026-04-20", "processing_days": 10}))
        self.assertIn(result["note"], result["message"])


# ══════════════════════════════════════════════════════════════════════════════
# Layer 3 — Date format validation
# ══════════════════════════════════════════════════════════════════════════════

class TestCalendarDateValidation(unittest.TestCase):

    def test_invalid_date_format_raises(self):
        with self.assertRaises(ValueError):
            run(CAL.run({"order_date": "20-04-2026", "processing_days": 7}))

    def test_empty_date_raises(self):
        with self.assertRaises((ValueError, Exception)):
            run(CAL.run({"order_date": "", "processing_days": 7}))

    def test_missing_order_date_raises(self):
        with self.assertRaises((ValueError, KeyError, Exception)):
            run(CAL.run({"processing_days": 7}))

    def test_missing_processing_days_raises(self):
        with self.assertRaises((ValueError, KeyError, Exception)):
            run(CAL.run({"order_date": "2026-04-20"}))

    def test_zero_processing_days_raises(self):
        with self.assertRaises((ValueError, Exception)):
            run(CAL.run({"order_date": "2026-04-20", "processing_days": 0}))

    def test_negative_processing_days_raises(self):
        with self.assertRaises((ValueError, Exception)):
            run(CAL.run({"order_date": "2026-04-20", "processing_days": -3}))

    def test_nonsense_date_raises(self):
        with self.assertRaises((ValueError, Exception)):
            run(CAL.run({"order_date": "not-a-date", "processing_days": 7}))

    def test_schema_has_required_fields(self):
        schema = CalendarTool.schema()
        required = schema.get("required", [])
        self.assertIn("order_date", required)
        self.assertIn("processing_days", required)


# ══════════════════════════════════════════════════════════════════════════════
# Layer 4 — Edge cases
# ══════════════════════════════════════════════════════════════════════════════

class TestCalendarEdgeCases(unittest.TestCase):

    def test_year_end_crossover(self):
        """Order placed Dec 28 with 7 days should land in January."""
        result = run(CAL.run({"order_date": "2025-12-28", "processing_days": 7}))
        self.assertEqual(result["estimated_delivery_date"], "2026-01-04")

    def test_leap_year_feb_28(self):
        """Feb 28, 2028 (leap year) + 2 days = Feb 29."""
        result = run(CAL.run({"order_date": "2028-02-28", "processing_days": 2}))
        self.assertEqual(result["estimated_delivery_date"], "2028-03-01")

    def test_month_end_crossover(self):
        """Jan 30 + 3 days = Feb 2."""
        result = run(CAL.run({"order_date": "2026-01-30", "processing_days": 3}))
        self.assertEqual(result["estimated_delivery_date"], "2026-02-02")

    def test_large_processing_days(self):
        """365 days processing = same calendar date next year."""
        result = run(CAL.run({"order_date": "2026-01-01", "processing_days": 365}))
        self.assertEqual(result["estimated_delivery_date"], "2027-01-01")

    def test_decimal_processing_days_coerced(self):
        """String integer should be accepted and coerced."""
        result = run(CAL.run({"order_date": "2026-04-20", "processing_days": "7"}))
        self.assertEqual(result["estimated_delivery_date"], "2026-04-27")


# ══════════════════════════════════════════════════════════════════════════════
# Standalone runner
# ══════════════════════════════════════════════════════════════════════════════

def run_calendar_unit_tests() -> dict:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestCalendarDeliveryDate,
        TestCalendarLongOrderNote,
        TestCalendarDateValidation,
        TestCalendarEdgeCases,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return {
        "total": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "passed": result.wasSuccessful(),
    }


if __name__ == "__main__":
    summary = run_calendar_unit_tests()
    print(f"\n{'='*60}")
    print(f"CALENDAR UNIT TEST SUMMARY")
    print(f"  Total  : {summary['total']}")
    print(f"  Passed : {summary['total'] - summary['failures'] - summary['errors']}")
    print(f"  Failed : {summary['failures']}")
    print(f"  Errors : {summary['errors']}")
    print(f"  Result : {'✅ ALL PASSED' if summary['passed'] else '❌ SOME FAILED'}")
    print(f"{'='*60}")
