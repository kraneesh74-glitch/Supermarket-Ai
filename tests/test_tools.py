"""Unit tests for the 4 Core Supermarket Tools & Self-Correction (📘 Lesson 2)."""

import pytest
from packages.tools.registry import CORE_TOOLS, execute_tool, get_tool_schemas


def test_core_tools_count_and_schemas():
    # Must have strictly 4 tools
    assert len(CORE_TOOLS) == 4
    assert set(CORE_TOOLS.keys()) == {
        "check_inventory_and_price",
        "get_store_info",
        "track_order_status",
        "get_active_promotions",
    }
    schemas = get_tool_schemas()
    assert len(schemas) == 4
    for s in schemas:
        assert "name" in s
        assert "description" in s
        assert "parameters" in s


def test_inventory_tool_in_stock():
    res = execute_tool("check_inventory_and_price", {"product_query": "avocado"})
    assert res.success is True
    assert res.data["sku"] == "PROD-001"
    assert res.data["in_stock"] is True
    assert res.data["price"] == "$2.99"
    assert "Produce Island 2" in res.data["location"]["aisle"]


def test_inventory_tool_out_of_stock_with_alternatives():
    res = execute_tool("check_inventory_and_price", {"product_query": "gluten-free bread"})
    assert res.success is True
    assert res.data["in_stock"] is False
    assert "out_of_stock_note" in res.data
    # Recommends in-stock substitute in Bakery
    assert "recommended_alternatives" in res.data
    assert any("Sourdough" in alt for alt in res.data["recommended_alternatives"])


def test_inventory_tool_missing_item_error_recovery():
    res = execute_tool("check_inventory_and_price", {"product_query": "dragonfruit xyz"})
    assert res.success is False
    assert "No products found" in res.error
    assert res.recovery_suggestion is not None
    assert "Available in-store samples" in res.recovery_suggestion


def test_store_info_tool():
    # Operating hours
    res_hours = execute_tool("get_store_info", {"query_type": "hours"})
    assert res_hours.success is True
    assert "07:00 - 22:00" in res_hours.data["operating_hours"]["monday"]

    # Returns policy
    res_policy = execute_tool("get_store_info", {"query_type": "returns"})
    assert res_policy.success is True
    assert "14 days" in res_policy.data["return_policy"]


def test_order_tracker_tool():
    # Clean lookup
    res = execute_tool("track_order_status", {"order_id": "ORD-9481", "phone_number": "+15551234567"})
    assert res.success is True
    assert res.data["status"] == "Ready for Pickup"
    assert res.data["pickup_bay"] == "Bay 2"

    # Numeric only order ID auto-normalization
    res_norm = execute_tool("track_order_status", {"order_id": "9481"})
    assert res_norm.success is True
    assert res_norm.data["order_id"] == "ORD-9481"

    # Wrong phone number error & hint
    res_err = execute_tool("track_order_status", {"order_id": "ORD-9481", "phone_number": "+19999999999"})
    assert res_err.success is False
    assert "Verification failed" in res_err.error
    assert res_err.recovery_suggestion is not None


def test_promo_tool():
    res = execute_tool("get_active_promotions", {"category_or_item": "Snacks"})
    assert res.success is True
    assert res.data["matched_deals_count"] >= 1
    assert any("Chips" in p["title"] or "Chips" in p["description"] for p in res.data["promotions"])


def test_unknown_tool_self_healing_error():
    res = execute_tool("cancel_order_and_refund", {"order_id": "123"})
    assert res.success is False
    assert "does not exist" in res.error
    assert "Please choose from one of the 4 supported tools" in res.recovery_suggestion

