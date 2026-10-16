from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from app.persistence.database import SessionLocal, BenchmarkRunRecord, BenchmarkCaseResult
from sqlalchemy import func, desc
import json

router = APIRouter()

@router.get("/benchmark/runs")
def list_benchmark_runs(limit: int = 20):
    """List recent benchmark runs."""
    with SessionLocal() as db:
        runs = db.query(BenchmarkRunRecord).order_by(desc(BenchmarkRunRecord.start_time)).limit(limit).all()
        return [{
            "run_id": r.id,
            "suite_version": r.suite_version,
            "mode": r.mode,
            "start_time": r.start_time.isoformat(),
            "end_time": r.end_time.isoformat() if r.end_time else None,
            "total_cases": r.total_cases,
            "passed_cases": r.passed_cases,
            "failed_cases": r.failed_cases,
            "skipped_cases": r.skipped_cases,
            "metrics": r.metrics_json
        } for r in runs]

@router.get("/benchmark/runs/{run_id}")
def get_benchmark_run(run_id: str):
    """Get details of a specific benchmark run."""
    with SessionLocal() as db:
        run = db.query(BenchmarkRunRecord).filter(BenchmarkRunRecord.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Benchmark run not found")

        return {
            "run_id": run.id,
            "suite_version": run.suite_version,
            "mode": run.mode,
            "start_time": run.start_time.isoformat(),
            "end_time": run.end_time.isoformat() if run.end_time else None,
            "total_cases": run.total_cases,
            "passed_cases": run.passed_cases,
            "failed_cases": run.failed_cases,
            "skipped_cases": run.skipped_cases,
            "metrics": run.metrics_json,
            "provider_config": run.provider_config_json,
            "environment": run.environment_json
        }

@router.get("/benchmark/runs/{run_id}/cases")
def get_benchmark_run_cases(run_id: str):
    """Get case results for a specific benchmark run."""
    with SessionLocal() as db:
        cases = db.query(BenchmarkCaseResult).filter(BenchmarkCaseResult.benchmark_run_id == run_id).all()
        return [{
            "case_id": c.case_id,
            "category": c.category,
            "status": c.status,
            "workflow_id": c.workflow_id,
            "latency_seconds": round(c.latency_seconds / 1000, 3) if c.latency_seconds else 0,  # Convert ms to seconds
            "error_message": c.error_message,
            "failure_reason": c.failure_reason,
            "expected_status": c.expected_status,
            "actual_status": c.actual_status,
            "output_correct": c.output_correct,
            "execution_trace": c.execution_trace_json
        } for c in cases]

@router.get("/benchmark/metrics/summary")
def get_benchmark_metrics_summary():
    """Get summary metrics across all benchmark runs, separated by mode."""
    with SessionLocal() as db:
        # Overall summary
        total_runs = db.query(BenchmarkRunRecord).count()
        if total_runs == 0:
            return {
                "total_runs": 0,
                "controlled": None,
                "live": None
            }

        # Controlled mode summary
        controlled_runs = db.query(BenchmarkRunRecord).filter(BenchmarkRunRecord.mode == "controlled").all()
        controlled_summary = None
        if controlled_runs:
            total_cases = sum(r.total_cases for r in controlled_runs)
            total_passed = sum(r.passed_cases for r in controlled_runs)
            avg_pass_rate = (total_passed / total_cases * 100) if total_cases > 0 else 0

            avg_metrics = {}
            metric_keys = ["workflow_completion_rate", "expected_behavior_pass_rate", "output_correctness_rate", "median_latency"]
            for key in metric_keys:
                values = [r.metrics_json.get(key, 0) for r in controlled_runs if r.metrics_json]
                if values:
                    avg_metrics[key] = sum(values) / len(values)

            controlled_summary = {
                "total_runs": len(controlled_runs),
                "total_cases": total_cases,
                "total_passed": total_passed,
                "average_pass_rate": round(avg_pass_rate, 2),
                "average_metrics": {k: round(v, 2) for k, v in avg_metrics.items()}
            }

        # Live mode summary
        live_runs = db.query(BenchmarkRunRecord).filter(BenchmarkRunRecord.mode == "live").all()
        live_summary = None
        if live_runs:
            total_cases = sum(r.total_cases for r in live_runs)
            total_passed = sum(r.passed_cases for r in live_runs)
            avg_pass_rate = (total_passed / total_cases * 100) if total_cases > 0 else 0

            avg_metrics = {}
            metric_keys = ["workflow_completion_rate", "expected_behavior_pass_rate", "output_correctness_rate", "median_latency"]
            for key in metric_keys:
                values = [r.metrics_json.get(key, 0) for r in live_runs if r.metrics_json]
                if values:
                    avg_metrics[key] = sum(values) / len(values)

            live_summary = {
                "total_runs": len(live_runs),
                "total_cases": total_cases,
                "total_passed": total_passed,
                "average_pass_rate": round(avg_pass_rate, 2),
                "average_metrics": {k: round(v, 2) for k, v in avg_metrics.items()}
            }

        return {
            "total_runs": total_runs,
            "controlled": controlled_summary,
            "live": live_summary
        }

@router.get("/benchmark/metrics/category-breakdown")
def get_benchmark_category_breakdown(run_id: Optional[str] = None):
    """Get category-wise breakdown, optionally for a specific run."""
    with SessionLocal() as db:
        query = db.query(BenchmarkCaseResult)
        if run_id:
            query = query.filter(BenchmarkCaseResult.benchmark_run_id == run_id)

        cases = query.all()

        breakdown = {}
        for case in cases:
            category = case.category
            if category not in breakdown:
                breakdown[category] = {
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "error": 0
                }
            breakdown[category]["total"] += 1
            if case.status == "passed":
                breakdown[category]["passed"] += 1
            elif case.status == "failed":
                breakdown[category]["failed"] += 1
            elif case.status == "error":
                breakdown[category]["error"] += 1

        return breakdown
