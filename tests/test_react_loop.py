"""Unit tests for ReAct Loop Engine: Think → Act → Look (📘 Lessons 1, 3, 5, 7)."""

import pytest
from apps.agent.react_loop import ReActAgent
from tests.fake_llm import FakeLLM, PatternRuleFakeLLM, AgentThought


def test_react_loop_successful_resolution():
    """Verify Think -> Act -> Look -> Think -> Final Answer flow."""
    llm = PatternRuleFakeLLM()
    agent = ReActAgent(llm=llm, max_steps=5)

    result = agent.execute("Are avocados in stock right now?")

    assert result.contained is True
    assert result.escalated is False
    assert result.total_steps == 2  # Step 1: Tool Call, Step 2: Final Answer
    assert len(result.steps) == 2

    # Step 1: Think & Act (Tool Call)
    s1 = result.steps[0]
    assert s1.action_type == "tool_call"
    assert s1.tool_name == "check_inventory_and_price"
    assert "Observation [SUCCESS]" in s1.observation
    assert "Produce Island 2" in s1.observation

    # Step 2: Think & Act (Final Answer)
    s2 = result.steps[1]
    assert s2.action_type == "final_answer"
    assert "Based on our store records" in result.final_response


def test_react_loop_tool_error_self_healing():
    """Verify tool error observation feeds back into Think step for recovery (📘 L2)."""
    # Program a canned sequence:
    # 1. Calls tool with missing item
    # 2. Observes error hint, then calls store info
    # 3. Emits final answer
    canned = [
        AgentThought(
            thought="Step 1: Check inventory for exotic item",
            action_type="tool_call",
            tool_name="check_inventory_and_price",
            tool_args={"product_query": "dragonfruit xyz"},
        ),
        AgentThought(
            thought="Step 2: Tool returned error with suggestions. Re-evaluating with store info.",
            action_type="tool_call",
            tool_name="get_store_info",
            tool_args={"query_type": "hours", "store_id": "STORE-001"},
        ),
        AgentThought(
            thought="Step 3: All necessary info collected. Formulate shopper response.",
            action_type="final_answer",
            response_text="We don't currently stock dragonfruit, but our produce section is open until 10 PM.",
        ),
    ]

    llm = FakeLLM(canned_responses=canned)
    agent = ReActAgent(llm=llm, max_steps=5)

    result = agent.execute("Do you have dragonfruit and when do you close?")

    assert result.contained is True
    assert result.total_steps == 3
    # Step 1 observed the error & self-healing hint
    assert "Observation [ERROR]" in result.steps[0].observation
    assert "Self-Correction Hint" in result.steps[0].observation
    # Step 2 succeeded
    assert "Observation [SUCCESS]" in result.steps[1].observation
    # Final answer delivered
    assert "We don't currently stock dragonfruit" in result.final_response


def test_react_loop_asks_you_first_safety_gate():
    """Verify sensitive actions pause and require shopper confirmation (📘 L7)."""
    llm = PatternRuleFakeLLM()
    agent = ReActAgent(llm=llm, max_steps=5)

    result = agent.execute("Please cancel my order and issue a refund")

    assert result.needs_user_confirmation is True
    assert result.total_steps == 1
    assert "Are you sure you want to proceed?" in result.final_response
    assert result.steps[0].action_type == "ask_user"


def test_react_loop_step_limit_escalation():
    """Verify runaway loops are cut off at max_steps and escalated to staff (📘 L7)."""
    # An LLM that constantly calls the same tool without reaching resolution
    looping_thought = AgentThought(
        thought="I am stuck in an endless loop",
        action_type="tool_call",
        tool_name="get_store_info",
        tool_args={"query_type": "hours"},
    )
    llm = FakeLLM(canned_responses=[looping_thought] * 10)
    agent = ReActAgent(llm=llm, max_steps=3)  # Hard cap at 3

    result = agent.execute("Infinite loop test")

    assert result.contained is False
    assert result.escalated is True
    assert result.total_steps == 3
    assert "step limit" in result.escalation_reason
    assert "in-store customer service team" in result.final_response

