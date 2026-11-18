"""Fake LLM Test Harness (📘 Lesson 8: Tiered Testing Strategy).

Enables deterministic, fast, offline unit testing of:
- The Think -> Act -> Look execution loop (L1, L3)
- Plan-before-act decomposition (L5)
- Tool calling dispatch & parameter serialization (L2)
- Tool error recovery & self-correction (L2)
- "Asks you first" confirmation gates (L7)
- Step limit recursion cutoff (L7)
"""

import re
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentThought(BaseModel):
    plan: Optional[str] = None
    thought: str
    action_type: str = "tool_call"  # "tool_call", "ask_user", "final_answer"
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    response_text: Optional[str] = None


class FakeLLM:
    """Deterministic Mock LLM for offline testing without API keys or flakiness."""

    def __init__(
        self,
        canned_responses: Optional[List[AgentThought]] = None,
        rule_handler: Optional[Callable[[List[Dict[str, Any]]], AgentThought]] = None,
    ):
        self.canned_responses = canned_responses or []
        self.rule_handler = rule_handler
        self.call_history: List[List[Dict[str, Any]]] = []
        self.step_index = 0

    def generate(self, messages: List[Dict[str, Any]]) -> AgentThought:
        """Process messages and return the next programmed thought/action."""
        self.call_history.append(messages)

        # 1. Custom rule handler takes precedence if supplied
        if self.rule_handler:
            return self.rule_handler(messages)

        # 2. Sequential canned response list
        if self.step_index < len(self.canned_responses):
            resp = self.canned_responses[self.step_index]
            self.step_index += 1
            return resp

        # 3. Default fallback
        return AgentThought(
            thought="No more canned steps; providing default completion.",
            action_type="final_answer",
            response_text="I have answered all your questions.",
        )

    def reset(self) -> None:
        self.step_index = 0
        self.call_history.clear()


class PatternRuleFakeLLM(FakeLLM):
    """Rule-based fake LLM mimicking intelligent supermarket domain understanding."""

    def __init__(self):
        super().__init__()

    def generate(self, messages: List[Dict[str, Any]]) -> AgentThought:
        self.call_history.append(messages)
        last_msg = messages[-1]["content"] if messages else ""
        last_role = messages[-1].get("role", "user")
        lower = last_msg.lower()

        # Check if the last message was a tool observation
        if last_role == "tool" or "Observation:" in last_msg or "Tool Result:" in last_msg:
            return AgentThought(
                thought="I have received the tool output. Now synthesizing friendly answer.",
                action_type="final_answer",
                response_text=f"Based on our store records: {last_msg}",
            )

        # 1. Safety & Confirmation Gate ("Asks you first" - L7) takes priority
        # Only trigger ask_user when explicitly asking to cancel/delete/transfer an order or points
        if any(w in lower for w in ["cancel my order", "cancel order", "delete my order", "transfer my", "points to cash"]):
            return AgentThought(
                thought="Customer wants a sensitive action (cancellation/refund). Safety check needed.",
                action_type="ask_user",
                response_text="Cancelling an order is irreversible. Are you sure you want to proceed? (yes/no)",
            )

        # 2. Order Tracking
        if "order" in lower or "ord-" in lower or "delivery" in lower or "pickup bay" in lower:
            # Extract order ID if present (e.g. ORD-9481, ORD-9482, ORD-9483, or numeric 9481)
            oid_match = re.search(r"ord-\d{4}", lower)
            order_id = oid_match.group(0).upper() if oid_match else "ORD-9481"
            if not oid_match:
                num_match = re.search(r"\b\d{4}\b", lower)
                if num_match:
                    order_id = f"ORD-{num_match.group(0)}"

            phone = "+15551234567"
            if "9482" in order_id:
                phone = "+15559876543"
            elif "9483" in order_id:
                phone = "+15555551212"

            return AgentThought(
                thought="Customer wants to track their order status.",
                action_type="tool_call",
                tool_name="track_order_status",
                tool_args={"order_id": order_id, "phone_number": phone},
            )

        # 3. Product Inventory & Price Queries
        products_map = {
            "avocado": "avocado",
            "milk": "milk",
            "almond milk": "almond milk",
            "banana": "banana",
            "sourdough": "sourdough",
            "bread": "bread",
            "gluten-free": "gluten-free bread",
            "egg": "eggs",
            "chips": "chips",
            "water": "sparkling water",
            "juice": "orange juice",
            "oj": "orange juice",
        }
        for kw, prod_query in products_map.items():
            if kw in lower:
                return AgentThought(
                    thought=f"Customer is asking about product inventory and pricing for {prod_query}.",
                    action_type="tool_call",
                    tool_name="check_inventory_and_price",
                    tool_args={"product_query": prod_query, "store_id": "STORE-001"},
                )

        # 4. Store Information, Hours & Policies
        store_info_keywords = [
            "hour", "close", "closing", "open", "opening", "time", "timing",
            "bakery", "pharmacy", "deli", "park", "parking", "garage", "ev",
            "wheelchair", "amenity", "kiosk", "address", "phone", "return",
            "receipt", "policy", "pet", "dog", "apple pay", "google pay",
            "pay with", "card", "desk", "location"
        ]
        if any(k in lower for k in store_info_keywords):
            q_type = "general"
            if any(h in lower for h in ["hour", "close", "open", "time", "timing"]):
                q_type = "hours"
            elif any(r in lower for r in ["return", "receipt", "exchange"]):
                q_type = "returns"
            elif any(p in lower for p in ["park", "ev", "wheelchair"]):
                q_type = "parking"
            elif any(pol in lower for pol in ["pet", "dog", "apple pay", "card", "pay"]):
                q_type = "policies"

            return AgentThought(
                thought="Customer is asking for store information or policies.",
                action_type="tool_call",
                tool_name="get_store_info",
                tool_args={"query_type": q_type, "store_id": "STORE-001"},
            )

        # 5. Promotions & Deals
        if any(d in lower for d in ["offer", "deal", "promo", "sale", "discount", "circular"]):
            return AgentThought(
                thought="Customer wants to know active discounts and circular deals.",
                action_type="tool_call",
                tool_name="get_active_promotions",
                tool_args={"category_or_item": "Snacks", "store_id": "STORE-001"},
            )

        # 6. Default Fallback
        return AgentThought(
            thought="Routine greeting or general query.",
            action_type="final_answer",
            response_text="Hello! How can I help you find items, check prices, or track an order today?",
        )
