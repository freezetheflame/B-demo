"""
Form submission analytics - success rate tracking.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text, case
from datetime import datetime, timedelta
from app.database import get_db
from app.models import SubmissionLog

router = APIRouter()


@router.get("/submit-metrics")
async def get_submit_metrics(
    form_type: str = Query(None),
    start: datetime = Query(None),
    end: datetime = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get form submission success rate statistics."""
    if not start:
        start = datetime.utcnow() - timedelta(days=7)
    if not end:
        end = datetime.utcnow()

    # Build base WHERE conditions as SQL text
    ft_condition = f"AND form_type = '{form_type}'" if form_type else ""

    query_count = text(f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success,
            SUM(CASE WHEN status = 'fail' THEN 1 ELSE 0 END) AS fail,
            AVG(duration_ms) AS avg_duration,
            MIN(duration_ms) AS min_dur,
            MAX(duration_ms) AS max_dur
        FROM submission_logs
        WHERE created_at BETWEEN :start AND :end
        {ft_condition}
    """)
    row = (await db.execute(query_count, {"start": start, "end": end})).one()

    # Fail reasons
    query_fails = text(f"""
        SELECT error_code, COUNT(*) AS cnt
        FROM submission_logs
        WHERE created_at BETWEEN :start AND :end
            AND status = 'fail'
            {ft_condition}
        GROUP BY error_code
        ORDER BY cnt DESC
        LIMIT 10
    """)
    fail_reasons = {}
    for r in (await db.execute(query_fails, {"start": start, "end": end})).all():
        fail_reasons[r.error_code or "unknown"] = r.cnt

    # Hourly trend
    query_trend = text(f"""
        SELECT
            date_trunc('hour', created_at) AS hour,
            COUNT(*) AS total,
            SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count
        FROM submission_logs
        WHERE created_at BETWEEN :start AND :end
            {ft_condition}
        GROUP BY hour
        ORDER BY hour
        LIMIT 168
    """)
    trend_result = await db.execute(query_trend, {"start": start, "end": end})
    trend = [{"hour": r.hour.isoformat(), "total": r.total, "success": r.success_count}
             for r in trend_result]

    success_rate = round(row.success / row.total * 100, 2) if row.total > 0 else 0

    return {
        "total_submits": row.total,
        "success_count": row.success,
        "fail_count": row.fail,
        "success_rate": success_rate,
        "avg_duration_ms": round(row.avg_duration, 2) if row.avg_duration else 0,
        "min_duration_ms": row.min_dur or 0,
        "max_duration_ms": row.max_dur or 0,
        "p50_ms": 0,
        "p99_ms": 0,
        "fail_reasons": fail_reasons,
        "hourly_trend": trend,
        "period": {"start": start.isoformat(), "end": end.isoformat()},
    }


@router.post("/log")
async def log_submission(
    form_type: str,
    merchant_id: str = None,
    status: str = "start",
    duration_ms: int = 0,
    error_code: str = None,
    error_msg: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Record a form submission event."""
    log = SubmissionLog(
        form_type=form_type,
        merchant_id=merchant_id,
        status=status,
        duration_ms=duration_ms,
        error_code=error_code,
        error_msg=error_msg,
    )
    db.add(log)
    return {"status": "logged"}
