# ABOUTME: Report generation for simulation analytics
# ABOUTME: Creates JSON and summary reports from simulation data

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import json

from database.models import SimulationRun, Tenant
from analytics.aggregations import get_simulation_summary, get_simulation_trends


class ReportGenerator:
    """
    Generates analytics reports for simulation data.
    """

    def __init__(self, db: Session, tenant_id: int):
        self.db = db
        self.tenant_id = tenant_id

    def generate_summary_report(
        self,
        days: int = 30,
        simulation_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive summary report.

        Args:
            days: Number of days to include
            simulation_types: Optional list of simulation types to include

        Returns:
            Dict containing the report
        """
        report = {
            "report_type": "summary",
            "generated_at": datetime.utcnow().isoformat(),
            "period_days": days,
            "tenant_id": self.tenant_id,
            "sections": {}
        }

        # Overall summary
        overall = get_simulation_summary(self.db, self.tenant_id, days=days)
        report["sections"]["overall"] = overall

        # Per-type summaries
        if simulation_types:
            type_summaries = {}
            for sim_type in simulation_types:
                type_summaries[sim_type] = get_simulation_summary(
                    self.db, self.tenant_id,
                    simulation_type=sim_type,
                    days=days
                )
            report["sections"]["by_type"] = type_summaries

        # Recent runs
        recent_runs = self._get_recent_runs(limit=10)
        report["sections"]["recent_runs"] = recent_runs

        return report

    def generate_performance_report(
        self,
        simulation_type: str,
        metrics: List[str],
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate a performance trend report for specific metrics.

        Args:
            simulation_type: Type of simulation
            metrics: List of metrics to analyze
            days: Number of days to include

        Returns:
            Dict containing the report
        """
        report = {
            "report_type": "performance",
            "generated_at": datetime.utcnow().isoformat(),
            "simulation_type": simulation_type,
            "period_days": days,
            "tenant_id": self.tenant_id,
            "metrics": {}
        }

        for metric in metrics:
            trend_data = get_simulation_trends(
                self.db, self.tenant_id,
                simulation_type=simulation_type,
                metric=metric,
                days=days
            )
            report["metrics"][metric] = trend_data

        return report

    def generate_comparison_report(
        self,
        baseline_params: Dict[str, Any],
        variant_params: Dict[str, Any],
        simulation_type: str,
        runs_per_variant: int = 5
    ) -> Dict[str, Any]:
        """
        Generate a comparison report between two parameter configurations.

        Args:
            baseline_params: Baseline simulation parameters
            variant_params: Variant simulation parameters
            simulation_type: Type of simulation
            runs_per_variant: Number of recent runs to include per variant

        Returns:
            Dict containing the comparison report
        """
        report = {
            "report_type": "comparison",
            "generated_at": datetime.utcnow().isoformat(),
            "simulation_type": simulation_type,
            "tenant_id": self.tenant_id,
            "baseline": {
                "parameters": baseline_params,
                "runs": []
            },
            "variant": {
                "parameters": variant_params,
                "runs": []
            }
        }

        # Find matching runs for baseline
        baseline_runs = self._find_matching_runs(
            simulation_type, baseline_params, limit=runs_per_variant
        )
        report["baseline"]["runs"] = baseline_runs

        # Find matching runs for variant
        variant_runs = self._find_matching_runs(
            simulation_type, variant_params, limit=runs_per_variant
        )
        report["variant"]["runs"] = variant_runs

        # Calculate summary statistics
        if baseline_runs and variant_runs:
            report["summary"] = self._compare_run_sets(baseline_runs, variant_runs)

        return report

    def _get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent simulation runs"""
        runs = self.db.query(SimulationRun).filter(
            SimulationRun.tenant_id == self.tenant_id
        ).order_by(SimulationRun.created_at.desc()).limit(limit).all()

        return [
            {
                "id": run.id,
                "simulation_type": run.simulation_type,
                "status": run.status,
                "duration_seconds": run.duration_seconds,
                "created_at": run.created_at.isoformat() if run.created_at else None
            }
            for run in runs
        ]

    def _find_matching_runs(
        self,
        simulation_type: str,
        params: Dict[str, Any],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find runs with matching parameters"""
        runs = self.db.query(SimulationRun).filter(
            SimulationRun.tenant_id == self.tenant_id,
            SimulationRun.simulation_type == simulation_type,
            SimulationRun.status == "completed"
        ).order_by(SimulationRun.created_at.desc()).limit(limit * 10).all()

        # Filter by matching parameters
        matching = []
        for run in runs:
            if run.parameters == params:
                matching.append({
                    "id": run.id,
                    "results": run.results,
                    "duration_seconds": run.duration_seconds,
                    "created_at": run.created_at.isoformat() if run.created_at else None
                })
                if len(matching) >= limit:
                    break

        return matching

    def _compare_run_sets(
        self,
        baseline_runs: List[Dict],
        variant_runs: List[Dict]
    ) -> Dict[str, Any]:
        """Compare two sets of runs and calculate differences"""
        # Extract common metrics
        all_metrics = set()
        for run in baseline_runs + variant_runs:
            if run.get("results"):
                all_metrics.update(run["results"].keys())

        comparisons = {}
        for metric in all_metrics:
            baseline_values = [
                r["results"][metric]
                for r in baseline_runs
                if r.get("results") and metric in r["results"]
                and isinstance(r["results"][metric], (int, float))
            ]
            variant_values = [
                r["results"][metric]
                for r in variant_runs
                if r.get("results") and metric in r["results"]
                and isinstance(r["results"][metric], (int, float))
            ]

            if baseline_values and variant_values:
                baseline_avg = sum(baseline_values) / len(baseline_values)
                variant_avg = sum(variant_values) / len(variant_values)
                diff = variant_avg - baseline_avg
                pct_change = (diff / baseline_avg * 100) if baseline_avg != 0 else 0

                comparisons[metric] = {
                    "baseline_avg": round(baseline_avg, 4),
                    "variant_avg": round(variant_avg, 4),
                    "difference": round(diff, 4),
                    "percent_change": round(pct_change, 2)
                }

        return comparisons
