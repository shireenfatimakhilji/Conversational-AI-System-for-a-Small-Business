"""
utterance_dataset.py
====================
Test utterance dataset for Crochetzies assistant tool-call evaluation.

Each entry describes:
  - utterance       : what the user says
  - expected_tool   : which tool the LLM should invoke (None = no tool)
  - expected_args   : key fields that must appear in the tool args (subset check)
  - category        : grouping label for reporting
  - notes           : human-readable intent description

This dataset is used by test_llm_tool_invocation.py to evaluate whether
the LLM triggers the right tool with the right arguments.
"""

from __future__ import annotations
from typing import Any


UTTERANCE_DATASET: list[dict[str, Any]] = [

    # ══════════════════════════════════════════════════════════════════════
    # CRM TOOL — store / retrieve / update customer info
    # ══════════════════════════════════════════════════════════════════════
    {
        "id": "crm_001",
        "category": "crm",
        "utterance": "My name is Alice Johnson.",
        "expected_tool": "crm",
        "expected_args": {"action": "upsert", "name": "Alice Johnson"},
        "notes": "User introduces themselves → CRM upsert with name",
    },
    {
        "id": "crm_002",
        "category": "crm",
        "utterance": "My name is Bob and I live at 12 Rose Street, Karachi.",
        "expected_tool": "crm",
        "expected_args": {"action": "upsert", "name": "Bob"},
        "notes": "Name + address → CRM upsert",
    },
    {
        "id": "crm_003",
        "category": "crm",
        "utterance": "My email is carol@example.com.",
        "expected_tool": "crm",
        "expected_args": {"action": "upsert", "email": "carol@example.com"},
        "notes": "Email provided → CRM upsert",
    },
    {
        "id": "crm_004",
        "category": "crm",
        "utterance": "You can reach me at +92-300-1234567.",
        "expected_tool": "crm",
        "expected_args": {"action": "upsert"},
        "notes": "Phone number → CRM upsert",
    },
    {
        "id": "crm_005",
        "category": "crm",
        "utterance": "My delivery address is 45 Garden Road, Lahore, Punjab.",
        "expected_tool": "crm",
        "expected_args": {"action": "upsert"},
        "notes": "Address update → CRM upsert",
    },
    {
        "id": "crm_006",
        "category": "crm",
        "utterance": "Please update my phone number to +92-321-9876543.",
        "expected_tool": "crm",
        "expected_args": {"action": "update"},
        "notes": "Explicit update request → CRM update",
    },
    {
        "id": "crm_007",
        "category": "crm",
        "utterance": "Can you look up my order details? My ID is user_abc123.",
        "expected_tool": "crm",
        "expected_args": {"action": "get", "user_id": "user_abc123"},
        "notes": "Lookup by user_id → CRM get",
    },

    # ══════════════════════════════════════════════════════════════════════
    # CALCULATOR TOOL — price arithmetic
    # ══════════════════════════════════════════════════════════════════════
    {
        "id": "calc_001",
        "category": "calculator",
        "utterance": "How much would 3 medium plushies cost in total?",
        "expected_tool": "calculator",
        "expected_args": {"expression": "3 * 1000"},
        "notes": "3 × medium min price → calculator",
    },
    {
        "id": "calc_002",
        "category": "calculator",
        "utterance": "I want 2 small keychains and 1 large stuffed animal. What's the total?",
        "expected_tool": "calculator",
        "expected_args": {"expression": "2 * 500 + 2000"},
        "notes": "Multi-item total → calculator",
    },
    {
        "id": "calc_003",
        "category": "calculator",
        "utterance": "What is 5 times 800?",
        "expected_tool": "calculator",
        "expected_args": {"expression": "5 * 800"},
        "notes": "Direct arithmetic question → calculator",
    },
    {
        "id": "calc_004",
        "category": "calculator",
        "utterance": "If I order 4 items at Rs 1500 each, what do I pay?",
        "expected_tool": "calculator",
        "expected_args": {"expression": "4 * 1500"},
        "notes": "Cost calculation → calculator",
    },
    {
        "id": "calc_005",
        "category": "calculator",
        "utterance": "Calculate 2500 + 3000 + 800 for me.",
        "expected_tool": "calculator",
        "expected_args": {"expression": "2500 + 3000 + 800"},
        "notes": "Explicit calculation request → calculator",
    },

    # ══════════════════════════════════════════════════════════════════════
    # CALENDAR TOOL — delivery date estimation
    # ══════════════════════════════════════════════════════════════════════
    {
        "id": "cal_001",
        "category": "calendar",
        "utterance": "When will my order arrive?",
        "expected_tool": "calendar",
        "expected_args": {"processing_days": 7},
        "notes": "Delivery date question → calendar with 7 days",
    },
    {
        "id": "cal_002",
        "category": "calendar",
        "utterance": "How long does delivery take?",
        "expected_tool": "calendar",
        "expected_args": {"processing_days": 7},
        "notes": "Delivery timing question → calendar",
    },
    {
        "id": "cal_003",
        "category": "calendar",
        "utterance": "What's the estimated delivery date for my order?",
        "expected_tool": "calendar",
        "expected_args": {"processing_days": 7},
        "notes": "Delivery estimate request → calendar",
    },
    {
        "id": "cal_004",
        "category": "calendar",
        "utterance": "When can I expect my crochet cat to arrive?",
        "expected_tool": "calendar",
        "expected_args": {"processing_days": 7},
        "notes": "Order arrival question → calendar",
    },
    {
        "id": "cal_005",
        "category": "calendar",
        "utterance": "How many days until my order is delivered?",
        "expected_tool": "calendar",
        "expected_args": {"processing_days": 7},
        "notes": "Days-until-delivery → calendar",
    },
    {
        "id": "cal_006",
        "category": "calendar",
        "utterance": "What date will I receive my order?",
        "expected_tool": "calendar",
        "expected_args": {},
        "notes": "Date query → calendar",
    },
    {
        "id": "cal_007",
        "category": "calendar",
        "utterance": "When is my delivery scheduled?",
        "expected_tool": "calendar",
        "expected_args": {},
        "notes": "Delivery schedule question → calendar",
    },

    # ══════════════════════════════════════════════════════════════════════
    # WEATHER TOOL — delivery weather impact
    # ══════════════════════════════════════════════════════════════════════
    {
        "id": "wx_001",
        "category": "weather",
        "utterance": "Will the weather affect my delivery in Karachi?",
        "expected_tool": "weather",
        "expected_args": {"action": "assess_delivery", "location": "Karachi"},
        "notes": "Delivery weather check → weather assess_delivery",
    },
    {
        "id": "wx_002",
        "category": "weather",
        "utterance": "Is there a storm in Lahore that might delay my order?",
        "expected_tool": "weather",
        "expected_args": {"location": "Lahore"},
        "notes": "Storm/delay question → weather",
    },
    {
        "id": "wx_003",
        "category": "weather",
        "utterance": "What's the weather like in London today?",
        "expected_tool": "weather",
        "expected_args": {"action": "check_weather", "location": "London"},
        "notes": "Weather check → weather check_weather",
    },
    {
        "id": "wx_004",
        "category": "weather",
        "utterance": "It's raining here. Will delivery be delayed?",
        "expected_tool": "weather",
        "expected_args": {},
        "notes": "Rain + delivery → weather (location may be asked)",
    },
    {
        "id": "wx_005",
        "category": "weather",
        "utterance": "Check the forecast for Delhi.",
        "expected_tool": "weather",
        "expected_args": {"location": "Delhi"},
        "notes": "Explicit forecast request → weather",
    },

    # ══════════════════════════════════════════════════════════════════════
    # NO TOOL — general / conversational / off-topic
    # ══════════════════════════════════════════════════════════════════════
    {
        "id": "none_001",
        "category": "no_tool",
        "utterance": "Hello! I'd like to place an order.",
        "expected_tool": None,
        "expected_args": {},
        "notes": "Greeting / intent → no tool, conversational response",
    },
    {
        "id": "none_002",
        "category": "no_tool",
        "utterance": "Do you make stuffed animals?",
        "expected_tool": None,
        "expected_args": {},
        "notes": "Product question → no tool, conversational answer from knowledge",
    },
    {
        "id": "none_003",
        "category": "no_tool",
        "utterance": "What is your return policy?",
        "expected_tool": None,
        "expected_args": {},
        "notes": "Policy question → no tool",
    },
    {
        "id": "none_004",
        "category": "no_tool",
        "utterance": "Tell me about your gift wrapping.",
        "expected_tool": None,
        "expected_args": {},
        "notes": "Business info question → no tool",
    },
    {
        "id": "none_005",
        "category": "no_tool",
        "utterance": "What is the capital of France?",
        "expected_tool": None,
        "expected_args": {},
        "notes": "Off-topic → no tool, redirect",
    },
    {
        "id": "none_006",
        "category": "no_tool",
        "utterance": "Can I pay with a credit card?",
        "expected_tool": None,
        "expected_args": {},
        "notes": "Payment question → no tool, COD policy answer",
    },
    {
        "id": "none_007",
        "category": "no_tool",
        "utterance": "Yes, that looks great! Please confirm my order.",
        "expected_tool": None,
        "expected_args": {},
        "notes": "Order confirmation → no tool",
    },
]


def get_utterances_by_category(category: str) -> list[dict]:
    """Filter dataset by category label."""
    return [u for u in UTTERANCE_DATASET if u["category"] == category]


def get_all_categories() -> list[str]:
    return list({u["category"] for u in UTTERANCE_DATASET})


if __name__ == "__main__":
    cats = get_all_categories()
    print(f"Total utterances : {len(UTTERANCE_DATASET)}")
    for cat in sorted(cats):
        items = get_utterances_by_category(cat)
        print(f"  {cat:15s}: {len(items)} items")
