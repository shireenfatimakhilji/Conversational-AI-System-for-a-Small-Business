"""
test_calculator_unit.py
=======================
Component-level (unit) tests for CalculatorTool.
Directly calls the tool — no LLM involved.

Tests cover:
  Layer 1 — Correct arithmetic results
  Layer 2 — Precision rounding
  Layer 3 — Allowed math functions (abs, sqrt, ceil, floor, round, min, max, sum)
  Layer 4 — Validation / error handling

Run:
    cd nlp_3
    python -m pytest evals/test_calculator_unit.py -v
"""

from __future__ import annotations

import asyncio
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.calculator import CalculatorTool


# def run(coro):
#     return asyncio.get_event_loop().run_until_complete(coro)
def run(coro):
    return asyncio.run(coro)


CALC = CalculatorTool()


# ══════════════════════════════════════════════════════════════════════════════
# Layer 1 — Basic arithmetic
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculatorBasicArithmetic(unittest.TestCase):

    def _calc(self, expr):
        return run(CALC.run({"expression": expr}))["result"]

    def test_addition(self):
        self.assertEqual(self._calc("2 + 3"), 5)

    def test_subtraction(self):
        self.assertEqual(self._calc("10 - 4"), 6)

    def test_multiplication(self):
        self.assertEqual(self._calc("6 * 7"), 42)

    def test_division(self):
        self.assertAlmostEqual(self._calc("10 / 4"), 2.5)

    def test_floor_division(self):
        self.assertEqual(self._calc("10 // 3"), 3)

    def test_modulo(self):
        self.assertEqual(self._calc("10 % 3"), 1)

    def test_power(self):
        self.assertEqual(self._calc("2 ** 8"), 256)

    def test_nested_parentheses(self):
        self.assertEqual(self._calc("(2 + 3) * (4 - 1)"), 15)

    def test_unary_negation(self):
        self.assertEqual(self._calc("-5 + 10"), 5)

    def test_unary_positive(self):
        self.assertEqual(self._calc("+5"), 5)

    def test_large_numbers(self):
        self.assertEqual(self._calc("1000000 * 1000000"), 1_000_000_000_000)

    def test_float_result(self):
        result = self._calc("1 / 3")
        self.assertAlmostEqual(result, 0.3333, places=4)

    def test_integer_result_type(self):
        result = self._calc("3 + 4")
        self.assertIsInstance(result, int)

    def test_crochetzies_pricing_calc(self):
        """Simulate: 3 medium items at Rs 1000 each."""
        result = self._calc("3 * 1000")
        self.assertEqual(result, 3000)

    def test_multi_item_total(self):
        """Simulate: 2 small (Rs 800) + 1 large (Rs 2000)."""
        result = self._calc("2 * 800 + 1 * 2000")
        self.assertEqual(result, 3600)


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2 — Precision rounding
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculatorPrecision(unittest.TestCase):

    def test_precision_2_decimal(self):
        result = run(CALC.run({"expression": "1 / 3", "precision": 2}))["result"]
        self.assertEqual(result, 0.33)

    def test_precision_0_rounds_to_int(self):
        result = run(CALC.run({"expression": "2.7", "precision": 0}))["result"]
        self.assertEqual(result, 3.0)

    def test_precision_5(self):
        result = run(CALC.run({"expression": "1 / 7", "precision": 5}))["result"]
        self.assertAlmostEqual(result, 0.14286, places=5)

    def test_precision_on_integer_no_effect(self):
        """Precision only applies to floats; integer stays integer."""
        result = run(CALC.run({"expression": "6 * 7", "precision": 3}))
        self.assertEqual(result["result"], 42)

    def test_precision_max_12(self):
        result = run(CALC.run({"expression": "1 / 3", "precision": 12}))["result"]
        self.assertIsNotNone(result)

    def test_precision_too_high_raises(self):
        with self.assertRaises((ValueError, Exception)):
            run(CALC.run({"expression": "1+1", "precision": 99}))

    def test_precision_negative_raises(self):
        with self.assertRaises((ValueError, Exception)):
            run(CALC.run({"expression": "1+1", "precision": -1}))


