"""Unit tests for FakeLLM deterministic test harness (📘 Lesson 8)."""

import pytest
from tests.fake_llm import FakeLLM, PatternRuleFakeLLM, AgentThought


def test_fake_llm_canned_sequence():
    thoughts = [
        AgentThought(
            thought="Step 1: Check inventory for milk",
            action_type="tool_call",
            tool_name="check_inventory_and_price",
            tool_args={"product_query": "milk", "store_id": "STORE-001"},
        ),
        AgentThought(
            thought="Step 2: Inventory confirmed. Reply to user.",
            action_type="final_answer",
            response_text="Whole milk is available in Aisle 1 for $2.49.",
        ),
    ]

    llm = FakeLLM(canned_responses=thoughts)

    # First turn
    step1 = llm.generate([{"role": "user", "content": "Do you have milk?"}])
    assert step1.action_type == "tool_call"
    assert step1.tool_name == "check_inventory_and_price"
    assert step1.tool_args["product_query"] == "milk"

    # Second turn
    step2 = llm.generate([
        {"role": "user", "content": "Do you have milk?"},
        {"role": "tool", "content": "In stock: 42 units at $2.49, Aisle 1"},
    ])
    assert step2.action_type == "final_answer"
    assert "Whole milk is available" in step2.response_text
    assert len(llm.call_history) == 2


def test_pattern_rule_fake_llm_tool_dispatch():
    llm = PatternRuleFakeLLM()

    # Avocado stock query
    resp = llm.generate([{"role": "user", "content": "Are avocados in stock right now?"}])
    assert resp.action_type == "tool_call"
    assert resp.tool_name == "check_inventory_and_price"
    assert resp.tool_args["product_query"] == "avocado"

    # Store hours query
    resp_hours = llm.generate([{"role": "user", "content": "What time does the store close tonight?"}])
    assert resp_hours.action_type == "tool_call"
    assert resp_hours.tool_name == "get_store_info"

    # Order tracking query
    resp_order = llm.generate([{"role": "user", "content": "Where is my order ORD-9481?"}])
    assert resp_order.action_type == "tool_call"
    assert resp_order.tool_name == "track_order_status"

    # Sensitive action ("Asks you first")
    resp_cancel = llm.generate([{"role": "user", "content": "Cancel my order and give me a refund"}])
    assert resp_cancel.action_type == "ask_user"
    assert "Are you sure you want to proceed?" in resp_cancel.response_text

