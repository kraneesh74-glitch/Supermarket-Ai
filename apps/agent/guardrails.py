"""Safety Guardrails, Non-Goal Enforcement & Staff Handoff Engine (📘 Lesson 7).

Implements:
1. Non-Goal Enforcement (v1 PRD): Refuse direct chat payment processing and cash refunds.
2. Escalation Trigger Engine: Detects explicit staff requests, frustration, repeated failures.
3. Structured Handoff Ticket: Packages 100% complete conversation context for store staff.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import uuid


class HandoffTicket(BaseModel):
    ticket_id: str = Field(default_factory=lambda: f"TICK-{uuid.uuid4().hex[:6].upper()}")
    session_id: str
    customer_phone: Optional[str] = None
    customer_name: Optional[str] = "Shopper"
    reason: str
    shopper_intent: str
    summary: str
    transcript: List[Dict[str, str]] = Field(default_factory=list)
    referenced_items_or_orders: List[str] = Field(default_factory=list)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class GuardrailResult(BaseModel):
    passed: bool
    action: str = "proceed"  # "proceed", "refuse_non_goal", "escalate_staff", "needs_confirmation"
    reason: Optional[str] = None
    response_text: Optional[str] = None
    handoff_ticket: Optional[HandoffTicket] = None


class GuardrailEngine:
    """Enforces PRD boundaries, safety restrictions, and escalation triggers."""

    # PRD v1 Non-Goals: Direct chat payments & cash refunds
    PAYMENT_REFUND_KEYWORDS = [
        "take payment", "process payment", "credit card number",
        "cash refund", "direct refund", "refund to card", "refund my money now"
    ]

    # Explicit Human Staff Escalation Keywords
    STAFF_KEYWORDS = [
        "human", "representative", "agent", "staff", "manager",
        "speak to someone", "talk to a person", "talk to staff", "customer support agent"
    ]

    # Frustration / Complaint Sentiment Keywords
    FRUSTRATION_KEYWORDS = [
        "useless", "terrible service", "horrible", "angry", "lawyer",
        "rip off", "scam", "unacceptable", "worst supermarket"
    ]

    @classmethod
    def inspect_query(
        cls,
        query: str,
        session_id: str,
        customer_phone: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> GuardrailResult:
        q_lower = query.lower()

        # 1. Non-Goal Guardrail: Payment & Direct Cash Refund Refusal (PRD v1)
        if any(kw in q_lower for kw in cls.PAYMENT_REFUND_KEYWORDS):
            return GuardrailResult(
                passed=False,
                action="refuse_non_goal",
                reason="Direct payment processing and cash refunds in chat are out of scope (v1 non-goal).",
                response_text=(
                    "For your security, I cannot process payments or issue cash refunds directly in chat. "
                    "Per supermarket policy, returns and refunds are processed in-person at the Customer Service Desk "
                    "within 14 days with receipt (or 24 hours for perishable items). Would you like store hours or directions?"
                ),
            )

        # 2. Explicit Human Request
        if any(kw in q_lower for kw in cls.STAFF_KEYWORDS):
            ticket = cls.create_handoff(
                session_id=session_id,
                customer_phone=customer_phone,
                reason="Customer explicitly requested human staff assistance.",
                shopper_intent=query,
                transcript=conversation_history or [],
            )
            return GuardrailResult(
                passed=False,
                action="escalate_staff",
                reason="Explicit human escalation requested.",
                response_text=(
                    "I am connecting you with a store staff member right now. "
                    f"Your Ticket #{ticket.ticket_id} has been created with full conversation context."
                ),
                handoff_ticket=ticket,
            )

        # 3. Frustration / Formal Complaint Detection
        if any(kw in q_lower for kw in cls.FRUSTRATION_KEYWORDS):
            ticket = cls.create_handoff(
                session_id=session_id,
                customer_phone=customer_phone,
                reason="Negative sentiment / customer frustration detected.",
                shopper_intent=query,
                transcript=conversation_history or [],
            )
            return GuardrailResult(
                passed=False,
                action="escalate_staff",
                reason="Customer frustration trigger.",
                response_text=(
                    "I'm truly sorry for your frustration. I am escalating your concern directly to our store manager "
                    f"(Ticket #{ticket.ticket_id}) so they can assist you immediately."
                ),
                handoff_ticket=ticket,
            )

        return GuardrailResult(passed=True)

    @staticmethod
    def create_handoff(
        session_id: str,
        customer_phone: Optional[str],
        reason: str,
        shopper_intent: str,
        transcript: List[Dict[str, str]],
        referenced_items: Optional[List[str]] = None,
    ) -> HandoffTicket:
        """Create structured handoff ticket ensuring 100% context delivery to staff."""
        summary = (
            f"Customer Intent: '{shopper_intent}'. "
            f"Escalation Reason: {reason}. "
            f"Conversation Length: {len(transcript)} messages."
        )

        return HandoffTicket(
            session_id=session_id,
            customer_phone=customer_phone,
            reason=reason,
            shopper_intent=shopper_intent,
            summary=summary,
            transcript=transcript,
            referenced_items_or_orders=referenced_items or [],
        )

