"""Tool 3: Supermarket Order Status & Delivery/Pickup Tracker (📘 Lesson 2)."""

from typing import Optional
from packages.tools.base import SupermarketTool, ToolResult
from data.mock_database import db


def track_order_status(order_id: str, phone_number: Optional[str] = None) -> ToolResult:
    """Track fulfillment status of Click & Collect and Delivery orders."""
    if not order_id or not order_id.strip():
        return ToolResult(
            success=False,
            error="order_id is required.",
            recovery_suggestion="Ask the customer for their order number (e.g., 'ORD-9481').",
        )

    clean_order_id = order_id.strip().upper()
    if not clean_order_id.startswith("ORD-") and clean_order_id.isdigit():
        clean_order_id = f"ORD-{clean_order_id}"

    result = db.track_order(clean_order_id, phone_number=phone_number)

    if "error" in result:
        return ToolResult(
            success=False,
            error=result["error"],
            recovery_suggestion=(
                "Ask customer to verify their order ID format (e.g., 'ORD-9481') or confirm the phone number on file."
            ),
        )

    return ToolResult(success=True, data=result)


order_tool = SupermarketTool(
    name="track_order_status",
    description=(
        "Track the live status of an online order, Click & Collect pickup, or home delivery. "
        "Returns order progress (Packing, Ready for Pickup, Out for Delivery), assigned pickup bay, "
        "estimated ready time/ETA, and item summary. Requires order_id and optional customer phone for authentication."
    ),
    parameters={
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "Order identifier (e.g., 'ORD-9481' or numeric digits '9481').",
            },
            "phone_number": {
                "type": "string",
                "description": "Customer phone number used when placing the order for verification.",
            },
        },
        "required": ["order_id"],
    },
    func=track_order_status,
)

