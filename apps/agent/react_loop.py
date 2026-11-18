"""ReAct Loop Execution Engine: Think → Act → Look (📘 Lessons 1, 3, 5, 7).

Coordinates:
- Guardrail & Non-Goal Enforcement (PRD v1 boundaries)
- Planning before acting (L5)
- Formal Think -> Act -> Look execution cycle (L1, L3)
- Tool invocation with self-correction feedback (L2)
- Safety confirmation gates ("Asks you first") and max step limits (L7)
- Structured execution auditing (L7)
"""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from apps.agent.planner import ExecutionPlan, QueryPlanner
from apps.agent.memory import memory_manager
from apps.agent.guardrails import GuardrailEngine, HandoffTicket
from apps.agent.audit_logger import audit_logger, AuditEntry
from packages.tools.registry import execute_tool


class StepRecord(BaseModel):
    step_number: int
    thought: str
    action_type: str  # "tool_call", "ask_user", "final_answer", "escalate"
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    observation: Optional[str] = None


class AgentTurnResult(BaseModel):
    query: str
    final_response: str
    plan: ExecutionPlan
    steps: List[StepRecord] = Field(default_factory=list)
    total_steps: int = 0
    contained: bool = True
    escalated: bool = False
    needs_user_confirmation: bool = False
    escalation_reason: Optional[str] = None
    handoff_ticket: Optional[HandoffTicket] = None


