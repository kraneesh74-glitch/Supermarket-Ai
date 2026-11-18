"""Unit tests for QueryPlanner (📘 Lesson 5: Plan Before It Acts)."""

from apps.agent.planner import QueryPlanner


def test_single_intent_planning():
    query = "Are avocados in stock?"
    plan = QueryPlanner.create_plan(query)

    assert plan.original_query == query
    assert len(plan.sub_tasks) >= 1
    assert "avocado" in plan.sub_tasks[0].description
    assert plan.sub_tasks[0].tool_hint == "check_inventory_and_price"


def test_compound_multi_step_planning():
    query = "Do you have sourdough bread, what time does the bakery close, and are there any chips deals?"
    plan = QueryPlanner.create_plan(query)

    assert plan.is_compound is True
    assert len(plan.sub_tasks) >= 3

    descriptions = [t.description for t in plan.sub_tasks]
    assert any("bread" in d for d in descriptions)
    assert any("bakery" in d or "operating hours" in d for d in descriptions)
    assert any("promotions" in d or "chips" in d for d in descriptions)

    # Test checklist progression
    checklist_initial = plan.render_checklist()
    assert "[ ] Step 1:" in checklist_initial

    task1 = plan.get_next_pending_task()
    assert task1 is not None
    assert task1.id == 1

    plan.mark_task_completed(1, "Bread in stock at $4.29")
    checklist_updated = plan.render_checklist()
    assert "[x] Step 1:" in checklist_updated
    assert "Done (Bread in stock at $4.29)" in checklist_updated

