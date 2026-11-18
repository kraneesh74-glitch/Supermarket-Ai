"""Unit tests for Memory Systems & Context Persistence (📘 Lesson 4)."""

import pytest
from apps.agent.memory import MemoryManager, SessionMemory, CustomerProfile
from apps.agent.react_loop import ReActAgent
from tests.fake_llm import PatternRuleFakeLLM, FakeLLM, AgentThought


def test_short_term_session_memory_sliding_window():
    session = SessionMemory(max_turns=3)  # Max 3 turns (6 messages)

    # Add 4 turns (8 messages)
    for i in range(1, 5):
        session.add_message("user", f"Question {i}")
        session.add_message("assistant", f"Answer {i}")

    history = session.get_history_for_llm()
    # Should only retain the last 3 turns (6 messages: Question 2-4)
    assert len(history) == 6
    assert history[0]["content"] == "Question 2"
    assert history[-1]["content"] == "Answer 4"


def test_long_term_customer_profile_rendering():
    profile = CustomerProfile(
        phone="+15551234567",
        name="Sarah Miller",
        preferred_store_id="STORE-001",
        dietary_preferences=["Organic", "Gluten-Free"],
        recent_inquiries=["almond milk"],
        last_order_id="ORD-9481",
        loyalty_tier="Gold",
        loyalty_points=850,
    )

    prompt = profile.render_context_prompt()
    assert "Sarah Miller (+15551234567)" in prompt
    assert "Preferred Store: STORE-001" in prompt
    assert "Organic, Gluten-Free" in prompt
    assert "almond milk" in prompt
    assert "ORD-9481" in prompt
    assert "Gold (850 pts)" in prompt


def test_memory_manager_preference_extraction():
    mgr = MemoryManager()
    phone = "+15559998877"

    # Turn with dietary keyword "vegan" and "organic"
    profile = mgr.update_customer_memory(
        phone=phone,
        query="Do you have any vegan and organic butter in stock?",
    )

    assert "Dairy-Free / Vegan" in profile.dietary_preferences
    assert "Organic" in profile.dietary_preferences

    # Retrieve in another call
    retrieved = mgr.get_customer_profile(phone)
    assert "Dairy-Free / Vegan" in retrieved.dietary_preferences


def test_cross_session_memory_persistence():
    """Verify memory persists across two separate sessions for the same customer (📘 L4)."""
    mgr = MemoryManager()
    phone = "+15551234567"  # Sarah Miller from seeded mock DB

    # Session 1: Sarah asks about a new item and gluten-free options
    session_1_id = "session_whatsapp_day_1"
    mgr.update_customer_memory(
        phone=phone,
        query="I have celiac disease so I need gluten-free bread options",
        inquired_product="gluten-free bread",
    )

    # Session 2: Days later, Sarah starts a completely new session
    session_2_id = "session_whatsapp_day_5"
    scratchpad = mgr.build_context_scratchpad(session_2_id, phone=phone)

    # System context prompt must contain Sarah's persistent preferences
    assert len(scratchpad) >= 1
    system_msg = scratchpad[0]
    assert system_msg["role"] == "system"
    assert "Sarah Miller" in system_msg["content"]
    assert "Gluten-Free" in system_msg["content"]
    assert "gluten-free bread" in system_msg["content"]


def test_react_agent_with_memory_integration():
    """Verify ReAct agent uses memory and updates session/profile seamlessly."""
    llm = PatternRuleFakeLLM()
    agent = ReActAgent(llm=llm, max_steps=5)

    session_id = "test_agent_session_101"
    phone = "+15551234567"

    # Turn 1
    res1 = agent.execute(
        query="Are avocados in stock?",
        session_id=session_id,
        customer_phone=phone,
    )
    assert res1.contained is True
    assert "Based on our store records" in res1.final_response

    # Verify session memory now holds Turn 1
    from apps.agent.memory import memory_manager
    session = memory_manager.get_session(session_id)
    history = session.get_history_for_llm()
    assert len(history) == 2
    assert history[0]["content"] == "Are avocados in stock?"
    assert "Based on our store records" in history[1]["content"]

