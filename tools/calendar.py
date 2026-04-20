"""Calendar / Delivery Estimation tool for crochet order date calculations."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict


class CalendarTool:
    """Estimate delivery dates for custom crochet orders."""

    @staticmethod
    def schema() -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "order_date": {
                    "type": "string",
                    "description": "The date the order was placed (format: YYYY-MM-DD).",
                },
                "processing_days": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Number of days needed to process and prepare the order.",
                },
            },
            "required": ["order_date", "processing_days"],
            "additionalProperties": False,
        }

    async def run(self, args: Dict[str, Any]) -> Dict[str, Any]:
        order_date_str = str(args.get("order_date", "")).strip()
        if not order_date_str:
            raise ValueError("Calendar 'order_date' is required.")

        processing_days = args.get("processing_days")
        if processing_days is None:
            raise ValueError("Calendar 'processing_days' is required.")

        processing_days = int(processing_days)
        if processing_days < 1:
            raise ValueError("'processing_days' must be at least 1.")

        result = _DeliveryEstimator().estimate(order_date_str, processing_days)
        return result


class _DeliveryEstimator:
    DATE_FORMAT = "%Y-%m-%d"
    LONG_ORDER_THRESHOLD = 7
    LONG_ORDER_NOTE = "This is a custom order and may take longer."

    def estimate(self, order_date_str: str, processing_days: int) -> Dict[str, Any]:
        order_date = self._parse_date(order_date_str)
        delivery_date = order_date + timedelta(days=processing_days)

        message = (
            f"Your order placed on {order_date.strftime(self.DATE_FORMAT)} "
            f"is estimated to be delivered by {delivery_date.strftime(self.DATE_FORMAT)}, "
            f"after {processing_days} processing day(s)."
        )

        note = None
        if processing_days > self.LONG_ORDER_THRESHOLD:
            note = self.LONG_ORDER_NOTE
            message += f" {note}"

        return {
            "order_date": order_date.strftime(self.DATE_FORMAT),
            "processing_days": processing_days,
            "estimated_delivery_date": delivery_date.strftime(self.DATE_FORMAT),
            "message": message,
            "note": note,
        }

    def _parse_date(self, date_str: str) -> date:
        try:
            return datetime.strptime(date_str, self.DATE_FORMAT).date()
        except ValueError:
            raise ValueError(
                f"Invalid 'order_date' format: '{date_str}'. Expected YYYY-MM-DD."
            )