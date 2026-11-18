"""Plan Before It Acts Module (📘 Lesson 5: Planning).

Decomposes complex, multi-part shopper queries into an ordered checklist of sub-tasks
before triggering tools in the ReAct loop.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SubTask(BaseModel):
    id: int
    description: str
    tool_hint: Optional[str] = None
    completed: bool = False
    result: Optional[str] = None


class ExecutionPlan(BaseModel):
    original_query: str
    is_compound: bool = False
    sub_tasks: List[SubTask] = Field(default_factory=list)

    def get_next_pending_task(self) -> Optional[SubTask]:
        """Return the first uncompleted sub-task."""
        for t in self.sub_tasks:
            if not t.completed:
                return t
        return None

    def mark_task_completed(self, task_id: int, result: str) -> None:
        for t in self.sub_tasks:
            if t.id == task_id:
                t.completed = True
                t.result = result
                break

    def is_all_completed(self) -> bool:
        return all(t.completed for t in self.sub_tasks)

    def render_checklist(self) -> str:
        """Render the plan as a markdown checklist for LLM scratchpad context."""
        lines = [f"Plan Checklist for: \"{self.original_query}\""]
        for t in self.sub_tasks:
            status = "[x]" if t.completed else "[ ]"
            line = f"{status} Step {t.id}: {t.description}"
            if t.completed and t.result:
                line += f" -> Done ({t.result})"
            lines.append(line)
        return "\n".join(lines)


class QueryPlanner:
    """Heuristic and LLM-assisted planner that decomposes compound queries into sub-tasks."""

    @staticmethod
    def create_plan(query: str) -> ExecutionPlan:
        q_lower = query.lower()

        # Identify distinct question topics
        topics = []

        # 1. Product & stock topics
        detected_products = []
        if "avocado" in q_lower:
            detected_products.append("avocado")
        if "milk" in q_lower or "almond milk" in q_lower:
            detected_products.append("milk")
        if "bread" in q_lower or "sourdough" in q_lower:
            detected_products.append("bread")
        if "egg" in q_lower:
            detected_products.append("eggs")
        if "chips" in q_lower:
            detected_products.append("chips")

        for prod in detected_products:
            topics.append({
                "description": f"Check inventory and price for '{prod}'",
                "tool_hint": "check_inventory_and_price",
            })

        # 2. Store info topics
        if any(h in q_lower for h in ["hour", "close", "closing", "open", "time"]):
            dept = "general"
            if "bakery" in q_lower:
                dept = "bakery"
            elif "pharmacy" in q_lower:
                dept = "pharmacy"
            topics.append({
                "description": f"Retrieve store and {dept} operating hours",
                "tool_hint": "get_store_info",
            })

        if any(p in q_lower for p in ["return", "refund", "exchange", "policy"]):
            topics.append({
                "description": "Look up store return and refund policies",
                "tool_hint": "get_store_info",
            })

        # 3. Promotions & deals
        if any(d in q_lower for d in ["deal", "offer", "discount", "promo", "sale", "circular"]):
            topics.append({
                "description": "Check current weekly circular promotions and discounts",
                "tool_hint": "get_active_promotions",
            })

        # 4. Order tracking
        if any(o in q_lower for o in ["order", "delivery", "pickup", "ord-"]):
            topics.append({
                "description": "Track online or Click & Collect order status",
                "tool_hint": "track_order_status",
            })

        # If more than 1 topic or compound conjunctions detected
        is_compound = len(topics) > 1 or (" and " in q_lower and ("?" in q_lower or len(topics) >= 1))

        if not topics:
            # Single general turn
            topics.append({
                "description": f"Resolve customer inquiry: '{query}'",
                "tool_hint": None,
            })

        sub_tasks = [
            SubTask(
                id=idx + 1,
                description=top["description"],
                tool_hint=top["tool_hint"],
            )
            for idx, top in enumerate(topics)
        ]

        return ExecutionPlan(
            original_query=query,
            is_compound=is_compound,
            sub_tasks=sub_tasks,
        )

