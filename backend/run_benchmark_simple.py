#!/usr/bin/env python3
"""Simplified benchmark runner - runs a subset of cases with actual planner."""
import asyncio
import os
import sys
from pathlib import Path

# Set environment variables BEFORE any imports
os.environ['DB_URL'] = 'sqlite:///:memory:'

sys.path.insert(0, str(Path(__file__).parent))

from app.benchmarks.suite import get_cases_by_category
from app.benchmarks.runner import BenchmarkRunner
from app.models.benchmark import BenchmarkMode, BenchmarkCategory
from app.persistence.database import init_db
import app.tools.builtins

async def main():
    init_db()
    app.tools.builtins.register_builtin_tools()

    # Run only 1 sequential case for quick test
    cases = [get_cases_by_category(BenchmarkCategory.SEQUENTIAL)[0]]

    print(f"[Benchmark] Running {len(cases)} test case: {cases[0].case_id}")

    runner = BenchmarkRunner(mode=BenchmarkMode.CONTROLLED)
    run = await runner.run_suite(cases)

    print(f"\n[Benchmark] Run completed: {run.run_id}")
    print(f"[Benchmark] Passed: {run.passed_cases}/{run.total_cases}")
    print(f"[Benchmark] Failed: {run.failed_cases}/{run.total_cases}")
    print(f"[Benchmark] Pass Rate: {run.metrics.get('expected_behavior_pass_rate', 0)}%")

    # Generate reports
    reports = runner.generate_reports(run)

    os.makedirs("backend/benchmark_reports", exist_ok=True)

    json_path = os.path.join("backend/benchmark_reports", os.path.basename(reports["json_path"]))
    md_path = os.path.join("backend/benchmark_reports", os.path.basename(reports["markdown_path"]))

    with open(json_path, "w") as f:
        f.write(reports["json"])
    print(f"[Benchmark] JSON report written to: {json_path}")

    with open(md_path, "w") as f:
        f.write(reports["markdown"])
    print(f"[Benchmark] Markdown report written to: {md_path}")

    # Print case results
    print("\n[Benchmark] Case Results:")
    for case_id, result in run.case_results.items():
        print(f"  {case_id}: {result['status']} ({result['actual_status']})")
        if result.get('failure_reason'):
            print(f"    Failure: {result['failure_reason']}")

if __name__ == "__main__":
    asyncio.run(main())
