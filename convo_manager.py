"""
convo_manager.py — Conversation Manager for Crochetzies
Phase III: Conversation Orchestration & State Management
"""

import json
import os
from datetime import datetime

import ollama
from prompt_temp import build_system_prompt, build_summarize_prompt
from config import MAX_TURNS, MODEL_NAME

# Phrase the model uses at the end of a confirmed order (must match prompt)
SESSION_END_SIGNAL = "have a wonderful day"


class ConversationManager:
    """
    Manages a single customer conversation session.

    Responsibilities:
      - Maintains full dialogue history
      - Triggers hybrid memory compression when history is too long
      - Builds structured prompts via prompt_temp.py
      - Calls the local LLM via Ollama
      - Enforces single-question turn-taking policy
      - Detects session end and saves history to JSON

    Memory Strategy: Sliding Window + Summarisation
      - Last MAX_TURNS turns are always kept verbatim
      - Older turns are compressed into a 3-4 sentence summary
      - Both summary + recent turns are sent to the model every turn
    """

    def __init__(self):
        self.history: list[dict] = []
        self.summary: str | None = None
        self._turn_count: int = 0
        self.system_prompt: str = build_system_prompt()  # pulls prices from config
        self.session_ended: bool = False                 # True after order confirmed

    # ── Public API ────────────────────────────────────────────────────────────

    def get_response(self, user_input: str, stream: bool = False) -> str:
        """
        Main entry point.
        1. Records user message
        2. Manages memory if needed
        3. Calls LLM (with optional streaming)
        4. Records bot reply
        5. Checks if session should end → saves history if so
        Returns the bot reply string.
        """
        self._add_turn("user", user_input)
        self._manage_memory()

        if stream:
            bot_reply = self._stream_response()
        else:
            response = ollama.chat(
                model=MODEL_NAME,
                messages=self._build_messages()
            )
            bot_reply = response["message"]["content"]

        self._add_turn("assistant", bot_reply)
        self._turn_count += 1

        # Detect order confirmation and save history
        if SESSION_END_SIGNAL in bot_reply.lower():
            self.session_ended = True
            self._save_history()

        return bot_reply

    def _build_messages(self) -> list:
        """
        Builds the message list for ollama.chat().
        Structure:
          [system prompt — built dynamically, includes live prices]
          [summary injected as a system note, if any]
          [history turns as alternating user/assistant messages]
        """
        messages = [{"role": "system", "content": self.system_prompt}]

        if self.summary:
            messages.append({
                "role": "system",
                "content": f"Context from earlier in the conversation: {self.summary}"
            })

        for turn in self.history:
            messages.append({"role": turn["role"], "content": turn["content"]})

        return messages

    def _stream_response(self) -> str:
        """Streams tokens to stdout and returns the full reply string."""
        full_reply = ""
        response_stream = ollama.chat(
            model=MODEL_NAME,
            messages=self._build_messages(),
            stream=True
        )
        for chunk in response_stream:
            token = chunk["message"]["content"]
            print(token, end="", flush=True)
            full_reply += token
        print()
        return full_reply

    def reset(self):
        """Clears all state — call this when a new customer session begins."""
        self.history = []
        self.summary = None
        self._turn_count = 0
        self.session_ended = False

    def get_stats(self) -> dict:
        """Returns session statistics (useful for benchmarking / debugging)."""
        return {
            "total_turns": self._turn_count,
            "history_window": len(self.history),
            "has_summary": self.summary is not None,
            "session_ended": self.session_ended,
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    def _add_turn(self, role: str, content: str):
        """Appends a turn to the conversation history."""
        self.history.append({"role": role, "content": content})

    def _save_history(self):
        """
        Extracts and saves only the confirmed order details from the conversation.
        Parses the ORDER SUMMARY block from the bot's last summary message.
        Filename: order_YYYYMMDD_HHMMSS.json
        """
        os.makedirs("order_history", exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"order_history/order_{timestamp}.json"

        # Find the last message that contains the order summary
        order_summary_text = ""
        for turn in reversed(self.history):
            if turn["role"] == "assistant" and "ORDER SUMMARY" in turn["content"].upper():
                order_summary_text = turn["content"]
                break

        # Helper to extract a field value from the summary text
        def extract(label: str) -> str:
            for line in order_summary_text.splitlines():
                if label.lower() in line.lower():
                    # Grab everything after the colon or pipe
                    parts = line.split(":", 1)
                    if len(parts) > 1:
                        return parts[1].strip().split("|")[0].strip()
            return "Not found"

        data = {
            "timestamp": datetime.now().isoformat(),
            "total_turns": self._turn_count,
            "order": {
                "item":     extract("Item"),
                "colors":   extract("Colors"),
                "size":     extract("Size"),
                "extras":   extract("Extras"),
                "quantity": extract("Qty"),
                "price":    extract("Total"),
                "name":     extract("Name"),
                "address":  extract("Address"),
                "payment":  "Cash on Delivery",
                "delivery": "5-7 business days",
            }
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n[Order saved → {filepath}]")
    def _manage_memory(self):
        """
        Hybrid memory: if history exceeds MAX_TURNS, compress the oldest half
        into a summary and keep only the most recent MAX_TURNS turns.
        """
        if len(self.history) <= MAX_TURNS:
            return

        cutoff = len(self.history) - MAX_TURNS
        old_turns = self.history[:cutoff]
        recent_turns = self.history[cutoff:]

        new_summary = self._summarize(old_turns)
        if self.summary:
            combined_prompt = (
                f"Previous summary: {self.summary}\n\n"
                f"Additional context to merge in: {new_summary}\n\n"
                "Merge these into a single 3-4 sentence summary covering all order details."
            )
            merge_response = ollama.chat(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": combined_prompt}]
            )
            self.summary = merge_response["message"]["content"]
        else:
            self.summary = new_summary

        self.history = recent_turns

    def _summarize(self, old_turns: list[dict]) -> str:
        """Calls the LLM to produce a concise summary of old turns."""
        summarize_prompt = build_summarize_prompt(old_turns)
        response = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": summarize_prompt}]
        )
        return response["message"]["content"]