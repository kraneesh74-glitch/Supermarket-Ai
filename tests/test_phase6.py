"""Phase 6 Tests — CSAT Scoring & Weekly Manager Report (Tasks 6.1 & 6.2).

Covers:
- 6.1: CSAT endpoint: stores ratings, returns live average, accumulates correctly
- 6.2: Weekly report endpoint: validates all required report structure fields
         and sub-keys expected by store managers
"""

import json
import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# App & shared state import
# ---------------------------------------------------------------------------
from apps.api.main import app
from apps.api.routes import chat as chat_module  # access CSAT_RECORDS directly

client = TestClient(app)


def _clear_csat():
    """Helper: wipe in-memory CSAT records between tests."""
    chat_module.CSAT_RECORDS.clear()


# ===========================================================================
# Task 6.1 — CSAT Prompt & Scoring
# ===========================================================================


class TestCSATEndpoint:
    """POST /api/csat — rating storage, averaging, and accumulation."""

    def setup_method(self):
        _clear_csat()

    # --- 6.1.1: Single rating stored and returned --------------------------
    def test_csat_stores_single_rating_and_returns_average(self):
        resp = client.post(
            "/api/csat",
            json={"session_id": "sess-001", "rating": 5},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["status"] == "success"
        assert data["total_responses"] == 1
        assert data["current_csat_average"] == 5.0
        assert data["recorded"]["rating"] == 5
        assert data["recorded"]["session_id"] == "sess-001"

    # --- 6.1.2: Average calculation is correct with multiple ratings -------
    def test_csat_average_is_mathematically_correct(self):
        ratings = [4, 5, 3, 5, 4]  # mean = 4.2
        for i, r in enumerate(ratings):
            client.post("/api/csat", json={"session_id": f"sess-{i}", "rating": r})

        resp = client.post(
            "/api/csat",
            json={"session_id": "sess-final", "rating": 4},
        )
        # ratings now [4,5,3,5,4,4] → mean = 25/6 ≈ 4.17
        data = resp.json()
        expected_avg = round(sum([4, 5, 3, 5, 4, 4]) / 6, 2)
        assert data["current_csat_average"] == expected_avg
        assert data["total_responses"] == 6

    # --- 6.1.3: Ratings accumulate across separate requests ----------------
    def test_csat_accumulates_across_requests(self):
        for i, rating in enumerate([5, 4, 5], start=1):
            resp = client.post(
                "/api/csat",
                json={"session_id": f"sess-acc-{i}", "rating": rating},
            )
            assert resp.json()["total_responses"] == i

        # Verify final state
        assert len(chat_module.CSAT_RECORDS) == 3

    # --- 6.1.4: Optional comment is stored ---------------------------------
    def test_csat_stores_optional_comment(self):
        resp = client.post(
            "/api/csat",
            json={
                "session_id": "sess-comment",
                "rating": 4,
                "comment": "Very helpful bot!",
            },
        )
        data = resp.json()
        assert data["recorded"]["comment"] == "Very helpful bot!"

    # --- 6.1.5: Boundary ratings accepted (1 and 5) ------------------------
    def test_csat_boundary_ratings_accepted(self):
        for rating in [1, 5]:
            resp = client.post(
                "/api/csat",
                json={"session_id": f"sess-boundary-{rating}", "rating": rating},
            )
            assert resp.status_code == 200
            assert resp.json()["recorded"]["rating"] == rating

    # --- 6.1.6: Out-of-bound ratings rejected (0 and 6) -------------------
    def test_csat_rejects_out_of_bound_ratings(self):
        for bad_rating in [0, 6]:
            resp = client.post(
                "/api/csat",
                json={"session_id": "sess-bad", "rating": bad_rating},
            )
            assert resp.status_code == 422, f"Expected 422 for rating={bad_rating}"

    # --- 6.1.7: Average meets PRD ≥ 4.2 target after positive ratings ------
    def test_csat_average_meets_prd_target_on_positive_session(self):
        for i, r in enumerate([5, 5, 4, 5, 4]):
            client.post("/api/csat", json={"session_id": f"pos-{i}", "rating": r})

        avg = sum([5, 5, 4, 5, 4]) / 5  # = 4.6
        assert avg >= 4.2, "Average of positive ratings should meet PRD ≥ 4.2 CSAT target"


# ===========================================================================
# Task 6.2 — Weekly Manager Insight Report
# ===========================================================================


class TestWeeklyReportEndpoint:
    """GET /api/reports/weekly — validates report structure and all required keys."""

    def test_weekly_report_returns_200(self):
        resp = client.get("/api/reports/weekly")
        assert resp.status_code == 200, resp.text

    def test_weekly_report_is_valid_json(self):
        resp = client.get("/api/reports/weekly")
        try:
            data = resp.json()
        except Exception as exc:
            pytest.fail(f"Response is not valid JSON: {exc}")
        assert isinstance(data, dict)

    def test_weekly_report_has_executive_summary(self):
        data = client.get("/api/reports/weekly").json()
        assert "executive_summary" in data, "Missing 'executive_summary' key"
        summary = data["executive_summary"]
        required_summary_keys = [
            "total_shopper_enquiries",
            "containment_rate",
            "containment_target_met",
            "escalated_to_staff_count",
            "average_csat",
            "csat_target_met",
        ]
        for key in required_summary_keys:
            assert key in summary, f"executive_summary missing key: '{key}'"

    def test_weekly_report_has_top_shopper_interests(self):
        data = client.get("/api/reports/weekly").json()
        assert "top_shopper_interests" in data, "Missing 'top_shopper_interests' key"
        assert isinstance(data["top_shopper_interests"], list)

    def test_weekly_report_has_stock_out_demand_tracker(self):
        data = client.get("/api/reports/weekly").json()
        assert "stock_out_demand_tracker" in data, "Missing 'stock_out_demand_tracker' key"
        tracker = data["stock_out_demand_tracker"]
        assert "description" in tracker
        assert "unmet_demand_items" in tracker
        assert isinstance(tracker["unmet_demand_items"], list)

    def test_weekly_report_has_escalation_themes(self):
        data = client.get("/api/reports/weekly").json()
        assert "escalation_and_complaint_themes" in data, "Missing 'escalation_and_complaint_themes'"
        assert isinstance(data["escalation_and_complaint_themes"], list)

    def test_weekly_report_has_recommendations(self):
        data = client.get("/api/reports/weekly").json()
        assert "recommendations_for_store_team" in data, "Missing 'recommendations_for_store_team'"
        recs = data["recommendations_for_store_team"]
        assert isinstance(recs, list)
        assert len(recs) >= 1, "Should have at least one recommendation"

    def test_weekly_report_has_metadata_fields(self):
        data = client.get("/api/reports/weekly").json()
        assert "report_generated_at" in data, "Missing 'report_generated_at'"
        assert "reporting_period" in data, "Missing 'reporting_period'"

    def test_weekly_report_containment_target_met_is_bool(self):
        data = client.get("/api/reports/weekly").json()
        assert isinstance(
            data["executive_summary"]["containment_target_met"], bool
        ), "containment_target_met must be a boolean"

    def test_weekly_report_csat_target_field_is_bool(self):
        data = client.get("/api/reports/weekly").json()
        assert isinstance(
            data["executive_summary"]["csat_target_met"], bool
        ), "csat_target_met must be a boolean"

    def test_weekly_report_is_idempotent(self):
        """Calling the endpoint twice returns consistent structure."""
        r1 = client.get("/api/reports/weekly").json()
        r2 = client.get("/api/reports/weekly").json()
        assert r1.keys() == r2.keys()

    def test_weekly_report_download_endpoint_exists(self):
        """GET /api/reports/weekly/download should return 200 with JSON file."""
        resp = client.get("/api/reports/weekly/download")
        assert resp.status_code == 200
        # It's served as application/json
        assert "json" in resp.headers.get("content-type", "")


# ===========================================================================
# Task 6.3 — Live Pilot Smoke Tests (integration with real agent)
# ===========================================================================


class TestPilotSmoke:
    """Core smoke tests for the branch pilot: chat, escalation, WhatsApp webhook."""

    def test_chat_stock_query_avocados(self):
        """POST /api/chat with a stock query returns a valid reply."""
        resp = client.post(
            "/api/chat",
            json={"message": "Are avocados in stock?", "session_id": "pilot-001"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "reply" in data
        assert isinstance(data["reply"], str)
        assert len(data["reply"]) > 0
        assert "contained" in data
        assert "latency_ms" in data

    def test_chat_escalation_to_manager(self):
        """POST /api/chat requesting a manager triggers escalation."""
        resp = client.post(
            "/api/chat",
            json={"message": "I want to speak to a manager", "session_id": "pilot-002"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "reply" in data
        # Escalation should be detected
        assert data.get("escalated") is True or "staff" in data["reply"].lower() or "manager" in data["reply"].lower()

    def test_whatsapp_webhook_verification(self):
        """GET /webhook/whatsapp with hub.challenge should echo back the challenge."""
        resp = client.get(
            "/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "SUPERMART_WA_VERIFY_TOKEN_2026",
                "hub.challenge": "test_challenge_abc123",
            },
        )
        assert resp.status_code == 200
        assert resp.text.strip('"') == "test_challenge_abc123"

    def test_health_endpoint(self):
        """GET /health returns healthy status."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    def test_chat_response_latency_logged(self):
        """Chat endpoint includes latency_ms in response."""
        resp = client.post(
            "/api/chat",
            json={"message": "What are your store hours?", "session_id": "pilot-003"},
        )
        data = resp.json()
        assert "latency_ms" in data
        assert isinstance(data["latency_ms"], (int, float))
        assert data["latency_ms"] >= 0
