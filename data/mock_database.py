"""Mock Supermarket Database and Store Services.

Provides in-memory simulated database with live lookup methods for:
- Product inventory, pricing, shelf locations, and stock levels
- Store master details (hours, amenities, policies, department timings)
- Order status & tracking (Click & Collect, Delivery)
- Active circulars, bundle discounts, and member promotions
- Long-term customer profiles and loyalty rewards
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path(__file__).resolve().parent


class SupermarketDatabase:
    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or DATA_DIR
        self._load_all()

    def _load_all(self) -> None:
        with open(self.data_dir / "products.json", "r", encoding="utf-8") as f:
            self.products: List[Dict[str, Any]] = json.load(f)

        with open(self.data_dir / "stores.json", "r", encoding="utf-8") as f:
            self.stores: List[Dict[str, Any]] = json.load(f)

        with open(self.data_dir / "promos.json", "r", encoding="utf-8") as f:
            self.promos: List[Dict[str, Any]] = json.load(f)

        with open(self.data_dir / "orders.json", "r", encoding="utf-8") as f:
            self.orders: List[Dict[str, Any]] = json.load(f)

        with open(self.data_dir / "customers.json", "r", encoding="utf-8") as f:
            self.customers: List[Dict[str, Any]] = json.load(f)

    # 1. Product & Inventory Search
    def search_products(
        self, query: str, store_id: str = "STORE-001"
    ) -> List[Dict[str, Any]]:
        """Search products by keyword, category, or name with token-overlap ranking."""
        if not query or not query.strip():
            return []

        q = query.strip().lower()
        query_tokens = set(q.split())
        scored_matches = []
        stop_words = {"fresh", "organic", "any", "some", "pack", "bag", "item", "good", "the", "a", "an", "do", "you", "have", "got"}
        substantive_tokens = {t for t in query_tokens if t not in stop_words}

        for p in self.products:
            searchable_text = (
                f"{p['name']} {p['brand']} {p['category']} "
                + " ".join(p.get("keywords", []))
            ).lower()

            # Exact phrase match gets highest score
            score = 0
            if q in searchable_text:
                score += 15

            matched_tokens = sum(1 for token in query_tokens if token in searchable_text)
            # If substantive tokens exist, require at least one substantive token to match
            if substantive_tokens:
                substantive_matched = sum(1 for token in substantive_tokens if token in searchable_text)
                if substantive_matched == 0 and q not in searchable_text:
                    continue
                score += substantive_matched * 5

            if matched_tokens > 0:
                score += matched_tokens * 2
                scored_matches.append((score, p))

        # Sort descending by score
        scored_matches.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored_matches]

    def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        for p in self.products:
            if p["sku"].upper() == sku.strip().upper():
                return p
        return None

    # 2. Store Master Info & Policies
    def get_store(self, store_id: str = "STORE-001") -> Optional[Dict[str, Any]]:
        for s in self.stores:
            if s["store_id"].upper() == store_id.strip().upper():
                return s
        return self.stores[0] if self.stores else None

    def query_store_info(
        self, query_type: str, store_id: str = "STORE-001"
    ) -> Dict[str, Any]:
        """Query specific store aspect: hours, bakery, pharmacy, parking, returns, etc."""
        store = self.get_store(store_id)
        if not store:
            return {"error": f"Store with ID '{store_id}' not found."}

        qt = query_type.strip().lower()
        if any(h in qt for h in ["hour", "time", "closing", "opening", "open"]):
            return {
                "store_name": store["name"],
                "operating_hours": store["operating_hours"],
                "department_hours": store.get("departments", {}),
            }
        elif any(p in qt for p in ["return", "refund", "exchange", "policy"]):
            return {
                "store_name": store["name"],
                "return_policy": store["policies"]["returns"],
                "pet_policy": store["policies"].get("pets"),
                "accepted_payments": store["policies"].get("accepted_payments"),
            }
        elif any(a in qt for a in ["park", "parking", "garage", "amenity", "kiosk", "wheelchair"]):
            return {
                "store_name": store["name"],
                "address": store["address"],
                "amenities": store["amenities"],
            }
        else:
            return {
                "store_name": store["name"],
                "address": store["address"],
                "phone": store["phone"],
                "operating_hours": store["operating_hours"],
                "departments": store["departments"],
                "amenities": store["amenities"],
                "policies": store["policies"],
            }

    # 3. Promotions & Offers
    def get_active_promotions(
        self, category_or_item: Optional[str] = None, store_id: str = "STORE-001"
    ) -> List[Dict[str, Any]]:
        """Retrieve promotions, optionally filtered by keyword or category."""
        if not category_or_item:
            return self.promos

        target = category_or_item.strip().lower()
        results = []
        for promo in self.promos:
            text = f"{promo['title']} {promo['description']} {promo['category']}".lower()
            if target in text:
                results.append(promo)
        return results if results else self.promos

    # 4. Order Tracking
    def track_order(
        self, order_id: str, phone_number: Optional[str] = None
    ) -> Dict[str, Any]:
        """Track customer order with optional phone authentication."""
        clean_id = order_id.strip().upper()
        for order in self.orders:
            if order["order_id"].upper() == clean_id:
                # If phone is supplied, verify matching
                if phone_number:
                    norm_input_phone = "".join(filter(str.isdigit, phone_number))
                    norm_order_phone = "".join(filter(str.isdigit, order["customer_phone"]))
                    if norm_input_phone and norm_input_phone != norm_order_phone:
                        return {
                            "error": "Phone number does not match the order records. Verification failed."
                        }
                return {
                    "order_id": order["order_id"],
                    "customer_name": order["customer_name"],
                    "status": order["status"],
                    "type": order["type"],
                    "estimated_ready": order.get("estimated_ready") or order.get("estimated_delivery"),
                    "pickup_bay": order.get("pickup_bay"),
                    "driver_name": order.get("driver_name"),
                    "items_count": len(order["items"]),
                    "items_summary": [f"{it['name']} x{it['quantity']}" for it in order["items"]],
                    "total_amount": order["total_amount"],
                    "payment_status": order["payment_status"],
                }
        return {"error": f"Order '{order_id}' not found. Please verify the order number."}

    # 5. Customer Profile & Persistent Long-Term Memory
    def get_customer_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        clean_input = "".join(filter(str.isdigit, phone))
        for cust in self.customers:
            if "".join(filter(str.isdigit, cust["phone"])) == clean_input:
                return cust
        return None

    def save_customer_memory(
        self, phone: str, key: str, value: Any
    ) -> Dict[str, Any]:
        cust = self.get_customer_by_phone(phone)
        if not cust:
            # Create a new lightweight profile
            cust = {
                "customer_id": f"CUST-{len(self.customers) + 101}",
                "name": "Shopper",
                "phone": phone,
                "loyalty_tier": "Bronze",
                "loyalty_points": 0,
                "preferred_store_id": "STORE-001",
                "dietary_preferences": [],
                "recent_orders": [],
            }
            self.customers.append(cust)

        if isinstance(value, list):
            cust[key] = list(value)
        elif key in cust and isinstance(cust[key], list):
            if value not in cust[key]:
                cust[key].append(value)
        else:
            cust[key] = value

        return cust


# Global singleton instance for app-wide access
db = SupermarketDatabase()