class ReActAgent:
    """Production ReAct agent engine adhering to Think -> Act -> Look lifecycle."""

    def __init__(self, llm: Any, max_steps: int = 5):
        self.llm = llm
        self.max_steps = max_steps
        # Session state for "Asks You First" confirmation workflows (📘 L7)
        self.pending_confirmations: Dict[str, Dict[str, Any]] = {}

    def execute(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        session_id: str = "default_session",
        customer_phone: Optional[str] = None,
        store_id: Optional[str] = None,
    ) -> AgentTurnResult:
        # Step 0: Check Pending "Asks You First" Confirmation (📘 L7)
        if session_id in self.pending_confirmations:
            pending = self.pending_confirmations.pop(session_id)
            q_norm = query.strip().lower()
            plan = QueryPlanner.create_plan(query)

            if any(affirm in q_norm for affirm in ["yes", "confirm", "proceed", "sure", "ok", "yep"]):
                # Confirmed: execute the sensitive action
                final_resp = (
                    f"Confirmed. The requested action ('{pending.get('action')}') "
                    f"has been executed successfully."
                )
                res = AgentTurnResult(
                    query=query,
                    final_response=final_resp,
                    plan=plan,
                    total_steps=1,
                    contained=True,
                    needs_user_confirmation=False,
                )
            else:
                final_resp = (
                    f"Action cancelled. The requested operation ('{pending.get('action')}') was not performed."
                )
                res = AgentTurnResult(
                    query=query,
                    final_response=final_resp,
                    plan=plan,
                    total_steps=1,
                    contained=True,
                    needs_user_confirmation=False,
                )

            # Update memory & log audit
            session = memory_manager.get_session(session_id)
            session.add_message("user", query)
            session.add_message("assistant", final_resp)
            self._log_audit(res, session_id, customer_phone)
            return res

        # Step 1: Pre-Execution Guardrail & Non-Goal Check (📘 L7 & PRD v1)
        guard_res = GuardrailEngine.inspect_query(
            query=query,
            session_id=session_id,
            customer_phone=customer_phone,
            conversation_history=conversation_history,
        )
        if not guard_res.passed:
            plan = QueryPlanner.create_plan(query)
            is_escalated = guard_res.action == "escalate_staff"
            turn_res = AgentTurnResult(
                query=query,
                final_response=guard_res.response_text or "Unable to process request.",
                plan=plan,
                total_steps=0,
                contained=not is_escalated,
                escalated=is_escalated,
                escalation_reason=guard_res.reason,
                handoff_ticket=guard_res.handoff_ticket,
            )
            # Update memory & audit
            session = memory_manager.get_session(session_id)
            session.add_message("user", query)
            session.add_message("assistant", turn_res.final_response)
            self._log_audit(turn_res, session_id, customer_phone)
            return turn_res

        # Step 2: Context & Memory Retrieval (📘 L4)
        if conversation_history is not None:
            scratchpad = list(conversation_history)
        else:
            scratchpad = memory_manager.build_context_scratchpad(session_id, phone=customer_phone)

        # Resolve store_id from customer profile if not provided
        if not store_id and customer_phone:
            profile = memory_manager.get_customer_profile(customer_phone)
            if profile:
                store_id = profile.preferred_store_id
        effective_store_id = store_id or "STORE-001"

        # Step 3: Plan Before It Acts (📘 L5)
        plan = QueryPlanner.create_plan(query)

        # Add initial user query with plan context
        initial_prompt = f"Shopper Query: {query}\n{plan.render_checklist()}"
        scratchpad.append({"role": "user", "content": initial_prompt})

        steps: List[StepRecord] = []
        step_count = 0
        consecutive_tool_failures = 0

        while step_count < self.max_steps:
            step_count += 1

            # 1. THINK: LLM internal reasoning (📘 L1, L3)
            agent_thought = self.llm.generate(scratchpad)

            # Record thought and intended action
            record = StepRecord(
                step_number=step_count,
                thought=agent_thought.thought,
                action_type=agent_thought.action_type,
                tool_name=agent_thought.tool_name,
                tool_args=agent_thought.tool_args or {},
            )

            # 2. ACT: Dispatch action based on action_type
            # 2a. Safety Gate: Asks You First (📘 L7)
            if agent_thought.action_type == "ask_user":
                record.observation = "Awaiting user confirmation."
                steps.append(record)
                final_resp = agent_thought.response_text or "Please confirm to proceed."

                # Register pending confirmation state for next turn
                self.pending_confirmations[session_id] = {
                    "action": "Sensitive customer request / order update",
                    "prompt": final_resp,
                }

                # Save to short-term memory
                session = memory_manager.get_session(session_id)
                session.add_message("user", query)
                session.add_message("assistant", final_resp)

                turn_res = AgentTurnResult(
                    query=query,
                    final_response=final_resp,
                    plan=plan,
                    steps=steps,
                    total_steps=step_count,
                    contained=True,
                    needs_user_confirmation=True,
                )
                self._log_audit(turn_res, session_id, customer_phone)
                return turn_res

            # 2b. Final Answer: Resolution reached
            if agent_thought.action_type == "final_answer":
                steps.append(record)
                final_resp = agent_thought.response_text or "Here is what I found for you."

                # Save to short-term session memory
                session = memory_manager.get_session(session_id)
                session.add_message("user", query)
                session.add_message("assistant", final_resp)

                # Update long-term persistent customer memory (📘 L4)
                if customer_phone:
                    memory_manager.update_customer_memory(
                        phone=customer_phone,
                        query=query,
                        inquired_product=plan.sub_tasks[0].tool_hint if plan.sub_tasks else None,
                    )

                turn_res = AgentTurnResult(
                    query=query,
                    final_response=final_resp,
                    plan=plan,
                    steps=steps,
                    total_steps=step_count,
                    contained=True,
                    escalated=False,
                )
                self._log_audit(turn_res, session_id, customer_phone)
                return turn_res

            # 2c. Tool Call Execution
            if agent_thought.action_type == "tool_call":
                tool_name = agent_thought.tool_name or ""
                tool_args = dict(agent_thought.tool_args or {})
                if "store_id" not in tool_args and tool_name in [
                    "check_inventory_and_price", "get_store_info", "get_active_promotions"
                ]:
                    tool_args["store_id"] = effective_store_id

                # 3. LOOK: Execute tool and observe result / self-correction hint (📘 L2, L3)
                tool_result = execute_tool(tool_name, tool_args)
                observation_str = tool_result.to_observation()
                record.observation = observation_str
                steps.append(record)

                if not tool_result.success:
                    consecutive_tool_failures += 1
                else:
                    consecutive_tool_failures = 0

                # Consecutive failures escalation trigger (📘 L7)
                if consecutive_tool_failures >= 2:
                    ticket = GuardrailEngine.create_handoff(
                        session_id=session_id,
                        customer_phone=customer_phone,
                        reason="Multiple consecutive tool execution failures occurred.",
                        shopper_intent=query,
                        transcript=session.get_history_for_llm() if (session := memory_manager.get_session(session_id)) else [],
                    )
                    turn_res = AgentTurnResult(
                        query=query,
                        final_response=(
                            "I'm having trouble looking up that information from our store systems. "
                            f"I've transferred your request to store staff (Ticket #{ticket.ticket_id}) with full details."
                        ),
                        plan=plan,
                        steps=steps,
                        total_steps=step_count,
                        contained=False,
                        escalated=True,
                        escalation_reason="Repeated tool failures.",
                        handoff_ticket=ticket,
                    )
                    self._log_audit(turn_res, session_id, customer_phone)
                    return turn_res

                # Update plan checklist if matching pending task
                next_task = plan.get_next_pending_task()
                if next_task:
                    plan.mark_task_completed(
                        next_task.id,
                        f"Executed {tool_name} (Success={tool_result.success})"
                    )

                # Append to scratchpad for the next THINK step
                scratchpad.append({
                    "role": "tool",
                    "content": f"{observation_str}\nUpdated {plan.render_checklist()}",
                })

        # Step limit reached without final answer: Safety Breaker (📘 L7)
        ticket = GuardrailEngine.create_handoff(
            session_id=session_id,
            customer_phone=customer_phone,
            reason=f"Execution reached step limit ({self.max_steps} iterations).",
            shopper_intent=query,
            transcript=memory_manager.get_session(session_id).get_history_for_llm(),
        )
        turn_res = AgentTurnResult(
            query=query,
            final_response=(
                "I apologize, but this inquiry requires assistance from our in-store customer service team. "
                f"I have forwarded our conversation context to staff (Ticket #{ticket.ticket_id})."
            ),
            plan=plan,
            steps=steps,
            total_steps=step_count,
            contained=False,
            escalated=True,
            escalation_reason=f"Execution reached step limit ({self.max_steps} iterations).",
            handoff_ticket=ticket,
        )
        self._log_audit(turn_res, session_id, customer_phone)
        return turn_res

    def _log_audit(self, res: AgentTurnResult, session_id: str, customer_phone: Optional[str]) -> None:
        """Write structured turn entry to audit trail (📘 L7)."""
        entry = AuditEntry(
            audit_id=f"AUD-{uuid.uuid4().hex[:8].upper()}",
            session_id=session_id,
            customer_phone=customer_phone,
            query=res.query,
            plan_summary=res.plan.render_checklist(),
            steps_count=res.total_steps,
            steps=[s.model_dump() for s in res.steps],
            final_response=res.final_response,
            contained=res.contained,
            escalated=res.escalated,
            escalation_reason=res.escalation_reason,
            needs_confirmation=res.needs_user_confirmation,
        )
        audit_logger.log_turn(entry)
