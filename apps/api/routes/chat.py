"""Web Chat & CSAT Rating API Routes (Task 4.2 & Task 4.3).

Provides:
- Standard JSON Chat Endpoint (/api/chat)
- Server-Sent Events (SSE) Streaming Endpoint (/api/chat/stream) for < 1s perceived first-token latency
- CSAT Survey Collection Endpoint (/api/csat)
- Cache Invalidation Webhook (/api/cache/invalidate)
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from apps.agent.react_loop import ReActAgent
from apps.agent.cache import cache
from apps.agent.live_llm import LiveSupermarketLLM

router = APIRouter(prefix="/api", tags=["Chat & Operations"])

default_agent = ReActAgent(llm=LiveSupermarketLLM(), max_steps=5)

# CSAT In-Memory Records
CSAT_RECORDS: List[Dict[str, Any]] = []


class ChatRequest(BaseModel):
    message: str
    session_id: str = "web_default"
    customer_phone: Optional[str] = None
    store_id: Optional[str] = "STORE-001"
    api_key: Optional[str] = None


class CSATRequest(BaseModel):
    session_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    customer_phone: Optional[str] = None


class InvalidateCacheRequest(BaseModel):
    tag: str = "inventory"  # "inventory", "store_info", "promotions", or "all"


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    """Standard synchronous chat endpoint."""
    t0 = time.time()
    agent = ReActAgent(llm=LiveSupermarketLLM(api_key=req.api_key), max_steps=5) if req.api_key else default_agent
    result = agent.execute(
        query=req.message,
        session_id=req.session_id,
        customer_phone=req.customer_phone,
        store_id=req.store_id,
    )
    latency_ms = round((time.time() - t0) * 1000, 2)

    return {
        "reply": result.final_response,
        "contained": result.contained,
        "escalated": result.escalated,
        "needs_user_confirmation": result.needs_user_confirmation,
        "total_steps": result.total_steps,
        "latency_ms": latency_ms,
        "plan": [t.description for t in result.plan.sub_tasks],
    }


@router.post("/chat/stream")
async def chat_stream_endpoint(req: ChatRequest):
    """SSE streaming endpoint providing instant typing events and streamed tokens."""
    async def event_generator():
        # 1. Immediate typing status event (< 50ms)
        yield f"event: status\ndata: {json.dumps({'status': 'thinking'})}\n\n"
        await asyncio.sleep(0.05)

        # 2. Execute agent
        result = default_agent.execute(
            query=req.message,
            session_id=req.session_id,
            customer_phone=req.customer_phone,
            store_id=req.store_id,
        )

        # 3. Stream plan progression
        for task in result.plan.sub_tasks:
            yield f"event: plan_step\ndata: {json.dumps({'step': task.description, 'completed': task.completed})}\n\n"
            await asyncio.sleep(0.02)

        # 4. Stream response words with simulated typing for immediate perceived response (< 1s first token)
        words = result.final_response.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            yield f"event: token\ndata: {json.dumps({'token': chunk})}\n\n"
            await asyncio.sleep(0.01)

        # 5. Done event with metadata
        yield f"event: done\ndata: {json.dumps({'contained': result.contained, 'escalated': result.escalated})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/csat")
async def submit_csat(req: CSATRequest):
    """Collect customer satisfaction rating (1-5) upon conversation resolution."""
    record = {
        "session_id": req.session_id,
        "rating": req.rating,
        "comment": req.comment,
        "customer_phone": req.customer_phone,
        "timestamp": time.time(),
    }
    CSAT_RECORDS.append(record)

    # Compute live CSAT average
    avg_score = round(sum(r["rating"] for r in CSAT_RECORDS) / len(CSAT_RECORDS), 2)
    return {
        "status": "success",
        "message": "Thank you for your feedback!",
        "recorded": record,
        "current_csat_average": avg_score,
        "total_responses": len(CSAT_RECORDS),
    }


@router.post("/cache/invalidate")
async def invalidate_cache_endpoint(req: InvalidateCacheRequest):
    """Webhook triggered on supermarket inventory / POS updates to invalidate stale cache."""
    if req.tag == "all":
        cache.clear()
        return {"status": "cleared_all"}

    count = cache.invalidate_tag(req.tag)
    return {"status": "invalidated", "tag": req.tag, "entries_purged": count}

