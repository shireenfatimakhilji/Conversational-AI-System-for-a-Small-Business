"""Weather update tool for delivery assessment."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

import aiohttp


class WeatherTool:
    """Check weather conditions and assess delivery impact."""

    def __init__(self, api_key: str | None = None):
        """Initialize weather tool with optional OpenWeatherMap API key."""
        self.api_key = api_key or "demo"  # Use demo mode if no key provided
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    @staticmethod
    def schema() -> Dict[str, Any]:
        """Return JSON schema for weather tool."""
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["check_weather", "assess_delivery"],
                },
                "location": {
                    "type": "string",
                    "description": "City name or delivery address (e.g., 'New York', 'London')"
                },
                "delivery_date": {
                    "type": "string",
                    "description": "Expected delivery date (format: YYYY-MM-DD)"
                },
            },
            "required": ["action", "location"],
            "additionalProperties": False,
        }

    async def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute weather tool with given arguments."""
        action = args.get("action", "").lower()
        location = args.get("location", "").strip()
        delivery_date = args.get("delivery_date", "").strip()

        if not location:
            raise ValueError("Location is required for weather check.")

        if action == "check_weather":
            weather = await self._check_weather(location)
            return {"action": action, "weather": weather}

        if action == "assess_delivery":
            assessment = await self._assess_delivery(location, delivery_date)
            return {"action": action, "assessment": assessment}

        raise ValueError(f"Unknown action: {action}. Allowed: check_weather, assess_delivery")

    async def _check_weather(self, location: str) -> Dict[str, Any]:
        """Check current weather for a location."""
        if self.api_key == "demo":
            return self._get_demo_weather(location)

        try:
            async with aiohttp.ClientSession() as session:
                params = {"q": location, "appid": self.api_key, "units": "metric"}
                async with session.get(self.base_url, params=params) as response:
                    if response.status != 200:
                        raise ValueError(f"Weather API returned status {response.status}")
                    data = await response.json()
                    return self._parse_weather_data(data)
        except asyncio.TimeoutError as exc:
            raise TimeoutError("Weather API request timed out") from exc

    async def _assess_delivery(self, location: str, delivery_date: str) -> Dict[str, Any]:
        """Assess if weather will impact delivery."""
        weather = await self._check_weather(location)
        condition = str(weather.get("condition", "")).lower()
        risk_level = "low"
        delivery_impact = ""

        severe_conditions = ["thunderstorm", "tornado", "heavy rain", "blizzard", "heavy snow", "hail"]
        moderate_conditions = ["rain", "snow", "drizzle", "sleet", "mist"]

        for severe in severe_conditions:
            if severe in condition:
                risk_level = "high"
                delivery_impact = (
                    f"High risk: {condition.title()} may cause significant delivery delays. "
                    "Expect 1-2 day delay."
                )
                break

        if risk_level == "low":
            for moderate in moderate_conditions:
                if moderate in condition:
                    risk_level = "medium"
                    delivery_impact = (
                        f"Medium risk: {condition.title()} may cause minor delivery delays. "
                        "Expect possible 6-12 hour delay."
                    )
                    break

        if risk_level == "low":
            delivery_impact = f"Low risk: {condition.title()} - Delivery on time as scheduled."

        return {
            "location": location,
            "weather_condition": condition,
            "temperature": weather.get("temperature"),
            "humidity": weather.get("humidity"),
            "wind_speed": weather.get("wind_speed"),
            "delivery_date": delivery_date or "Not specified",
            "risk_level": risk_level,
            "delivery_impact": delivery_impact,
        }

    def _parse_weather_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse OpenWeatherMap API response."""
        main_data = data.get("main", {})
        weather_list = data.get("weather", [{}])
        wind_data = data.get("wind", {})

        return {
            "location": data.get("name", "Unknown"),
            "country": data.get("sys", {}).get("country", ""),
            "condition": weather_list[0].get("main", "Unknown"),
            "description": weather_list[0].get("description", ""),
            "temperature": main_data.get("temp", None),
            "feels_like": main_data.get("feels_like", None),
            "humidity": main_data.get("humidity", None),
            "pressure": main_data.get("pressure", None),
            "wind_speed": wind_data.get("speed", None),
            "wind_deg": wind_data.get("deg", None),
            "clouds": data.get("clouds", {}).get("all", None),
            "visibility": data.get("visibility", None),
        }

    def _get_demo_weather(self, location: str) -> Dict[str, Any]:
        """Return mock weather data for demo/testing."""
        demo_data = {
            "new york": {
                "condition": "Rainy",
                "temperature": 15,
                "humidity": 75,
                "wind_speed": 12,
            },
            "london": {
                "condition": "Cloudy",
                "temperature": 12,
                "humidity": 70,
                "wind_speed": 8,
            },
            "delhi": {
                "condition": "Clear",
                "temperature": 32,
                "humidity": 45,
                "wind_speed": 5,
            },
            "karachi": {
                "condition": "Partly Cloudy",
                "temperature": 28,
                "humidity": 60,
                "wind_speed": 10,
            },
            "thunderstorm": {
                "condition": "Thunderstorm",
                "temperature": 18,
                "humidity": 85,
                "wind_speed": 25,
            },
            "snow": {
                "condition": "Heavy Snow",
                "temperature": -5,
                "humidity": 90,
                "wind_speed": 30,
            },
        }

        location_lower = location.lower().strip()
        weather = demo_data.get(location_lower, {
            "condition": "Partly Cloudy",
            "temperature": 22,
            "humidity": 65,
            "wind_speed": 8,
        })

        return {
            "location": location,
            "condition": weather["condition"],
            "temperature": weather["temperature"],
            "humidity": weather["humidity"],
            "wind_speed": weather["wind_speed"],
            "description": f"{weather['condition']} weather in {location}",
            "note": "Demo data - provide API key for real weather data",
        }
