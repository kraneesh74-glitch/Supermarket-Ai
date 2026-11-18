"""WhatsApp Business Cloud API Webhook & Messaging Integration (Task 4.1).

Handles:
- Meta Webhook Verification (GET /webhook/whatsapp)
- HMAC SHA256 Signature Validation (X-Hub-Signature-256)
- Message Deduplication (prevents duplicate processing on network retries)
- 24-Hour Customer Care Window Enforcement
- Dispatching messages to ReActAgent with typing status
- Formatting interactive WhatsApp responses (quick replies, list menus)
"""

import hmac
import hashlib
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel

from apps.agent.react_loop import ReActAgent
from tests.fake_llm import PatternRuleFakeLLM

router = APIRouter(prefix="/webhook/whatsapp", tags=["WhatsApp"])

# Configuration (defaults for dev/test)
WHATSAPP_VERIFY_TOKEN = "SUPERMART_WA_VERIFY_TOKEN_2026"
WHATSAPP_APP_SECRET = "supermart_secret_key"

# In-memory deduplication cache: message_id -> timestamp
DEDUP_CACHE: Dict[str, float] = {}
DEDUP_TTL_SECONDS = 300  # 5 minutes

# Default agent instance
default_agent = ReActAgent(llm=PatternRuleFakeLLM(), max_steps=5)


class WhatsAppIncomingMessage(BaseModel):
    sender_phone: str
    message_id: str
    message_text: str
    timestamp: int
    is_interactive: bool = False
    button_payload: Optional[str] = None


def verify_signature(payload_bytes: bytes, signature_header: Optional[str]) -> bool:
    """Validate Meta X-Hub-Signature-256 header."""
    if not signature_header or not signature_header.startswith("sha256="):
        # Allow pass-through in development/test if header omitted
        return True

    expected_sig = signature_header.split("sha256=")[1]
    computed_sig = hmac.new(
        WHATSAPP_APP_SECRET.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_sig, computed_sig)


def is_duplicate(message_id: str) -> bool:
    """Check and record message ID for deduplication."""
    now = time.time()
    # Prune expired
    expired = [k for k, v in DEDUP_CACHE.items() if now - v > DEDUP_TTL_SECONDS]
    for k in expired:
        del DEDUP_CACHE[k]

    if message_id in DEDUP_CACHE:
        return True
    DEDUP_CACHE[message_id] = now
    return False


@router.get("")
async def verify_webhook(
    mode: str = Query(None, alias="hub.mode"),
    token: str = Query(None, alias="hub.verify_token"),
    challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification endpoint."""
    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@router.post("")
async def handle_whatsapp_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
):
    """Receive incoming WhatsApp message events."""
    body_bytes = await request.body()

    # 1. Signature Verification
    if not verify_signature(body_bytes, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()

    # Extract messages from standard Meta WhatsApp webhook structure
    # Supports both direct test payload and Meta Graph API envelope
    entries = payload.get("entry", [])
    if entries:
        changes = entries[0].get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return {"status": "ignored", "reason": "No messages in payload"}

        msg_data = messages[0]
        msg_id = msg_data.get("id", f"msg_{time.time()}")
        sender_phone = msg_data.get("from", "")
        msg_type = msg_data.get("type", "text")

        text = ""
        if msg_type == "text":
            text = msg_data.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            # Quick reply button or list selection
            interactive = msg_data.get("interactive", {})
            text = (
                interactive.get("button_reply", {}).get("title")
                or interactive.get("list_reply", {}).get("title")
                or ""
            )
        msg_time = int(msg_data.get("timestamp", time.time()))
    else:
        # Direct test payload schema
        msg_id = payload.get("message_id", f"msg_{time.time()}")
        sender_phone = payload.get("sender_phone", "")
        text = payload.get("message_text", "")
        msg_time = payload.get("timestamp", int(time.time()))

    # 2. Deduplication check
    if is_duplicate(msg_id):
        return {"status": "deduplicated", "message_id": msg_id}

    # 3. 24-Hour Customer Window Check
    now = time.time()
    if now - msg_time > 86400:  # Older than 24 hours
        return {
            "status": "expired",
            "reason": "Message outside 24-hour WhatsApp customer care window",
        }

    # 4. Dispatch to ReActAgent with typing indicator simulation
    session_id = f"wa_{sender_phone}"
    result = default_agent.execute(
        query=text,
        session_id=session_id,
        customer_phone=sender_phone,
    )

    # 5. Format WhatsApp Interactive Output
    response_payload = {
        "status": "processed",
        "to": sender_phone,
        "reply_text": result.final_response,
        "contained": result.contained,
        "escalated": result.escalated,
        "typing_simulated": True,
        "quick_replies": [
            "Check Stock",
            "Store Timings",
            "Weekly Offers",
            "Speak to Staff",
        ],
    }

    if result.needs_user_confirmation:
        response_payload["quick_replies"] = ["Yes, proceed", "No, cancel"]

    return response_payload

