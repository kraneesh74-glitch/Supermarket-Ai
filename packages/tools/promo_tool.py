"""Tool 4: Supermarket Promotions, Deals & Weekly Circulars (📘 Lesson 2)."""

from typing import Optional
from packages.tools.base import SupermarketTool, ToolResult
from data.mock_database import db


def get_active_promotions(
    category_or_item: Optional[str] = None, store_id: str = "STORE-001"
) -> ToolResult:
    """Retrieve active weekly circular deals, bundle discounts, and member offers."""
    promos = db.get_active_promotions(category_or_item=category_or_item, store_id=store_id)

    if not promos:
        return ToolResult(
            success=False,
            error=f"No active promotions found matching '{category_or_item}'.",
            recovery_suggestion="Retrieve general in-store circular deals without category filter.",
        )

    formatted = []
    for p in promos:
        formatted.append({
            "promo_id": p["promo_id"],
            "title": p["title"],
            "description": p["description"],
            "category": p["category"],
            "valid_dates": f"{p['start_date']} to {p['end_date']}",
            "member_only": p.get("member_only", False),
        })

    return ToolResult(
        success=True,
        data={
            "matched_deals_count": len(formatted),
            "promotions": formatted,
        },
    )


promo_tool = SupermarketTool(
    name="get_active_promotions",
    description=(
        "Search active supermarket promotional deals, weekly circulars, BOGO discounts, and loyalty member offers. "
        "Can be filtered by category (e.g. 'Dairy Alternatives', 'Snacks', 'Bakery') or item keyword. "
        "Use when a customer asks what is on sale, on offer, or about weekly circular deals."
    ),
    parameters={
        "type": "object",
        "properties": {
            "category_or_item": {
                "type": "string",
                "description": "Optional category or product to filter offers (e.g., 'Dairy', 'Snacks', 'Bakery').",
            },
            "store_id": {
                "type": "string",
                "description": "Store branch identifier, defaults to 'STORE-001'.",
                "default": "STORE-001",
            },
        },
        "required": [],
    },
    func=get_active_promotions,
)