# ══════════════════════════════════════════════════════════════════════════════
# Layer 3 — Allowed math functions
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculatorFunctions(unittest.TestCase):

    def _calc(self, expr):
        return run(CALC.run({"expression": expr}))["result"]

    def test_abs_positive(self):
        self.assertEqual(self._calc("abs(5)"), 5)

    def test_abs_negative(self):
        self.assertEqual(self._calc("abs(-7)"), 7)

    def test_round_function(self):
        self.assertEqual(self._calc("round(3.7)"), 4)

    def test_min_function(self):
        self.assertEqual(self._calc("min(3, 7, 2)"), 2)

    def test_max_function(self):
        self.assertEqual(self._calc("max(3, 7, 2)"), 7)

    def test_sum_list(self):
        self.assertEqual(self._calc("sum([1, 2, 3, 4, 5])"), 15)

    def test_sqrt(self):
        self.assertAlmostEqual(self._calc("sqrt(9)"), 3.0)

    def test_sqrt_non_perfect(self):
        self.assertAlmostEqual(self._calc("sqrt(2)"), math.sqrt(2), places=6)

    def test_ceil(self):
        self.assertEqual(self._calc("ceil(3.1)"), 4)

    def test_floor(self):
        self.assertEqual(self._calc("floor(3.9)"), 3)

    def test_nested_functions(self):
        # abs(min(-3, 5)) → abs(-3) → 3
        self.assertEqual(self._calc("abs(min(-3, 5))"), 3)


# ══════════════════════════════════════════════════════════════════════════════
# Layer 4 — Validation and error handling
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculatorValidation(unittest.TestCase):

    def test_empty_expression_raises(self):
        with self.assertRaises(ValueError):
            run(CALC.run({"expression": ""}))

    def test_missing_expression_raises(self):
        with self.assertRaises(ValueError):
            run(CALC.run({}))

    def test_string_literal_raises(self):
        """String constants are not allowed."""
        with self.assertRaises((ValueError, Exception)):
            run(CALC.run({"expression": "'hello'"}))

    def test_exec_attempt_raises(self):
        """Potentially dangerous code must be blocked."""
        with self.assertRaises((ValueError, Exception)):
            run(CALC.run({"expression": "__import__('os').system('echo bad')"}))

    def test_unsupported_function_raises(self):
        with self.assertRaises((ValueError, Exception)):
            run(CALC.run({"expression": "open('etc/passwd')"}))

    def test_division_by_zero_raises(self):
        with self.assertRaises((ZeroDivisionError, Exception)):
            run(CALC.run({"expression": "1 / 0"}))

    def test_response_contains_expression(self):
        result = run(CALC.run({"expression": "2 + 2"}))
        self.assertEqual(result["expression"], "2 + 2")
        self.assertEqual(result["result"], 4)

    def test_schema_has_required_expression(self):
        schema = CalculatorTool.schema()
        self.assertIn("expression", schema.get("required", []))


# ══════════════════════════════════════════════════════════════════════════════
# Standalone runner
# ══════════════════════════════════════════════════════════════════════════════

def run_calculator_unit_tests() -> dict:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestCalculatorBasicArithmetic,
        TestCalculatorPrecision,
        TestCalculatorFunctions,
        TestCalculatorValidation,
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
    summary = run_calculator_unit_tests()
    print(f"\n{'='*60}")
    print(f"CALCULATOR UNIT TEST SUMMARY")
    print(f"  Total  : {summary['total']}")
    print(f"  Passed : {summary['total'] - summary['failures'] - summary['errors']}")
    print(f"  Failed : {summary['failures']}")
    print(f"  Errors : {summary['errors']}")
    print(f"  Result : {'✅ ALL PASSED' if summary['passed'] else '❌ SOME FAILED'}")
    print(f"{'='*60}")
