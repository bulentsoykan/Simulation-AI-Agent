# ABOUTME: Database aggregation queries for simulation analytics
# ABOUTME: Provides summary statistics, comparisons, and trend analysis

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from database.models import SimulationRun


def get_simulation_summary(
    db: Session,
    tenant_id: int,
    simulation_type: Optional[str] = None,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get summary statistics for simulation runs.

    Args:
        db: Database session
        tenant_id: Tenant ID for filtering
        simulation_type: Optional filter by simulation type
        days: Number of days to look back

    Returns:
        Dict with summary statistics
    """
    since = datetime.utcnow() - timedelta(days=days)

    query = db.query(SimulationRun).filter(
        SimulationRun.tenant_id == tenant_id,
        SimulationRun.created_at >= since
    )

    if simulation_type:
        query = query.filter(SimulationRun.simulation_type == simulation_type)

    runs = query.all()

    if not runs:
        return {
            "total_runs": 0,
            "by_type": {},
            "by_status": {},
            "avg_duration_seconds": None,
            "period_days": days
        }

    # Count by type
    by_type = {}
    for run in runs:
        by_type[run.simulation_type] = by_type.get(run.simulation_type, 0) + 1

    # Count by status
    by_status = {}
    for run in runs:
        by_status[run.status] = by_status.get(run.status, 0) + 1

    # Average duration
    durations = [r.duration_seconds for r in runs if r.duration_seconds is not None]
    avg_duration = sum(durations) / len(durations) if durations else None

    return {
        "total_runs": len(runs),
        "by_type": by_type,
        "by_status": by_status,
        "avg_duration_seconds": round(avg_duration, 2) if avg_duration else None,
        "period_days": days
    }


def compare_simulation_runs(
    db: Session,
    tenant_id: int,
    run_ids: List[int]
) -> Dict[str, Any]:
    """
    Compare multiple simulation runs.

    Args:
        db: Database session
        tenant_id: Tenant ID for validation
        run_ids: List of simulation run IDs to compare

    Returns:
        Dict with comparison data
    """
    runs = db.query(SimulationRun).filter(
        SimulationRun.tenant_id == tenant_id,
        SimulationRun.id.in_(run_ids)
    ).all()

    if not runs:
        return {"error": "No runs found", "comparisons": []}

    comparisons = []
    for run in runs:
        comparisons.append({
            "id": run.id,
            "simulation_type": run.simulation_type,
            "parameters": run.parameters,
            "results": run.results,
            "duration_seconds": run.duration_seconds,
            "created_at": run.created_at.isoformat() if run.created_at else None
        })

    # Find common metrics to compare
    common_metrics = set()
    for run in runs:
        if run.results:
            if not common_metrics:
                common_metrics = set(run.results.keys())
            else:
                common_metrics &= set(run.results.keys())

    return {
        "runs": comparisons,
        "common_metrics": list(common_metrics),
        "count": len(comparisons)
    }


def get_simulation_trends(
    db: Session,
    tenant_id: int,
    simulation_type: str,
    metric: str,
    days: int = 30,
    granularity: str = "day"
) -> Dict[str, Any]:
    """
    Get trend data for a specific metric over time.

    Args:
        db: Database session
        tenant_id: Tenant ID for filtering
        simulation_type: Type of simulation
        metric: Metric name to track (e.g., "avg_wait_time")
        days: Number of days to look back
        granularity: "hour", "day", or "week"

    Returns:
        Dict with trend data points
    """
    since = datetime.utcnow() - timedelta(days=days)

    runs = db.query(SimulationRun).filter(
        SimulationRun.tenant_id == tenant_id,
        SimulationRun.simulation_type == simulation_type,
        SimulationRun.status == "completed",
        SimulationRun.created_at >= since
    ).order_by(SimulationRun.created_at).all()

    # Group by granularity
    buckets = {}
    for run in runs:
        if not run.results or metric not in run.results:
            continue

        if granularity == "hour":
            key = run.created_at.strftime("%Y-%m-%d %H:00")
        elif granularity == "week":
            key = run.created_at.strftime("%Y-W%W")
        else:  # day
            key = run.created_at.strftime("%Y-%m-%d")

        if key not in buckets:
            buckets[key] = []
        buckets[key].append(run.results[metric])

    # Calculate averages
    trend_data = []
    for time_key, values in sorted(buckets.items()):
        avg_value = sum(values) / len(values)
        trend_data.append({
            "time": time_key,
            "value": round(avg_value, 4),
            "count": len(values)
        })

    return {
        "simulation_type": simulation_type,
        "metric": metric,
        "granularity": granularity,
        "period_days": days,
        "data_points": trend_data
    }
