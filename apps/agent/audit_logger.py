"""Structured Audit Logging Engine (📘 Lesson 7: Safety & Auditing).

Provides an append-only structured audit trail of every conversation turn:
- Shopper query and generated plan
- Every ReAct step (Think, Act, Tool Call arguments, Look/Observation)
- Resolution status (Contained vs. Escalated)
- Escalation tickets and reasons
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"


class AuditEntry(BaseModel):
    audit_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str
    customer_phone: Optional[str] = None
    query: str
    plan_summary: Optional[str] = None
    steps_count: int
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    final_response: str
    contained: bool
    escalated: bool
    escalation_reason: Optional[str] = None
    needs_confirmation: bool = False


class AuditLogger:
    """Manages file-based and in-memory audit logs for compliance and analytics."""

    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or LOGS_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "audit_trail.jsonl"
        self._entries: List[AuditEntry] = []

    def log_turn(self, entry: AuditEntry) -> None:
        """Append audit entry to JSONL log file and in-memory buffer."""
        self._entries.append(entry)

        # Append to disk
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(entry.model_dump_json() + "\n")
        except Exception as e:
            # Fallback print if file write fails
            print(f"[AUDIT LOG ERROR] Failed writing to {self.log_file}: {e}")

    def get_recent_entries(self, limit: int = 50) -> List[AuditEntry]:
        return self._entries[-limit:]

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Calculate containment and escalation metrics from logged events."""
        total = len(self._entries)
        if total == 0:
            return {
                "total_queries": 0,
                "containment_rate": 1.0,
                "escalated_count": 0,
                "needs_confirmation_count": 0,
            }

        contained_count = sum(1 for e in self._entries if e.contained)
        escalated_count = sum(1 for e in self._entries if e.escalated)
        confirm_count = sum(1 for e in self._entries if e.needs_confirmation)

        return {
            "total_queries": total,
            "contained_count": contained_count,
            "containment_rate": round(contained_count / total, 3),
            "escalated_count": escalated_count,
            "escalation_rate": round(escalated_count / total, 3),
            "needs_confirmation_count": confirm_count,
        }

    def clear(self) -> None:
        self._entries.clear()
        if self.log_file.exists():
            self.log_file.unlink()


# Global audit logger singleton
audit_logger = AuditLogger()

