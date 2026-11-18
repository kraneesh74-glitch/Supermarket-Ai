"""Manager Analytics & Weekly Report API Routes (Task 6.2).

Provides:
- GET /api/reports/weekly  — Generate & return the weekly manager insight report
- GET /api/reports/weekly/download — Download the last generated JSON report file
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse

from apps.agent.report_generator import ManagerReportGenerator
from apps.agent.audit_logger import LOGS_DIR

router = APIRouter(prefix="/api/reports", tags=["Manager Analytics"])


@router.get("/weekly")
async def get_weekly_report():
    """Generate and return the weekly manager insight report as JSON.

    Aggregates the audit trail (logs/audit_trail.jsonl) and CSAT records
    into a human-readable executive digest for supermarket store managers.
    """
    report = ManagerReportGenerator.generate_report()
    return report


@router.get("/weekly/download")
async def download_weekly_report():
    """Download the most recently generated weekly report as a JSON file."""
    report_path = LOGS_DIR / "weekly_manager_report.json"
    if not report_path.exists():
        # Generate one on-the-fly
        ManagerReportGenerator.generate_report()
    return FileResponse(
        path=str(report_path),
        media_type="application/json",
        filename="weekly_manager_report.json",
    )

