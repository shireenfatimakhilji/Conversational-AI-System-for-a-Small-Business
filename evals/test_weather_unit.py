"""
test_weather_unit.py
====================
Component-level (unit) tests for WeatherTool.
Directly calls the tool — no LLM involved. Uses demo mode (no real API key).

Tests cover:
  Layer 1 — check_weather action (demo data)
  Layer 2 — assess_delivery action (risk level logic)
  Layer 3 — Known cities and defaults
  Layer 4 — Validation / error handling

Run:
    cd nlp_3
    python -m pytest evals/test_weather_unit.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.weather import WeatherTool


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# Demo-mode tool (no real API key needed)
WEATHER = WeatherTool(api_key="demo")


# ══════════════════════════════════════════════════════════════════════════════
# Layer 1 — check_weather action
# ══════════════════════════════════════════════════════════════════════════════

class TestWeatherCheckWeather(unittest.TestCase):

    def _check(self, location: str) -> dict:
        return run(WEATHER.run({"action": "check_weather", "location": location}))

    def test_action_in_response(self):
        result = self._check("Karachi")
        self.assertEqual(result["action"], "check_weather")

    def test_weather_dict_present(self):
        result = self._check("Karachi")
        self.assertIn("weather", result)
        self.assertIsInstance(result["weather"], dict)

    def test_karachi_weather_condition(self):
        weather = self._check("Karachi")["weather"]
        self.assertIn("condition", weather)
        self.assertIsInstance(weather["condition"], str)

    def test_karachi_temperature_numeric(self):
        weather = self._check("Karachi")["weather"]
        self.assertIsInstance(weather["temperature"], (int, float))

    def test_new_york_condition_is_rainy(self):
        """Demo data hard-codes New York as 'Rainy'."""
        weather = self._check("New York")["weather"]
        self.assertEqual(weather["condition"].lower(), "rainy")

    def test_london_condition_is_cloudy(self):
        weather = self._check("London")["weather"]
        self.assertEqual(weather["condition"].lower(), "cloudy")

    def test_unknown_city_returns_default(self):
        """Unknown city should return default demo data, not raise."""
        result = self._check("Timbuktu")
        self.assertIn("weather", result)
        self.assertIsNotNone(result["weather"]["condition"])

    def test_response_has_location_field(self):
        weather = self._check("Delhi")["weather"]
        self.assertIn("location", weather)

    def test_weather_has_humidity(self):
        weather = self._check("Karachi")["weather"]
        self.assertIn("humidity", weather)

    def test_weather_has_wind_speed(self):
        weather = self._check("Karachi")["weather"]
        self.assertIn("wind_speed", weather)

    def test_demo_note_present(self):
        weather = self._check("Karachi")["weather"]
        self.assertIn("note", weather)
        self.assertIn("demo", weather["note"].lower())


# ══════════════════════════════════════════════════════════════════════════════
# Layer 2 — assess_delivery action & risk levels
# ══════════════════════════════════════════════════════════════════════════════

class TestWeatherAssessDelivery(unittest.TestCase):

    def _assess(self, location: str, delivery_date: str = "2026-05-10") -> dict:
        return run(WEATHER.run({
            "action": "assess_delivery",
            "location": location,
            "delivery_date": delivery_date,
        }))

    def test_action_in_response(self):
        result = self._assess("Karachi")
        self.assertEqual(result["action"], "assess_delivery")

    def test_assessment_dict_present(self):
        result = self._assess("Karachi")
        self.assertIn("assessment", result)

    def test_assessment_has_risk_level(self):
        assessment = self._assess("Karachi")["assessment"]
        self.assertIn("risk_level", assessment)
        self.assertIn(assessment["risk_level"], ("low", "medium", "high"))

    def test_assessment_has_delivery_impact(self):
        assessment = self._assess("Karachi")["assessment"]
        self.assertIn("delivery_impact", assessment)
        self.assertIsInstance(assessment["delivery_impact"], str)

    def test_clear_weather_low_risk(self):
        """Delhi is 'Clear' in demo → low risk."""
        assessment = self._assess("Delhi")["assessment"]
        self.assertEqual(assessment["risk_level"], "low")

    def test_thunderstorm_high_risk(self):
        """The demo city named 'thunderstorm' returns Thunderstorm condition → high risk."""
        assessment = self._assess("thunderstorm")["assessment"]
        self.assertEqual(assessment["risk_level"], "high")

    def test_snow_high_risk(self):
        """The demo city named 'snow' returns Heavy Snow → high risk."""
        assessment = self._assess("snow")["assessment"]
        self.assertEqual(assessment["risk_level"], "high")

    def test_rainy_medium_risk(self):
        """New York is Rainy → medium risk (rain is a moderate condition)."""
        assessment = self._assess("New York")["assessment"]
        self.assertEqual(assessment["risk_level"], "medium")

    def test_delivery_date_in_response(self):
        assessment = self._assess("Karachi", "2026-06-01")["assessment"]
        self.assertEqual(assessment["delivery_date"], "2026-06-01")

    def test_temperature_in_response(self):
        assessment = self._assess("Karachi")["assessment"]
        self.assertIn("temperature", assessment)

    def test_humidity_in_response(self):
        assessment = self._assess("Karachi")["assessment"]
        self.assertIn("humidity", assessment)

    def test_missing_delivery_date_defaults(self):
        """delivery_date is optional; should still return assessment."""
        result = run(WEATHER.run({"action": "assess_delivery", "location": "Karachi"}))
        self.assertIn("assessment", result)
        self.assertEqual(result["assessment"]["delivery_date"], "Not specified")


# ══════════════════════════════════════════════════════════════════════════════
# Layer 3 — Known cities
# ══════════════════════════════════════════════════════════════════════════════

class TestWeatherKnownCities(unittest.TestCase):

    DEMO_CITIES = ["new york", "london", "delhi", "karachi", "thunderstorm", "snow"]

    def test_all_demo_cities_return_data(self):
        for city in self.DEMO_CITIES:
            with self.subTest(city=city):
                result = run(WEATHER.run({"action": "check_weather", "location": city}))
                self.assertIn("weather", result)
                weather = result["weather"]
                self.assertIsNotNone(weather.get("condition"))


# ══════════════════════════════════════════════════════════════════════════════
# Layer 4 — Validation / error handling
# ══════════════════════════════════════════════════════════════════════════════

class TestWeatherValidation(unittest.TestCase):

    def test_missing_location_raises(self):
        with self.assertRaises(ValueError):
            run(WEATHER.run({"action": "check_weather", "location": ""}))

    def test_missing_location_key_raises(self):
        with self.assertRaises((ValueError, KeyError, Exception)):
            run(WEATHER.run({"action": "check_weather"}))

    def test_unknown_action_raises(self):
        with self.assertRaises((ValueError, Exception)):
            run(WEATHER.run({"action": "teleport", "location": "Karachi"}))

    def test_missing_action_defaults_or_raises(self):
        """No action provided — should raise ValueError."""
        with self.assertRaises((ValueError, Exception)):
            run(WEATHER.run({"location": "Karachi"}))

    def test_schema_has_required_fields(self):
        schema = WeatherTool.schema()
        required = schema.get("required", [])
        self.assertIn("action", required)
        self.assertIn("location", required)

    def test_schema_action_enum(self):
        schema = WeatherTool.schema()
        allowed = schema["properties"]["action"]["enum"]
        self.assertIn("check_weather", allowed)
        self.assertIn("assess_delivery", allowed)

    def test_weather_api_timeout_handled(self):
        """
        Simulate an API timeout by patching aiohttp.ClientSession.
        The tool should propagate TimeoutError or return an error.
        """
        import aiohttp
        real_key_tool = WeatherTool(api_key="fake_key_to_trigger_real_path")

        async def mock_get(*args, **kwargs):
            raise asyncio.TimeoutError()

        with patch.object(aiohttp.ClientSession, "get", side_effect=mock_get):
            with self.assertRaises((TimeoutError, asyncio.TimeoutError, Exception)):
                run(real_key_tool.run({"action": "check_weather", "location": "London"}))


# ══════════════════════════════════════════════════════════════════════════════
# Standalone runner
# ══════════════════════════════════════════════════════════════════════════════

def run_weather_unit_tests() -> dict:
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestWeatherCheckWeather,
        TestWeatherAssessDelivery,
        TestWeatherKnownCities,
        TestWeatherValidation,
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
    summary = run_weather_unit_tests()
    print(f"\n{'='*60}")
    print(f"WEATHER UNIT TEST SUMMARY")
    print(f"  Total  : {summary['total']}")
    print(f"  Passed : {summary['total'] - summary['failures'] - summary['errors']}")
    print(f"  Failed : {summary['failures']}")
    print(f"  Errors : {summary['errors']}")
    print(f"  Result : {'✅ ALL PASSED' if summary['passed'] else '❌ SOME FAILED'}")
    print(f"{'='*60}")
