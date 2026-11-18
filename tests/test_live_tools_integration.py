"""Tier 2: Live Tool Integration Tests (📘 Lesson 8).

Directly validates all 4 live tools against the seeded supermarket database:
- `check_inventory_and_price`
- `get_store_info`
- `track_order_status`
- `get_active_promotions`
"""

import pytest
from packages.tools.inventory_tool import check_inventory_and_price
from packages.tools.store_info_tool import get_store_info
from packages.tools.order_tool import track_order_status
from packages.tools.promo_tool import get_active_promotions
from data.mock_database import db


def test_inventory_tool_all_seeded_products():
    """Verify live inventory lookup accurately matches every item in products.json."""
    for product in db.products:
        res = check_inventory_and_price(product["name"], store_id="STORE-001")
        assert res.success is True
        data = res.data
        assert data["sku"] == product["sku"]
        assert data["price"] == f"${product['price']:.2f}"
        assert data["in_stock"] == product["in_stock"]
        assert data["stock_quantity"] == product["stock_quantity"]


def test_inventory_substitute_recommendations():
    """Verify out-of-stock items recommend in-stock substitutes within the same category."""
    # Gluten-free bread is out of stock in Bakery
    res = check_inventory_and_price("gluten-free bread")
    assert res.success is True
    assert res.data["in_stock"] is False
    assert "recommended_alternatives" in res.data
    assert "Artisan Sourdough Loaf 500g" in res.data["recommended_alternatives"]


def test_store_info_all_branches():
    """Verify both Downtown Flagship (STORE-001) and Westside (STORE-002) return valid data."""
    res1 = get_store_info("hours", store_id="STORE-001")
    assert res1.success is True
    assert "SuperMart Downtown Flagship" in res1.data["store_name"]

    res2 = get_store_info("hours", store_id="STORE-002")
    assert res2.success is True
    assert "SuperMart Westside Suburban" in res2.data["store_name"]


def test_order_tracker_status_and_items():
    """Verify order tracking returns complete breakdown of order items and bay assignment."""
    res = track_order_status("ORD-9481", phone_number="+15551234567")
    assert res.success is True
    assert res.data["status"] == "Ready for Pickup"
    assert res.data["pickup_bay"] == "Bay 2"
    assert res.data["items_count"] == 3
    assert any("Whole Milk" in it for it in res.data["items_summary"])


def test_promotions_filtering_and_deals():
    """Verify promo tool retrieves and filters circulars correctly."""
    # Specific category
    res_dairy = get_active_promotions("Dairy Alternatives")
    assert res_dairy.success is True
    assert any("Almond Milk" in p["title"] or "Almond Milk" in p["description"] for p in res_dairy.data["promotions"])

    # General all promotions
    res_all = get_active_promotions(None)
    assert res_all.success is True
    assert res_all.data["matched_deals_count"] == len(db.promos)

