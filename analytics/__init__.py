# ABOUTME: Analytics package for simulation reporting and aggregations
# ABOUTME: Exports aggregation functions and report generators

from analytics.aggregations import (
    get_simulation_summary,
    compare_simulation_runs,
    get_simulation_trends
)
from analytics.reports import ReportGenerator

__all__ = [
    "get_simulation_summary",
    "compare_simulation_runs",
    "get_simulation_trends",
    "ReportGenerator",
]
