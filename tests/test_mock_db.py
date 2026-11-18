"""Unit tests for Mock Supermarket Database & Service Lookups."""

import pytest
from data.mock_database import SupermarketDatabase


@pytest.fixture
def db():
    return SupermarketDatabase()


def test_search_products_exact_and_fuzzy(db):
    # Search by keyword
    results = db.search_products("milk")
    assert len(results) >= 2
    names = [r["name"] for r in results]
    assert any("Whole Milk" in n for n in names)
    assert any("Almond Milk" in n for n in names)

    # Search for specific item
    avocado = db.search_products("avocado")
    assert len(avocado) == 1
    assert avocado[0]["sku"] == "PROD-001"
    assert avocado[0]["price"] == 2.99
    assert avocado[0]["in_stock"] is True
    assert "Produce Island 2" in avocado[0]["location"]["aisle"]


def test_out_of_stock_item(db):
    bread = db.search_products("gluten-free bread")
    assert len(bread) >= 1
    # Top match must be the gluten-free bread which is out of stock
    top_match = bread[0]
    assert top_match["sku"] == "BAK-002"
    assert top_match["in_stock"] is False
    assert top_match["stock_quantity"] == 0


def test_query_store_info(db):
    # Query operating hours
    hours = db.query_store_info("opening hours", store_id="STORE-001")
    assert "operating_hours" in hours
    assert "monday" in hours["operating_hours"]
    assert hours["operating_hours"]["monday"] == "07:00 - 22:00"

    # Query returns policy
    returns = db.query_store_info("return policy", store_id="STORE-001")
    assert "return_policy" in returns
    assert "14 days" in returns["return_policy"]


def test_track_order_success(db):
    order = db.track_order("ORD-9481", phone_number="+15551234567")
    assert "error" not in order
    assert order["order_id"] == "ORD-9481"
    assert order["status"] == "Ready for Pickup"
    assert order["pickup_bay"] == "Bay 2"


def test_track_order_mismatched_phone(db):
    order = db.track_order("ORD-9481", phone_number="+19999999999")
    assert "error" in order
    assert "Verification failed" in order["error"]


def test_get_promotions(db):
    promos = db.get_active_promotions("Dairy Alternatives")
    assert len(promos) >= 1
    assert any("Almond Milk" in p["description"] for p in promos)


def test_customer_persistent_memory(db):
    # Lookup customer
    cust = db.get_customer_by_phone("+15551234567")
    assert cust is not None
    assert cust["name"] == "Sarah Miller"

    # Update customer memory preference
    updated = db.save_customer_memory("+15551234567", "dietary_preferences", "Nut-Free")
    assert "Nut-Free" in updated["dietary_preferences"]
