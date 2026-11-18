"""Tool 1: Real-Time Supermarket Inventory & Price Checker (📘 Lesson 2)."""

from typing import Optional
from data.mock_database import db
from packages.tools.base import SupermarketTool, ToolResult


def check_inventory_and_price(product_query: str, store_id: str = "STORE-001") -> ToolResult:
    """Check live shelf inventory, aisle location, stock quantity, and current price for an item."""
    if not product_query or not product_query.strip():
        return ToolResult(
            success=False,
            error="Product query cannot be empty.",
            recovery_suggestion="Provide the item name (e.g., 'avocados', 'almond milk', 'sourdough bread').",
        )

    results = db.search_products(product_query, store_id=store_id)

    if not results:
        # Self-healing hint: Suggest available categories or top in-stock products
        sample_items = [p["name"] for p in db.products[:4]]
        return ToolResult(
            success=False,
            error=f"No products found matching '{product_query}' at {store_id}.",
            recovery_suggestion=f"Check spelling or try broader terms. Available in-store samples: {sample_items}",
        )

    top_item = results[0]
    data = {
        "sku": top_item["sku"],
        "name": top_item["name"],
        "brand": top_item["brand"],
        "category": top_item["category"],
        "in_stock": top_item["in_stock"],
        "stock_quantity": top_item["stock_quantity"],
        "price": f"{top_item['currency']}{top_item['price']:.2f}",
        "unit": top_item["unit"],
        "location": top_item["location"],
        "other_matches_count": len(results) - 1,
    }

    if not top_item["in_stock"]:
        data["out_of_stock_note"] = "This specific item is currently out of stock."
        # Find in-stock substitute in the same category
        substitutes = [
            p["name"]
            for p in db.products
            if p["category"] == top_item["category"] and p["in_stock"] and p["sku"] != top_item["sku"]
        ]
        if substitutes:
            data["recommended_alternatives"] = substitutes

    return ToolResult(success=True, data=data)


inventory_tool = SupermarketTool(
    name="check_inventory_and_price",
    description=(
        "Search live supermarket inventory to check if an item is in stock, its current retail price, "
        "exact aisle/shelf location, and remaining units. Use whenever a customer asks about product availability, "
        "cost, brand, or where an item is located in the store."
    ),
    parameters={
        "type": "object",
        "properties": {
            "product_query": {
                "type": "string",
                "description": "Name, keyword, or brand of the grocery item (e.g., 'almond milk', 'avocado', 'sourdough').",
            },
            "store_id": {
                "type": "string",
                "description": "Store branch identifier, defaults to 'STORE-001' (Downtown Flagship).",
                "default": "STORE-001",
            },
        },
        "required": ["product_query"],
    },
    func=check_inventory_and_price,
)

