"""Direct function-call checks for the tool implementations."""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

from convo_manager import ConversationManager
from orchestrator import execute_tool
from tools.calculator import CalculatorTool
from tools.calendar import CalendarTool  # <-- added
from tools.crm import CRMTool
from tools.weather import WeatherTool


def test_crm_tool() -> None:
    with TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "crm.sqlite3"
        crm = CRMTool(db_path=db_path)

        created = asyncio.run(
            crm.run(
                {
                    "action": "upsert",
                    "user_id": "cust-001",
                    "name": "Ayesha Khan",
                    "email": "ayesha@example.com",
                    "phone": "0300-1234567",
                    "preferences": {"contact_method": "whatsapp"},
                }
            )
        )
        assert created["user"]["name"] == "Ayesha Khan"

        updated = asyncio.run(
            crm.run(
                {
                    "action": "update",
                    "user_id": "cust-001",
                    "address": "House 12, Street 4, Rawalpindi",
                    "metadata": {"tier": "vip"},
                }
            )
        )
        assert updated["user"]["address"] == "House 12, Street 4, Rawalpindi"
        assert updated["user"]["metadata"]["tier"] == "vip"

        fetched = asyncio.run(crm.run({"action": "get", "user_id": "cust-001"}))
        assert fetched["user"]["email"] == "ayesha@example.com"


def test_calculator_tool() -> None:
    calculator = CalculatorTool()
    result = asyncio.run(calculator.run({"expression": "(12 + 8) / 5", "precision": 2}))
    assert result["result"] == 4.0

    result_two = asyncio.run(calculator.run({"expression": "sqrt(81) + max(2, 5)"}))
    assert result_two["result"] == 14.0


def test_weather_tool() -> None:
    weather = WeatherTool(api_key="demo")

    check_result = asyncio.run(weather.run({"action": "check_weather", "location": "London"}))
    assert check_result["action"] == "check_weather"
    assert check_result["weather"]["location"] == "London"

    assess_result = asyncio.run(
        weather.run(
            {
                "action": "assess_delivery",
                "location": "Karachi",
                "delivery_date": "2026-04-25",
            }
        )
    )
    assert assess_result["action"] == "assess_delivery"
    assert "delivery_impact" in assess_result["assessment"]
    assert "risk_level" in assess_result["assessment"]


def test_calendar_tool() -> None:  # <-- added
    calendar = CalendarTool()

    # Standard order within threshold — no note expected.
    result = asyncio.run(calendar.run({"order_date": "2026-04-20", "processing_days": 5}))
    assert result["order_date"] == "2026-04-20"
    assert result["estimated_delivery_date"] == "2026-04-25"
    assert result["note"] is None

    # Long order exceeding threshold — note must be present.
    result_long = asyncio.run(calendar.run({"order_date": "2026-04-20", "processing_days": 10}))
    assert result_long["estimated_delivery_date"] == "2026-04-30"
    assert result_long["note"] is not None


def test_orchestrator_smoke() -> None:
    crm_response = asyncio.run(
        execute_tool(
            "crm",
            {
                "action": "upsert",
                "user_id": "cust-002",
                "name": "Ayesha Khan",
                "notes": "Prefers small orders.",
            },
        )
    )
    assert crm_response["ok"] is True
    assert crm_response["result"]["user"]["name"] == "Ayesha Khan"

    calc_response = asyncio.run(execute_tool("calculator", {"expression": "10 * 3 + 2"}))
    assert calc_response["ok"] is True
    assert calc_response["result"]["result"] == 32

    weather_response = asyncio.run(
        execute_tool("weather", {"action": "check_weather", "location": "Delhi"})
    )
    assert weather_response["ok"] is True
    assert weather_response["result"]["weather"]["location"] == "Delhi"

    calendar_response = asyncio.run(  # <-- added
        execute_tool("calendar", {"order_date": "2026-04-20", "processing_days": 3})
    )
    assert calendar_response["ok"] is True
    assert calendar_response["result"]["estimated_delivery_date"] == "2026-04-23"


def test_conversation_weather() -> None:
    manager = ConversationManager()

    weather_response = manager.get_response("What is the weather in London?")
    assert len(weather_response) > 0

    follow_up_manager = ConversationManager()
    follow_up_manager.awaiting_weather_check = True
    follow_up_response = follow_up_manager.get_response("Karachi")
    assert "weather" in follow_up_response.lower() or "delivery" in follow_up_response.lower()


def run_all_tests() -> None:
    test_crm_tool()
    test_calculator_tool()
    test_weather_tool()
    test_calendar_tool()  # <-- added
    test_orchestrator_smoke()
    test_conversation_weather()
    print("All tool tests passed.")


if __name__ == "__main__":
    run_all_tests()