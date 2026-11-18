"""Tool 2: Supermarket Store Information, Hours & Policy Lookup (📘 Lesson 2)."""

from packages.tools.base import SupermarketTool, ToolResult
from data.mock_database import db


def get_store_info(query_type: str, store_id: str = "STORE-001") -> ToolResult:
    """Lookup store operating hours, department timings, address, parking amenities, or policies."""
    if not query_type or not query_type.strip():
        return ToolResult(
            success=False,
            error="query_type cannot be empty.",
            recovery_suggestion="Specify query_type as 'hours', 'bakery', 'pharmacy', 'parking', 'returns', or 'policies'.",
        )

    store = db.get_store(store_id)
    if not store:
        available_stores = [s["store_id"] for s in db.stores]
        return ToolResult(
            success=False,
            error=f"Store branch '{store_id}' not found.",
            recovery_suggestion=f"Please choose a valid store_id from: {available_stores}",
        )

    info = db.query_store_info(query_type, store_id=store_id)
    return ToolResult(success=True, data=info)


store_info_tool = SupermarketTool(
    name="get_store_info",
    description=(
        "Retrieve store operating hours, specific department hours (bakery, pharmacy, deli), "
        "street address, contact phone, parking availability, and store policies (returns, refunds, pets, payments). "
        "Use whenever a shopper asks when the store closes/opens, where to park, or what the return policy is."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "description": "Topic of inquiry: 'hours', 'bakery_hours', 'pharmacy_hours', 'parking', 'returns', 'policies', or 'general'.",
            },
            "store_id": {
                "type": "string",
                "description": "Store branch identifier, defaults to 'STORE-001'.",
                "default": "STORE-001",
            },
        },
        "required": ["query_type"],
    },
    func=get_store_info,
)

