"""
convo_manager.py - Conversation Manager for Crochetzies
Phase III: Conversation Orchestration, State Management, and RAG Integration
"""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import AsyncIterator
from uuid import uuid4

import ollama

from config import MAX_TURNS, MODEL_NAME
from orchestrator import execute_tool_sync
from prompt_temp import build_summarize_prompt, build_system_prompt
#from retrieval.retriever import retrieve

SESSION_END_SIGNAL = "order-complete"

TOOL_CALL_PATTERN = re.compile(
    r'\{\s*"tool"\s*:\s*"(?P<tool>[^"]+)"\s*,\s*"args"\s*:\s*(?P<args>\{[^{}]*\})\s*\}',
    re.DOTALL,
)

WEATHER_KEYWORDS = (
    "weather", "forecast", "rain", "rainy", "storm", "snow",
    "delivery weather", "weather impact", "will delivery be affected",
)

CALENDAR_KEYWORDS = (
    "when will", "delivery date", "arrive", "arrival", "how long",
    "how many days", "estimated date", "delivery time", "when can i expect",
    "expected delivery", "when will it arrive", "when will my order",
    "delivery estimate", "when should i expect", "when is my order",
    "what date", "which date", "delivery day",
)


class ConversationManager:
    def __init__(self):
        self.history: list[dict] = []
        self.summary: str | None = None
        self._turn_count: int = 0
        self._system_prompt: str | None = None
        self.session_ended: bool = False
        self.last_order_id: str | None = None
        self.awaiting_weather_check: bool = False

    # ------------------------------------------------------------------ #
    # Lazy system prompt                                                   #
    # ------------------------------------------------------------------ #

    @property
    def system_prompt(self) -> str:
        if self._system_prompt is None:
            self._system_prompt = build_system_prompt()
        return self._system_prompt

    # ------------------------------------------------------------------ #
    # Public API — sync                                                    #
    # ------------------------------------------------------------------ #

    def get_response(self, user_input: str, stream: bool = False) -> str:
        self._add_turn("user", user_input)
        self._manage_memory()

        # Check for calendar request FIRST (higher priority than weather)
        calendar_reply = self._handle_calendar_request_sync(user_input)
        if calendar_reply:
            return self._finalize_response(calendar_reply)

        weather_reply = self._handle_weather_request_sync(user_input)
        if weather_reply:
            return self._finalize_response(weather_reply)

        rag_context = self._get_rag_context(user_input)

        if stream:
            bot_reply = self._stream_response_sync(rag_context)
        else:
            response = ollama.chat(
                model=MODEL_NAME,
                messages=self._build_messages(rag_context),
            )
            bot_reply = response["message"]["content"]

        tool_reply = self._handle_tool_call(user_input, bot_reply)
        if tool_reply:
            return self._finalize_response(tool_reply)

        return self._finalize_response(bot_reply)

    def finalize_response(self, bot_reply: str) -> str:
        """Public alias for _finalize_response."""
        return self._finalize_response(bot_reply)

    # ------------------------------------------------------------------ #
    # Public API — async (WebSocket path)                                  #
    # ------------------------------------------------------------------ #

    async def get_response_async(self, user_input: str) -> str:
        """Full async round-trip (no streaming)."""
        self._add_turn("user", user_input)
        self._manage_memory()

        calendar_reply = await self._handle_calendar_request_async(user_input)
        if calendar_reply:
            return self._finalize_response(calendar_reply)

        weather_reply = await self._handle_weather_request_async(user_input)
        if weather_reply:
            return self._finalize_response(weather_reply)

        rag_context = self._get_rag_context(user_input)

        loop = asyncio.get_event_loop()
        bot_reply = await loop.run_in_executor(
            None,
            lambda: ollama.chat(
                model=MODEL_NAME,
                messages=self._build_messages(rag_context),
            )["message"]["content"],
        )

        tool_reply = self._handle_tool_call(user_input, bot_reply)
        if tool_reply:
            return self._finalize_response(tool_reply)

        return self._finalize_response(bot_reply)

    async def stream_response_async(self, user_input: str) -> AsyncIterator[str]:
        """
        Async generator for WebSocket streaming.
        """
        self._add_turn("user", user_input)
        self._manage_memory()

        # Calendar short-circuit
        calendar_reply = await self._handle_calendar_request_async(user_input)
        if calendar_reply:
            self.last_streamed_reply = calendar_reply
            yield calendar_reply
            return

        # Weather short-circuit
        weather_reply = await self._handle_weather_request_async(user_input)
        if weather_reply:
            self.last_streamed_reply = weather_reply
            yield weather_reply
            return

        rag_context = self._get_rag_context(user_input)
        messages = self._build_messages(rag_context)

        full_reply = ""
        loop = asyncio.get_event_loop()

        response_stream = await loop.run_in_executor(
            None,
            lambda: ollama.chat(model=MODEL_NAME, messages=messages, stream=True),
        )

        for chunk in response_stream:
            token = chunk["message"]["content"]
            full_reply += token
            yield token
            await asyncio.sleep(0)

        tool_reply = self._handle_tool_call(user_input, full_reply)
        if tool_reply:
            full_reply = tool_reply
            yield tool_reply

        self.last_streamed_reply = full_reply

    # ------------------------------------------------------------------ #
    # Calendar handling — NEW                                              #
    # ------------------------------------------------------------------ #

    def _looks_like_calendar_request(self, user_input: str) -> bool:
        """Check if user is asking about delivery date/timing."""
        normalized = self._normalize_text(user_input)
        return any(kw in normalized for kw in CALENDAR_KEYWORDS)

    def _handle_calendar_request_sync(self, user_input: str) -> str | None:
        """Synchronous calendar request handler."""
        if not self._looks_like_calendar_request(user_input):
            return None
        return self._generate_calendar_reply_sync()

    async def _handle_calendar_request_async(self, user_input: str) -> str | None:
        """Asynchronous calendar request handler."""
        if not self._looks_like_calendar_request(user_input):
            return None
        return await self._generate_calendar_reply_async()

    def _generate_calendar_reply_sync(self) -> str:
        """Call calendar tool and format response."""
        today = datetime.now().strftime("%Y-%m-%d")
        result = execute_tool_sync("calendar", {
            "order_date": today,
            "processing_days": 7
        })

        if not result.get("ok"):
            error_msg = result.get("error", "Unknown error")
            print(f"[Calendar] Tool failed: {error_msg}")
            return (
                f"I tried to calculate your delivery date but ran into an issue. "
                f"Typically, delivery takes 5-7 business days. You can expect your order "
                f"within about a week from today!"
            )

        data = result.get("result", {})
        delivery_date = data.get("estimated_delivery_date", "within 7 days")
        message = data.get("message", f"Your order will be delivered by {delivery_date}.")
        
        # Format the date nicely if possible
        try:
            date_obj = datetime.strptime(delivery_date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%A, %B %d, %Y")
            return f"Your order will be delivered by {formatted_date}! That's about 7 days from today. 😊"
        except (ValueError, TypeError):
            return message

    async def _generate_calendar_reply_async(self) -> str:
        """Async version of calendar reply generation."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._generate_calendar_reply_sync)

    # ------------------------------------------------------------------ #
    # Reset / stats                                                        #
    # ------------------------------------------------------------------ #

    def reset(self):
        self.history = []
        self.summary = None
        self._turn_count = 0
        self._system_prompt = None
        self.session_ended = False
        self.last_order_id = None
        self.awaiting_weather_check = False

    def get_stats(self) -> dict:
        return {
            "total_turns": self._turn_count,
            "history_window": len(self.history),
            "has_summary": self.summary is not None,
            "session_ended": self.session_ended,
        }

    # ------------------------------------------------------------------ #
    # RAG                                                                  #
    # ------------------------------------------------------------------ #

    def _get_rag_context(self, user_input: str) -> str | None:
        try:
            from retrieval.retriever import retrieve  # ← add this line
            chunks = retrieve(user_input)
            if not chunks:
                return None
            formatted = "\n\n".join(
                f"--- Source: {c.source} (Relevance: {c.score:.3f}) ---\n{c.text}"
                for c in chunks
            )
            return formatted
        except Exception as exc:
            print(f"[RAG] Retrieval error (non-fatal): {exc}")
            return None

    # ------------------------------------------------------------------ #
    # Message builder                                                      #
    # ------------------------------------------------------------------ #

    def _build_messages(self, current_rag_context: str | None = None) -> list[dict]:
        messages: list[dict] = [{"role": "system", "content": self.system_prompt}]

        if self.summary:
            messages.append({
                "role": "system",
                "content": "Context from earlier in the conversation:\n" + self.summary,
            })

        if current_rag_context:
            messages.append({
                "role": "system",
                "content": (
                    "Relevant business information retrieved from the knowledge base:\n"
                    + current_rag_context
                    + "\n\nUse this information to answer the user's latest query "
                    "if applicable. Do not mention that you retrieved this information."
                ),
            })

        for turn in self.history:
            messages.append({"role": turn["role"], "content": turn["content"]})

        return messages

    # ------------------------------------------------------------------ #
    # Streaming — sync (for CLI / non-WebSocket use)                       #
    # ------------------------------------------------------------------ #

    def _stream_response_sync(self, rag_context: str | None = None) -> str:
        full_reply = ""
        response_stream = ollama.chat(
            model=MODEL_NAME,
            messages=self._build_messages(rag_context),
            stream=True,
        )
        for chunk in response_stream:
            token = chunk["message"]["content"]
            print(token, end="", flush=True)
            full_reply += token
        print()
        return full_reply

    # ------------------------------------------------------------------ #
    # Finalise                                                             #
    # ------------------------------------------------------------------ #

    def _finalize_response(self, bot_reply: str) -> str:
        self._add_turn("assistant", bot_reply)
        self._turn_count += 1

        if SESSION_END_SIGNAL in bot_reply.lower():
            self.session_ended = True
            order_id = self._generate_order_id()
            self.last_order_id = order_id
            self._save_history()
            bot_reply = self._append_order_id_to_response(bot_reply, order_id)
            self.history[-1]["content"] = bot_reply

        return bot_reply

    # ------------------------------------------------------------------ #
    # Weather — sync                                                       #
    # ------------------------------------------------------------------ #

    def _handle_weather_request_sync(self, user_input: str) -> str | None:
        if self.awaiting_weather_check:
            return self._handle_weather_followup_sync(user_input)
        if not self._looks_like_weather_request(user_input):
            return None
        location = self._extract_location(user_input)
        if not location:
            self.awaiting_weather_check = True
            return (
                "I'd be happy to check delivery weather for you! "
                "Could you share your city or delivery location?"
            )
        return self._generate_weather_reply_sync(location)

    def _handle_weather_followup_sync(self, user_input: str) -> str | None:
        lowered = self._normalize_text(user_input)
        cancel_phrases = ("dont know", "do not know", "never mind", "cancel", "no thanks", "skip")
        order_intent_phrases = ("i want", "crochet", "order", "confirm", "item")

        location = self._extract_location(user_input)
        if location:
            self.awaiting_weather_check = False
            return self._generate_weather_reply_sync(location)
        if any(phrase in lowered for phrase in cancel_phrases):
            self.awaiting_weather_check = False
            return "No problem! Let me know if you need anything else."
        if any(phrase in lowered for phrase in order_intent_phrases):
            self.awaiting_weather_check = False
            return None
        return "Could you tell me the city or area for delivery so I can check the weather?"

    def _generate_weather_reply_sync(self, location: str) -> str:
        result = execute_tool_sync("weather", {"action": "assess_delivery", "location": location})
        if not result.get("ok"):
            self.awaiting_weather_check = True
            return f"I couldn't check the weather for {location}. {result.get('error', 'Please try another location.')}"

        assessment = result.get("result", {}).get("assessment", {})
        self.awaiting_weather_check = False
        parts = [f"Weather for {assessment.get('location', location)}: {assessment.get('weather_condition', 'unknown')}."]
        if assessment.get("temperature") is not None:
            parts.append(f"Temperature: {assessment['temperature']} °C.")
        if assessment.get("humidity") is not None:
            parts.append(f"Humidity: {assessment['humidity']}%.")
        if assessment.get("wind_speed") is not None:
            parts.append(f"Wind speed: {assessment['wind_speed']}.")
        parts.append(f"Delivery impact: {assessment.get('delivery_impact', 'Unable to assess.')}")
        return " ".join(parts)

    # ------------------------------------------------------------------ #
    # Weather — async                                                      #
    # ------------------------------------------------------------------ #

    async def _handle_weather_request_async(self, user_input: str) -> str | None:
        if self.awaiting_weather_check:
            return await self._handle_weather_followup_async(user_input)
        if not self._looks_like_weather_request(user_input):
            return None
        location = self._extract_location(user_input)
        if not location:
            self.awaiting_weather_check = True
            return (
                "I'd be happy to check delivery weather for you! "
                "Could you share your city or delivery location?"
            )
        return await self._generate_weather_reply_async(location)

    async def _handle_weather_followup_async(self, user_input: str) -> str | None:
        lowered = self._normalize_text(user_input)
        cancel_phrases = ("dont know", "do not know", "never mind", "cancel", "no thanks", "skip")
        order_intent_phrases = ("i want", "crochet", "order", "confirm", "item")

        location = self._extract_location(user_input)
        if location:
            self.awaiting_weather_check = False
            return await self._generate_weather_reply_async(location)
        if any(phrase in lowered for phrase in cancel_phrases):
            self.awaiting_weather_check = False
            return "No problem! Let me know if you need anything else."
        if any(phrase in lowered for phrase in order_intent_phrases):
            self.awaiting_weather_check = False
            return None
        return "Could you tell me the city or area for delivery so I can check the weather?"

    async def _generate_weather_reply_async(self, location: str) -> str:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: execute_tool_sync("weather", {"action": "assess_delivery", "location": location}),
        )
        if not result.get("ok"):
            self.awaiting_weather_check = True
            return f"I couldn't check the weather for {location}. {result.get('error', 'Please try another location.')}"

        assessment = result.get("result", {}).get("assessment", {})
        self.awaiting_weather_check = False
        parts = [f"Weather for {assessment.get('location', location)}: {assessment.get('weather_condition', 'unknown')}."]
        if assessment.get("temperature") is not None:
            parts.append(f"Temperature: {assessment['temperature']} °C.")
        if assessment.get("humidity") is not None:
            parts.append(f"Humidity: {assessment['humidity']}%.")
        if assessment.get("wind_speed") is not None:
            parts.append(f"Wind speed: {assessment['wind_speed']}.")
        parts.append(f"Delivery impact: {assessment.get('delivery_impact', 'Unable to assess.')}")
        return " ".join(parts)

    # ------------------------------------------------------------------ #
    # Shared helpers                                                       #
    # ------------------------------------------------------------------ #

    def _looks_like_weather_request(self, user_input: str) -> bool:
        return any(kw in self._normalize_text(user_input) for kw in WEATHER_KEYWORDS)

    def _extract_location(self, user_input: str) -> str | None:
        normalized = self._normalize_text(user_input)
        for city in ("karachi", "lahore", "islamabad", "rawalpindi", "delhi", "london", "new york", "dubai"):
            if city in normalized:
                return city.title()
        match = re.search(r"(?:in|at|for)\s+([a-zA-Z]+(?:\s+[a-zA-Z]+)?)", user_input)
        return match.group(1).strip().title() if match else None

    def _normalize_text(self, text: str) -> str:
        return text.lower().strip()

    # ------------------------------------------------------------------ #
    # Tool calling                                                         #
    # ------------------------------------------------------------------ #

    def _handle_tool_call(self, user_input: str, bot_reply: str) -> str | None:
        match = TOOL_CALL_PATTERN.search(bot_reply)
        if not match:
            return None

        tool_name = match.group("tool").strip()
        try:
            args = json.loads(match.group("args").strip())
        except json.JSONDecodeError as exc:
            print(f"[Tool] Could not parse args for '{tool_name}': {exc}")
            return None

        if not tool_name or not isinstance(args, dict):
            return None

        result = execute_tool_sync(tool_name, args)
        if not result.get("ok"):
            error_msg = result.get("error", "An unknown error occurred.")
            print(f"[Tool] '{tool_name}' failed: {error_msg}")
            return (
                f"I tried to use the {tool_name} tool but ran into an issue: {error_msg} "
                "Please try again or contact us directly."
            )

        return self._resolve_tool_result(user_input, tool_name, result["result"])

    def _resolve_tool_result(self, user_input: str, tool_name: str, result: dict) -> str:
        # Special handling for calendar to ensure nice formatting
        if tool_name == "calendar":
            delivery_date = result.get("estimated_delivery_date", "within 7 days")
            try:
                date_obj = datetime.strptime(delivery_date, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%A, %B %d, %Y")
                return f"Your order will be delivered by {formatted_date}! That's about 7 days from today. 😊"
            except (ValueError, TypeError):
                return result.get("message", f"Your order will be delivered by {delivery_date}.")

        # Default handling for other tools
        result_text = json.dumps(result, indent=2)
        followup_prompt = (
            f"The user asked: {user_input}\n\n"
            f"You called the '{tool_name}' tool and received this result:\n"
            f"{result_text}\n\n"
            "Using this information, give the user a clear, friendly, natural-language reply. "
            "Do not expose raw JSON. Do not add placeholder text."
        )
        messages = self._build_messages()
        messages.append({"role": "user", "content": followup_prompt})
        response = ollama.chat(model=MODEL_NAME, messages=messages)
        return response["message"]["content"]

    # ------------------------------------------------------------------ #
    # Memory                                                               #
    # ------------------------------------------------------------------ #

    def _add_turn(self, role: str, content: str):
        self.history.append({"role": role, "content": content})

    def _manage_memory(self):
        if len(self.history) <= MAX_TURNS:
            return
        cutoff = len(self.history) - MAX_TURNS
        old_turns = self.history[:cutoff]
        self.history = self.history[cutoff:]
        new_summary = self._summarize(old_turns)
        if self.summary:
            combined_prompt = (
                f"Previous summary: {self.summary}\n\n"
                f"New conversation segment to merge in: {new_summary}\n\n"
                "Merge these into a single concise summary (3-4 sentences) covering "
                "all order details, customer info, and any changes."
            )
            self.summary = ollama.chat(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": combined_prompt}],
            )["message"]["content"]
        else:
            self.summary = new_summary

    def _summarize(self, old_turns: list[dict]) -> str:
        return ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": build_summarize_prompt(old_turns)}],
        )["message"]["content"]

    # ------------------------------------------------------------------ #
    # Order persistence                                                    #
    # ------------------------------------------------------------------ #

    def _save_history(self):
        os.makedirs("order_history", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"order_history/order_{timestamp}.json"

        order_summary_text = ""
        for turn in reversed(self.history):
            if turn["role"] == "assistant" and "ORDER SUMMARY" in turn["content"].upper():
                order_summary_text = turn["content"]
                break

        def extract(label: str) -> str:
            for line in order_summary_text.splitlines():
                if label.lower() in line.lower():
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        return parts[1].strip().split("|")[0].strip()
            return "Not found"

        order_id = self.last_order_id or self._generate_order_id()
        self.last_order_id = order_id

        data = {
            "timestamp": datetime.now().isoformat(),
            "order_id": order_id,
            "total_turns": self._turn_count,
            "order": {
                "item": extract("Item"),
                "colors": extract("Colors"),
                "size": extract("Size"),
                "extras": extract("Extras"),
                "quantity": extract("Qty"),
                "price": extract("Total"),
                "name": extract("Name"),
                "address": extract("Address"),
                "payment": "Cash on Delivery",
                "delivery": "5-7 business days",
            },
        }
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n[Order saved → {filepath}]")
        except OSError as exc:
            print(f"[Order] Could not save history: {exc}")

    def _generate_order_id(self) -> str:
        return f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:6].upper()}"

    def _append_order_id_to_response(self, bot_reply: str, order_id: str) -> str:
        return (
            bot_reply
            + f"\n\nYour Order ID: **{order_id}**\n"
            "Please save this for order tracking and reference."
        )