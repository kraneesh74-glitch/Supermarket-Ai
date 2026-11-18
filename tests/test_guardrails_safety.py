"""Unit tests for Phase 3: Safety Guardrails, Human Confirmation & Escalation (📘 Lesson 7)."""

import pytest
from apps.agent.react_loop import ReActAgent
from apps.agent.guardrails import GuardrailEngine
from apps.agent.audit_logger import audit_logger, AuditLogger
from tests.fake_llm import PatternRuleFakeLLM, FakeLLM, AgentThought


@pytest.fixture(autouse=True)
def clean_audit_logs():
    audit_logger.clear()
    yield
    audit_logger.clear()


def test_asks_you_first_multi_turn_confirmation():
    """Verify 2-turn confirmation protocol: Asks first, then confirms or aborts (📘 L7)."""
    llm = PatternRuleFakeLLM()
    agent = ReActAgent(llm=llm, max_steps=5)
    session_id = "sess_confirm_test"

    # Turn 1: Shopper requests sensitive action
    res1 = agent.execute("Please cancel my order and give me a refund", session_id=session_id)
    assert res1.needs_user_confirmation is True
    assert "Are you sure you want to proceed?" in res1.final_response
    assert session_id in agent.pending_confirmations

    # Turn 2: Shopper confirms with 'yes'
    res2 = agent.execute("Yes, please proceed", session_id=session_id)
    assert res2.needs_user_confirmation is False
    assert "Confirmed" in res2.final_response
    assert session_id not in agent.pending_confirmations


def test_asks_you_first_aborted_flow():
    """Verify shopper can decline the action and it aborts gracefully (📘 L7)."""
    llm = PatternRuleFakeLLM()
    agent = ReActAgent(llm=llm, max_steps=5)
    session_id = "sess_abort_test"

    # Turn 1: Sensitive request
    res1 = agent.execute("Cancel my order ORD-9481", session_id=session_id)
    assert res1.needs_user_confirmation is True

    # Turn 2: Shopper says 'no'
    res2 = agent.execute("No, actually keep my order", session_id=session_id)
    assert "Action cancelled" in res2.final_response
    assert session_id not in agent.pending_confirmations


def test_non_goal_payment_and_cash_refund_refusal():
    """Verify PRD v1 non-goals are blocked: payments/refunds in chat are redirected to desk."""
    llm = PatternRuleFakeLLM()
    agent = ReActAgent(llm=llm, max_steps=5)

    res = agent.execute("Can you take payment with my credit card number 4111222233334444?")
    assert res.contained is True
    assert res.escalated is False
    assert "cannot process payments" in res.final_response
    assert "Customer Service Desk" in res.final_response

    # Cash refund refusal
    res_refund = agent.execute("Give me a cash refund to card right now")
    assert "cannot process payments or issue cash refunds" in res_refund.final_response
    assert "Customer Service Desk" in res_refund.final_response


def test_explicit_human_escalation_ticket():
    """Verify explicit request for human creates a 100% contextual handoff ticket."""
    llm = PatternRuleFakeLLM()
    agent = ReActAgent(llm=llm, max_steps=5)

    res = agent.execute(
        query="I want to speak with a human store manager please",
        session_id="sess_human_req",
        customer_phone="+15551234567",
    )
    assert res.escalated is True
    assert res.contained is False
    assert "ticket #" in res.final_response.lower()
    assert res.handoff_ticket is not None
    assert res.handoff_ticket.customer_phone == "+15551234567"
    assert "Explicit human escalation requested" in res.escalation_reason


def test_frustration_sentiment_escalation():
    """Verify negative sentiment triggers automatic escalation to store staff."""
    llm = PatternRuleFakeLLM()
    agent = ReActAgent(llm=llm, max_steps=5)

    res = agent.execute(
        query="This is terrible service and an absolute rip off!",
        session_id="sess_angry_shopper",
    )
    assert res.escalated is True
    assert "Ticket #" in res.final_response
    assert "Customer frustration trigger" in res.escalation_reason


def test_consecutive_tool_failures_escalation():
    """Verify 2 consecutive tool errors automatically trigger staff escalation (📘 L7)."""
    # LLM that calls invalid tools repeatedly
    bad_tool_thought = AgentThought(
        thought="Calling non-existent tool",
        action_type="tool_call",
        tool_name="non_existent_tool",
        tool_args={},
    )
    llm = FakeLLM(canned_responses=[bad_tool_thought] * 5)
    agent = ReActAgent(llm=llm, max_steps=5)

    res = agent.execute("Find broken thing", session_id="sess_fail_test")
    assert res.escalated is True
    assert res.contained is False
    assert "Repeated tool failures" in res.escalation_reason
    assert "Ticket #" in res.final_response


def test_audit_logger_records_all_turns():
    """Verify every turn generates an append-only audit trail entry (📘 L7)."""
    llm = PatternRuleFakeLLM()
    agent = ReActAgent(llm=llm, max_steps=5)

    # Execute 3 distinct turns
    agent.execute("Are avocados in stock?", session_id="aud_1")
    agent.execute("What are the store hours?", session_id="aud_2")
    agent.execute("Speak to human staff", session_id="aud_3")

    entries = audit_logger.get_recent_entries()
    assert len(entries) == 3

    # Check metrics
    metrics = audit_logger.get_metrics_summary()
    assert metrics["total_queries"] == 3
    assert metrics["contained_count"] == 2
    assert metrics["escalated_count"] == 1
    assert metrics["containment_rate"] == 0.667
