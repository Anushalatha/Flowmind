#!/usr/bin/env python3
"""
Benchmark execution CLI.

Usage:
    python -m app.benchmarks.run --mode controlled
    python -m app.benchmarks.run --mode live
"""
import asyncio
import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.benchmarks.suite import ALL_BENCHMARK_CASES
from app.benchmarks.runner import BenchmarkRunner
from app.models.benchmark import BenchmarkMode
from app.persistence.database import init_db
import app.tools.builtins

async def main():
    parser = argparse.ArgumentParser(description="Run FlowMind benchmark suite")
    parser.add_argument("--mode", choices=["controlled", "live"], default="controlled", help="Execution mode")
    parser.add_argument("--category", choices=["sequential", "parallel", "research", "api_data", "failure_recovery", "persistence", "all"], default="all", help="Category to run")
    parser.add_argument("--output-dir", default="benchmark_reports", help="Output directory for reports")

    args = parser.parse_args()

    # Initialize database
    init_db()
    app.tools.builtins.register_builtin_tools()

    # Select cases
    if args.category == "all":
        cases = ALL_BENCHMARK_CASES
    else:
        from app.models.benchmark import BenchmarkCategory
        category_map = {
            "sequential": BenchmarkCategory.SEQUENTIAL,
            "parallel": BenchmarkCategory.PARALLEL,
            "research": BenchmarkCategory.RESEARCH,
            "api_data": BenchmarkCategory.API_DATA,
            "failure_recovery": BenchmarkCategory.FAILURE_RECOVERY,
            "persistence": BenchmarkCategory.PERSISTENCE
        }
        from app.benchmarks.suite import get_cases_by_category
        cases = get_cases_by_category(category_map[args.category])

    mode = BenchmarkMode.CONTROLLED if args.mode == "controlled" else BenchmarkMode.LIVE

    print(f"[Benchmark] Starting {mode.value.upper()} benchmark with {len(cases)} cases")

    runner = BenchmarkRunner(mode=mode)
    run = await runner.run_suite(cases)

    print(f"\n[Benchmark] Run completed: {run.run_id}")
    print(f"[Benchmark] Passed: {run.passed_cases}/{run.total_cases}")
    print(f"[Benchmark] Failed: {run.failed_cases}/{run.total_cases}")
    print(f"[Benchmark] Pass Rate: {run.metrics.get('expected_behavior_pass_rate', 0)}%")

    # Generate reports
    reports = runner.generate_reports(run)

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    # Write reports
    json_path = os.path.join(args.output_dir, os.path.basename(reports["json_path"]))
    md_path = os.path.join(args.output_dir, os.path.basename(reports["markdown_path"]))

    with open(json_path, "w") as f:
        f.write(reports["json"])
    print(f"[Benchmark] JSON report written to: {json_path}")

    with open(md_path, "w") as f:
        f.write(reports["markdown"])
    print(f"[Benchmark] Markdown report written to: {md_path}")

    return run

if __name__ == "__main__":
    asyncio.run(main())
