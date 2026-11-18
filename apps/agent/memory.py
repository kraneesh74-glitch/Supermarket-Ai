"""Memory Systems & Context Persistence (📘 Lesson 4: Memory Between Tasks).

Provides:
1. Short-Term Session Memory: Sliding-window conversation buffer for multi-turn chats.
2. Long-Term Customer Memory: Persistent profile across tasks/sessions (preferred branch,
   dietary restrictions, recent inquiries, last order ID).
3. MemoryManager: Orchestrates memory retrieval and context injection into the ReAct loop.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from data.mock_database import db


class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CustomerProfile(BaseModel):
    phone: str
    customer_id: Optional[str] = None
    name: Optional[str] = "Shopper"
    preferred_store_id: str = "STORE-001"
    dietary_preferences: List[str] = Field(default_factory=list)
    recent_inquiries: List[str] = Field(default_factory=list)
    last_order_id: Optional[str] = None
    loyalty_tier: Optional[str] = "Bronze"
    loyalty_points: int = 0

    def render_context_prompt(self) -> str:
        """Render customer profile as a structured context block for the agent's Think step."""
        lines = [f"[Customer Context: {self.name} ({self.phone})]"]
        lines.append(f"- Preferred Store: {self.preferred_store_id}")
        if self.dietary_preferences:
            lines.append(f"- Dietary Preferences: {', '.join(self.dietary_preferences)}")
        if self.recent_inquiries:
            lines.append(f"- Recent Inquiries: {', '.join(self.recent_inquiries[-3:])}")
        if self.last_order_id:
            lines.append(f"- Last Active Order: {self.last_order_id}")
        if self.loyalty_points > 0:
            lines.append(f"- Loyalty: {self.loyalty_tier} ({self.loyalty_points} pts)")
        return "\n".join(lines)


class SessionMemory:
    """Sliding-window short-term conversation buffer for active sessions."""

    def __init__(self, max_turns: int = 6):
        self.max_turns = max_turns
        self.messages: List[ChatMessage] = []

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content))
        # Sliding window pruning: retain only the most recent N turns
        if len(self.messages) > self.max_turns * 2:
            self.messages = self.messages[-(self.max_turns * 2):]

    def get_history_for_llm(self) -> List[Dict[str, str]]:
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def clear(self) -> None:
        self.messages.clear()


class MemoryManager:
    """Orchestrates short-term session memory and long-term customer profiles."""

    def __init__(self, default_window_size: int = 6):
        self.default_window_size = default_window_size
        self._sessions: Dict[str, SessionMemory] = {}
        self._profiles: Dict[str, CustomerProfile] = {}
        self._init_from_mock_db()

    def _init_from_mock_db(self) -> None:
        """Pre-populate profiles from database customer records."""
        for c in db.customers:
            phone = c["phone"]
            prefs = []
            for item in c.get("dietary_preferences", []):
                if isinstance(item, list):
                    prefs.extend(item)
                else:
                    prefs.append(item)

            self._profiles[phone] = CustomerProfile(
                phone=phone,
                customer_id=c.get("customer_id"),
                name=c.get("name"),
                preferred_store_id=c.get("preferred_store_id", "STORE-001"),
                dietary_preferences=prefs,
                recent_inquiries=[],
                last_order_id=c.get("recent_orders", [None])[0] if c.get("recent_orders") else None,
                loyalty_tier=c.get("loyalty_tier", "Bronze"),
                loyalty_points=c.get("loyalty_points", 0),
            )

    def get_session(self, session_id: str) -> SessionMemory:
        if session_id not in self._sessions:
            self._sessions[session_id] = SessionMemory(max_turns=self.default_window_size)
        return self._sessions[session_id]

    def get_customer_profile(self, phone: Optional[str]) -> Optional[CustomerProfile]:
        if not phone:
            return None
        # Clean numeric normalization
        clean_phone = "".join(filter(str.isdigit, phone))
        for p_key, profile in self._profiles.items():
            if "".join(filter(str.isdigit, p_key)) == clean_phone:
                return profile

        # Create new customer profile if first-time contact
        new_profile = CustomerProfile(phone=phone)
        self._profiles[phone] = new_profile
        return new_profile

    def update_customer_memory(
        self,
        phone: str,
        query: str,
        inquired_product: Optional[str] = None,
        detected_preference: Optional[str] = None,
        referenced_order: Optional[str] = None,
    ) -> CustomerProfile:
        """Update long-term memory after a conversation turn."""
        profile = self.get_customer_profile(phone)
        if not profile:
            profile = CustomerProfile(phone=phone)
            self._profiles[phone] = profile

        # Heuristic extraction of preferences if not explicitly supplied
        q_lower = query.lower()
        if "gluten-free" in q_lower or "celiac" in q_lower:
            if "Gluten-Free" not in profile.dietary_preferences:
                profile.dietary_preferences.append("Gluten-Free")
        if "vegan" in q_lower or "plant-based" in q_lower or "dairy-free" in q_lower:
            if "Dairy-Free / Vegan" not in profile.dietary_preferences:
                profile.dietary_preferences.append("Dairy-Free / Vegan")
        if "organic" in q_lower:
            if "Organic" not in profile.dietary_preferences:
                profile.dietary_preferences.append("Organic")

        if detected_preference and detected_preference not in profile.dietary_preferences:
            profile.dietary_preferences.append(detected_preference)

        if inquired_product and inquired_product not in profile.recent_inquiries:
            profile.recent_inquiries.append(inquired_product)

        if referenced_order:
            profile.last_order_id = referenced_order

        # Sync back to mock DB
        db.save_customer_memory(phone, "dietary_preferences", profile.dietary_preferences)
        return profile

    def build_context_scratchpad(
        self, session_id: str, phone: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Construct the prompt history with long-term memory header and recent turns."""
        scratchpad: List[Dict[str, str]] = []

        # 1. Long-Term Customer Memory Header (📘 L4)
        profile = self.get_customer_profile(phone)
        if profile:
            scratchpad.append({
                "role": "system",
                "content": profile.render_context_prompt(),
            })

        # 2. Short-Term Session Dialogue History
        session = self.get_session(session_id)
        scratchpad.extend(session.get_history_for_llm())
        return scratchpad


# App-wide singleton memory manager
memory_manager = MemoryManager()
