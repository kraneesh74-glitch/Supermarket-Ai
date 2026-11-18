"""Concurrency & Latency Stress Testing (< 5s SLA - Task 4.4, Task 4.1, Task 4.3)."""

import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from apps.agent.cache import cache

client = TestClient(app)


def test_health_check_endpoint():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"


def test_whatsapp_webhook_verification():
    # Valid challenge verification
    res = client.get(
        "/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=SUPERMART_WA_VERIFY_TOKEN_2026&hub.challenge=test_12345"
    )
    assert res.status_code == 200
    assert res.text == "test_12345"

    # Invalid token rejected with 403
    res_bad = client.get(
        "/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=WRONG_TOKEN&hub.challenge=test_12345"
    )
    assert res_bad.status_code == 403


def test_whatsapp_incoming_message_and_deduplication():
    msg_id = f"wa_msg_unique_{time.time()}"
    payload = {
        "sender_phone": "+15551234567",
        "message_id": msg_id,
        "message_text": "Are avocados in stock?",
        "timestamp": int(time.time()),
    }

    # First send -> processed
    res1 = client.post("/webhook/whatsapp", json=payload)
    assert res1.status_code == 200
    body1 = res1.json()
    assert body1["status"] == "processed"
    assert "reply_text" in body1
    assert "quick_replies" in body1

    # Second send with same message_id -> deduplicated instantly
    res2 = client.post("/webhook/whatsapp", json=payload)
    assert res2.status_code == 200
    body2 = res2.json()
    assert body2["status"] == "deduplicated"


def test_chat_api_and_csat_recording():
    # Chat message
    chat_res = client.post(
        "/api/chat",
        json={"message": "What time does the store close?", "session_id": "test_web_sess"},
    )
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert data["contained"] is True
    assert data["latency_ms"] < 5000  # Strictly under 5s SLA

    # Submit CSAT feedback
    csat_res = client.post(
        "/api/csat",
        json={"session_id": "test_web_sess", "rating": 5, "comment": "Super fast answers!"},
    )
    assert csat_res.status_code == 200
    csat_data = csat_res.json()
    assert csat_data["status"] == "success"
    assert csat_data["current_csat_average"] >= 1.0


def test_caching_layer_speedup_and_invalidation():
    cache.clear()
    args = {"query_type": "hours", "store_id": "STORE-001"}

    # Turn 1: Cold read
    t0 = time.time()
    res1 = client.post("/api/chat", json={"message": "What are your operating hours?", "session_id": "c_sess1"})
    cold_latency = time.time() - t0

    # Turn 2: Warm read from cache
    t1 = time.time()
    res2 = client.post("/api/chat", json={"message": "What are your operating hours?", "session_id": "c_sess2"})
    warm_latency = time.time() - t1

    assert res1.status_code == 200
    assert res2.status_code == 200
    assert warm_latency <= cold_latency or warm_latency < 0.05

    # Test cache invalidation endpoint
    inv_res = client.post("/api/cache/invalidate", json={"tag": "store_info"})
    assert inv_res.status_code == 200
    assert inv_res.json()["status"] == "invalidated"


def test_concurrency_stress_and_sub_5s_latency():
    """Simulate 50 concurrent shopper queries and verify < 5s response time for 90% (Task 4.4)."""
    queries = [
        "Are avocados in stock?",
        "What time does the bakery open?",
        "Where is my order ORD-9481?",
        "What chips are on sale?",
        "What is the return policy?",
        "Do you carry almond milk?",
        "How much is whole milk?",
        "Do you have parking?",
        "Are there gluten-free bread options?",
        "What are your holiday hours?",
    ] * 5  # 50 total requests

    latencies = []

    def make_request(idx_and_query):
        idx, q = idx_and_query
        sess = f"stress_sess_{idx}"
        t_start = time.time()
        resp = client.post("/api/chat", json={"message": q, "session_id": sess})
        elapsed = time.time() - t_start
        assert resp.status_code == 200
        return elapsed

    # Execute 50 concurrent requests via ThreadPool
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(make_request, enumerate(queries)))

    latencies = sorted(results)
    p50 = latencies[int(len(latencies) * 0.50)]
    p90 = latencies[int(len(latencies) * 0.90)]
    p99 = latencies[int(len(latencies) * 0.99)]

    print(f"\n[LATENCY BENCHMARK] 50 Concurrent Requests:")
    print(f"p50: {p50*1000:.1f}ms | p90: {p90*1000:.1f}ms | p99: {p99*1000:.1f}ms")

    # PRD SLA Validation: 90% of requests must resolve in < 5 seconds
    assert p90 < 5.0, f"p90 latency {p90}s exceeded 5-second target SLA"
    assert p50 < 2.0, f"Median latency {p50}s exceeded target"

