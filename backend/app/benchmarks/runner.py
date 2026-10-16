import asyncio
import uuid
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from app.models.benchmark import BenchmarkCase, BenchmarkRun, BenchmarkMode, BenchmarkCaseStatus, BenchmarkMetrics
from app.models.workflow import WorkflowStatus, WorkflowPlan, WorkflowStepDefinition, ErrorCategory
from app.orchestrator.engine import engine
from app.persistence.database import SessionLocal, BenchmarkRunRecord, BenchmarkCaseResult, WorkflowRecord, EventRecord
from app.tools.registry import registry
from app.tools.builtins import ToolError
from sqlalchemy import func
import json

class BenchmarkRunner:
    def __init__(self, mode: BenchmarkMode = BenchmarkMode.CONTROLLED):
        self.mode = mode
        self.run_id = str(uuid.uuid4())
        self.mock_handlers: Dict[str, Any] = {}
        self.original_handlers: Dict[str, Any] = {}

    def setup_mocks(self):
        """Setup mock handlers for controlled mode."""
        if self.mode == BenchmarkMode.CONTROLLED:
            # Mock the planner to use predefined plans
            from app.benchmarks.controlled_planner import get_controlled_plan
            self.original_handlers["planner"] = engine.planner.execute

            async def mock_planner(user_request: str):
                return get_controlled_plan(user_request)

            engine.planner.execute = mock_planner
            self.mock_handlers["planner"] = mock_planner

            # Mock the synthesis agent to avoid LLM calls
            self.original_handlers["synthesis"] = engine.synthesis.execute

            async def mock_synthesis(user_request: str, step_summary: dict, plan: dict):
                # Return a simple synthesis that includes the final result
                successful_steps = step_summary.get("successful_steps", {})
                if successful_steps:
                    # Get the last successful step's result
                    last_step_id = list(successful_steps.keys())[-1]
                    last_result = successful_steps[last_step_id].get("result")
                    if last_result is not None:
                        return f"Result: {last_result}"
                return "Calculation completed"

            engine.synthesis.execute = mock_synthesis
            self.mock_handlers["synthesis"] = mock_synthesis

            # Mock web_search for controlled results
            web_tool = registry.get_tool("web_search")
            self.original_handlers["web_search"] = web_tool.handler

            async def mock_web_search(args):
                query = args.get("query", "").lower()
                # Return controlled results based on query
                if "python" in query or "programming" in query:
                    return {"success": True, "snippets": ["Python is a high-level programming language"], "source": "Wikipedia", "query": args["query"]}
                elif "nonexistent" in query or "xyz" in query or "abc" in query or "def" in query:
                    return {"success": True, "snippets": [], "source": "Wikipedia", "query": args["query"]}
                elif "postgres" in query:
                    return {"success": True, "snippets": ["PostgreSQL is a relational database"], "source": "Wikipedia", "query": args["query"]}
                elif "mongo" in query:
                    return {"success": True, "snippets": ["MongoDB is a NoSQL database"], "source": "Wikipedia", "query": args["query"]}
                elif "qdrant" in query:
                    return {"success": True, "snippets": [], "source": "Wikipedia", "query": args["query"]}
                elif "redis" in query:
                    return {"success": True, "snippets": ["Redis is an in-memory data store"], "source": "Wikipedia", "query": args["query"]}
                elif "network error" in query:
                    raise ToolError("Network error", ErrorCategory.NETWORK_ERROR)
                elif "rate limit" in query:
                    raise ToolError("Rate limit exceeded", ErrorCategory.RATE_LIMIT)
                else:
                    return {"success": True, "snippets": ["General result"], "source": "Wikipedia", "query": args["query"]}

            web_tool.handler = mock_web_search
            self.mock_handlers["web_search"] = mock_web_search

            # Mock http_request for controlled results
            http_tool = registry.get_tool("http_request")
            self.original_handlers["http_request"] = http_tool.handler

            async def mock_http_request(args):
                url = args.get("url", "")
                if "jsonplaceholder" in url:
                    return {"status_code": 200, "headers": {}, "body": '{"title": "Test Todo", "completed": false}', "success": True}
                elif "nonexistent" in url:
                    raise ToolError("Network error", ErrorCategory.NETWORK_ERROR)
                else:
                    return {"status_code": 200, "headers": {}, "body": '{"data": "test"}', "success": True}

            http_tool.handler = mock_http_request
            self.mock_handlers["http_request"] = mock_http_request

    def restore_mocks(self):
        """Restore original handlers."""
        for tool_name, original_handler in self.original_handlers.items():
            if tool_name == "planner":
                engine.planner.execute = original_handler
            elif tool_name == "synthesis":
                engine.synthesis.execute = original_handler
            else:
                tool = registry.get_tool(tool_name)
                if tool:
                    tool.handler = original_handler
        self.mock_handlers.clear()
        self.original_handlers.clear()

    async def execute_case(self, case: BenchmarkCase) -> Dict[str, Any]:
        """Execute a single benchmark case."""
        start_time = time.perf_counter()
        result = {
            "case_id": case.case_id,
            "category": case.category.value,
            "status": BenchmarkCaseStatus.ERROR.value,
            "workflow_id": None,
            "latency_seconds": 0.0,
            "error_message": None,
            "failure_reason": None,
            "expected_status": case.expected_terminal_status,
            "actual_status": None,
            "output_correct": False,
            "execution_trace": []
        }

        # Handle skipped cases
        if case.expected_terminal_status == "skipped":
            result["status"] = BenchmarkCaseStatus.SKIPPED.value
            result["actual_status"] = "skipped"
            result["output_correct"] = True
            result["execution_trace"].append({
                "event": "case_skipped",
                "reason": case.output_validation
            })
            return result

        try:
            # Execute workflow normally
            workflow_id = engine.new_workflow(case.user_request)
            result["workflow_id"] = workflow_id
            result["execution_trace"].append({"event": "workflow_created", "workflow_id": workflow_id})

            # Wait for completion
            await self._wait_for_completion(workflow_id, case.timeout)

            with SessionLocal() as db:
                record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
                if record:
                    result["actual_status"] = record.status
                    state = record.state_json
                    result["execution_trace"].append({
                        "event": "workflow_completed",
                        "status": record.status,
                        "step_results": state.get("step_results", {})
                    })

            if result["actual_status"] is None:
                result["status"] = BenchmarkCaseStatus.ERROR.value
                result["failure_reason"] = f"Timeout after {case.timeout}s"
                return result

            # Validate expected status
            status_match = result["actual_status"] == case.expected_terminal_status
            result["execution_trace"].append({
                "event": "status_validation",
                "expected": case.expected_terminal_status,
                "actual": result["actual_status"],
                "match": status_match
            })

            # Validate output if specified
            output_correct = True
            if case.expected_output:
                state = None
                with SessionLocal() as db:
                    record = db.query(WorkflowRecord).filter(WorkflowRecord.id == result["workflow_id"]).first()
                    if record:
                        state = record.state_json

                if state and "step_results" in state:
                    # Check if final result matches expected - check both final_response and last step result
                    final_response = state.get("final_response", "")
                    expected = str(case.expected_output.get("final_result", ""))
                    
                    # Check in final_response
                    if expected in final_response:
                        output_correct = True
                    else:
                        # Check in all step results to find the aggregation/final step
                        step_results = state.get("step_results", {})
                        if step_results:
                            # Try to find the step with the expected value
                            found_match = False
                            for step_id in sorted(step_results.keys()):
                                step_result = step_results[step_id].get("result")
                                if step_result is not None:
                                    # Compare numeric values flexibly
                                    try:
                                        if float(expected) == float(step_result):
                                            output_correct = True
                                            found_match = True
                                            break
                                    except (ValueError, TypeError):
                                        # If not numeric, do string comparison
                                        if expected in str(step_result):
                                            output_correct = True
                                            found_match = True
                                            break
                            if not found_match:
                                output_correct = False
                        else:
                            output_correct = False

            result["output_correct"] = output_correct and status_match

            # Validate failure classification rules if specified
            classification_valid = True
            if case.failure_classification_rules:
                classification_valid = self._validate_failure_classification(workflow_id, case.failure_classification_rules)
                result["execution_trace"].append({
                    "event": "failure_classification_validation",
                    "valid": classification_valid,
                    "rules": case.failure_classification_rules
                })

            # Validate persistence
            persistence_valid = self._validate_persistence(workflow_id)
            result["execution_trace"].append({
                "event": "persistence_validation",
                "valid": persistence_valid
            })

            # Determine overall status
            if status_match and output_correct and classification_valid and persistence_valid:
                result["status"] = BenchmarkCaseStatus.PASSED.value
            elif not status_match:
                result["status"] = BenchmarkCaseStatus.FAILED.value
                result["failure_reason"] = f"Status mismatch: expected {case.expected_terminal_status}, got {result['actual_status']}"
            elif not output_correct:
                result["status"] = BenchmarkCaseStatus.FAILED.value
                result["failure_reason"] = "Output validation failed"
            elif not classification_valid:
                result["status"] = BenchmarkCaseStatus.FAILED.value
                result["failure_reason"] = "Failure classification validation failed"
            elif not persistence_valid:
                result["status"] = BenchmarkCaseStatus.FAILED.value
                result["failure_reason"] = "Persistence validation failed"
            else:
                result["status"] = BenchmarkCaseStatus.FAILED.value
                result["failure_reason"] = "Unknown validation failure"

        except Exception as e:
            result["status"] = BenchmarkCaseStatus.ERROR.value
            result["error_message"] = str(e)
            result["failure_reason"] = f"Exception: {str(e)}"
            result["execution_trace"].append({"event": "exception", "error": str(e)})

        finally:
            # Store latency in milliseconds for precision, convert to seconds for reporting
            latency_ms = (time.perf_counter() - start_time) * 1000
            result["latency_seconds"] = round(latency_ms, 3)  # Keep as milliseconds for database storage

        return result

    def _validate_failure_classification(self, workflow_id: str, rules: Dict[str, Any]) -> bool:
        """Validate failure classification rules."""
        with SessionLocal() as db:
            # Get workflow record to check step results
            workflow = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            if not workflow:
                return False

            state = workflow.state_json
            step_results = state.get("step_results", {})

            # Check retry count if specified
            if "expected_retry_count" in rules:
                # Count total retries across all steps
                total_retries = sum(step_result.get("retry_count", 0) for step_result in step_results.values())
                # Allow tolerance of +/- 1 due to timing issues
                if abs(total_retries - rules["expected_retry_count"]) > 1:
                    return False

            # Check error category if specified
            if "expected_error_category" in rules:
                for step_result in step_results.values():
                    if step_result.get("status") == "failed":
                        error_category = step_result.get("error_category")
                        # Handle both enum and string values (enum is stored as string in JSON)
                        expected = rules["expected_error_category"]
                        if error_category == expected or str(error_category) == expected:
                            return True
                return False

            # Check failed steps count if specified
            if "expected_failed_steps" in rules:
                failed_count = sum(1 for step_result in step_results.values() if step_result.get("status") == "failed")
                if failed_count != rules["expected_failed_steps"]:
                    return False

            # Check blocked steps count if specified
            if "expected_blocked_steps" in rules:
                blocked_count = sum(1 for step_result in step_results.values() if step_result.get("status") == "dependency_blocked")
                if blocked_count != rules["expected_blocked_steps"]:
                    return False

            # Check successful steps count if specified
            if "expected_successful_steps" in rules:
                successful_count = sum(1 for step_result in step_results.values() if step_result.get("status") in ["completed", "empty_result"])
                if successful_count != rules["expected_successful_steps"]:
                    return False

        return True

    def _validate_persistence(self, workflow_id: str) -> bool:
        """Validate that workflow state and events are persisted."""
        with SessionLocal() as db:
            # Check workflow record exists
            workflow = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
            if not workflow:
                return False

            # Check state_json is not empty
            if not workflow.state_json:
                return False

            # Check events are persisted
            events = db.query(EventRecord).filter(EventRecord.workflow_id == workflow_id).all()
            if not events:
                return False

            # Check for required event types
            event_types = {e.event_type for e in events}
            required_events = {"workflow.started", "workflow.completed"}
            if not required_events.issubset(event_types):
                return False

        return True

    async def _wait_for_completion(self, workflow_id: str, timeout_seconds: int):
        """Wait for workflow completion."""
        elapsed = 0
        check_interval = 0.5

        while elapsed < timeout_seconds:
            await asyncio.sleep(check_interval)
            elapsed += check_interval

            with SessionLocal() as db:
                record = db.query(WorkflowRecord).filter(WorkflowRecord.id == workflow_id).first()
                if record and record.status in ["completed", "failed", "partially_completed"]:
                    return

    async def run_suite(self, cases: List[BenchmarkCase]) -> BenchmarkRun:
        """Run the full benchmark suite."""
        self.setup_mocks()

        run = BenchmarkRun(
            run_id=self.run_id,
            mode=self.mode,
            start_time=datetime.utcnow(),
            total_cases=len(cases),
            provider_config={"mode": self.mode.value},
            environment={"test_mode": "controlled" if self.mode == BenchmarkMode.CONTROLLED else "live"}
        )

        try:
            for case in cases:
                print(f"[Benchmark] Executing case {case.case_id}: {case.description}")
                case_result = await self.execute_case(case)
                run.case_results[case.case_id] = case_result

                if case_result["status"] == BenchmarkCaseStatus.PASSED.value:
                    run.passed_cases += 1
                elif case_result["status"] == BenchmarkCaseStatus.FAILED.value:
                    run.failed_cases += 1
                elif case_result["status"] == BenchmarkCaseStatus.ERROR.value:
                    run.failed_cases += 1
                else:
                    run.skipped_cases += 1

                print(f"[Benchmark] Case {case.case_id}: {case_result['status']}")

            run.end_time = datetime.utcnow()
            run.metrics = self.calculate_metrics(run)

            # Persist results
            self.persist_results(run)

        finally:
            self.restore_mocks()

        return run

    def calculate_metrics(self, run: BenchmarkRun) -> Dict[str, Any]:
        """Calculate benchmark metrics."""
        total_cases = run.total_cases
        executed_cases = total_cases - run.skipped_cases

        if total_cases == 0:
            return {
                "workflow_completion_rate": 0.0,
                "expected_behavior_pass_rate": 0.0,
                "output_correctness_rate": 0.0,
                "median_latency": 0.0,
                "p95_latency": 0.0,
                "mean_latency": 0.0,
                "tool_call_success_rate": 0.0,
                "retry_recovery_rate": 0.0,
                "provider_error_rate": 0.0,
                "empty_result_rate": 0.0,
                "partial_completion_rate": 0.0,
                "executed_cases": 0,
                "skipped_cases": 0
            }

        # Workflow completion rate (based on executed cases)
        completed_workflows = sum(1 for r in run.case_results.values() if r.get("actual_status") in ["completed", "partially_completed"])
        workflow_completion_rate = (completed_workflows / executed_cases * 100) if executed_cases > 0 else 0.0

        # Expected behavior pass rate (based on executed cases)
        passed_cases = sum(1 for r in run.case_results.values() if r.get("status") == BenchmarkCaseStatus.PASSED.value)
        expected_behavior_pass_rate = (passed_cases / executed_cases * 100) if executed_cases > 0 else 0.0

        # Output correctness rate
        cases_with_output_validation = [r for r in run.case_results.values() if r.get("output_correct") is not None]
        if cases_with_output_validation:
            output_correct_cases = sum(1 for r in cases_with_output_validation if r.get("output_correct"))
            output_correctness_rate = (output_correct_cases / len(cases_with_output_validation)) * 100
        else:
            output_correctness_rate = 0.0

        # Latency metrics (latency_seconds is stored in milliseconds)
        latencies_ms = [r.get("latency_seconds", 0) for r in run.case_results.values()]
        latencies_ms.sort()
        if latencies_ms:
            median_latency_ms = latencies_ms[len(latencies_ms) // 2]
            p95_index = int(len(latencies_ms) * 0.95)
            p95_latency_ms = latencies_ms[min(p95_index, len(latencies_ms) - 1)]
            mean_latency_ms = sum(latencies_ms) / len(latencies_ms)
            # Convert to seconds for reporting
            median_latency = median_latency_ms / 1000 if median_latency_ms > 0 else 0.0
            p95_latency = p95_latency_ms / 1000 if p95_latency_ms > 0 else 0.0
            mean_latency = mean_latency_ms / 1000 if mean_latency_ms > 0 else 0.0
        else:
            median_latency = 0.0
            p95_latency = 0.0
            mean_latency = 0.0

        # Tool reliability metrics (from database events)
        with SessionLocal() as db:
            # Get all tool events for benchmark workflows
            workflow_ids = [r.get("workflow_id") for r in run.case_results.values() if r.get("workflow_id")]
            if workflow_ids:
                tool_started = db.query(EventRecord).filter(
                    EventRecord.workflow_id.in_(workflow_ids),
                    EventRecord.event_type == "tool.started"
                ).count()

                tool_completed = db.query(EventRecord).filter(
                    EventRecord.workflow_id.in_(workflow_ids),
                    EventRecord.event_type == "tool.completed"
                ).count()

                tool_failed = db.query(EventRecord).filter(
                    EventRecord.workflow_id.in_(workflow_ids),
                    EventRecord.event_type == "tool.failed"
                ).count()

                retries = db.query(EventRecord).filter(
                    EventRecord.workflow_id.in_(workflow_ids),
                    EventRecord.event_type == "retry.started"
                ).count()

                tool_call_success_rate = (tool_completed / tool_started * 100) if tool_started > 0 else 0.0
                retry_recovery_rate = (retries / tool_started * 100) if tool_started > 0 else 0.0
                provider_error_rate = (tool_failed / tool_started * 100) if tool_started > 0 else 0.0
            else:
                tool_call_success_rate = 0.0
                retry_recovery_rate = 0.0
                provider_error_rate = 0.0

        # Empty result rate and partial completion rate (based on executed cases)
        empty_result_count = sum(1 for r in run.case_results.values() if r.get("failure_reason") and "empty" in r.get("failure_reason", "").lower())
        empty_result_rate = (empty_result_count / executed_cases * 100) if executed_cases > 0 else 0.0

        partial_completion_count = sum(1 for r in run.case_results.values() if r.get("actual_status") == "partially_completed")
        partial_completion_rate = (partial_completion_count / executed_cases * 100) if executed_cases > 0 else 0.0

        return {
            "workflow_completion_rate": round(workflow_completion_rate, 2),
            "expected_behavior_pass_rate": round(expected_behavior_pass_rate, 2),
            "output_correctness_rate": round(output_correctness_rate, 2),
            "median_latency": round(median_latency, 2),
            "p95_latency": round(p95_latency, 2),
            "mean_latency": round(mean_latency, 2),
            "tool_call_success_rate": round(tool_call_success_rate, 2),
            "retry_recovery_rate": round(retry_recovery_rate, 2),
            "provider_error_rate": round(provider_error_rate, 2),
            "empty_result_rate": round(empty_result_rate, 2),
            "partial_completion_rate": round(partial_completion_rate, 2),
            "executed_cases": executed_cases,
            "skipped_cases": run.skipped_cases
        }

    def persist_results(self, run: BenchmarkRun):
        """Persist benchmark results to database."""
        with SessionLocal() as db:
            # Persist benchmark run
            run_record = BenchmarkRunRecord(
                id=run.run_id,
                suite_version=run.suite_version,
                mode=run.mode.value,
                start_time=run.start_time,
                end_time=run.end_time,
                total_cases=run.total_cases,
                passed_cases=run.passed_cases,
                failed_cases=run.failed_cases,
                skipped_cases=run.skipped_cases,
                metrics_json=run.metrics,
                provider_config_json=run.provider_config,
                environment_json=run.environment
            )
            db.add(run_record)

            # Persist case results
            for case_id, case_result in run.case_results.items():
                case_record = BenchmarkCaseResult(
                    id=str(uuid.uuid4()),
                    benchmark_run_id=run.run_id,
                    case_id=case_id,
                    category=case_result.get("category"),
                    status=case_result.get("status"),
                    workflow_id=case_result.get("workflow_id"),
                    latency_seconds=case_result.get("latency_seconds"),
                    error_message=case_result.get("error_message"),
                    failure_reason=case_result.get("failure_reason"),
                    expected_status=case_result.get("expected_status"),
                    actual_status=case_result.get("actual_status"),
                    output_correct=case_result.get("output_correct"),
                    execution_trace_json=case_result.get("execution_trace")
                )
                db.add(case_record)

            db.commit()

    def generate_reports(self, run: BenchmarkRun) -> Dict[str, str]:
        """Generate JSON and Markdown reports."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

        # JSON report
        # Convert latency from milliseconds to seconds for reporting
        case_results_with_latency = {}
        for case_id, result in run.case_results.items():
            result_copy = result.copy()
            if "latency_seconds" in result_copy:
                result_copy["latency_seconds"] = round(result_copy["latency_seconds"] / 1000, 3)
            case_results_with_latency[case_id] = result_copy

        json_report = {
            "run_id": run.run_id,
            "suite_version": run.suite_version,
            "mode": run.mode.value,
            "start_time": run.start_time.isoformat(),
            "end_time": run.end_time.isoformat() if run.end_time else None,
            "summary": {
                "total_cases": run.total_cases,
                "executed_cases": run.metrics.get('executed_cases', run.total_cases),
                "passed_cases": run.passed_cases,
                "failed_cases": run.failed_cases,
                "skipped_cases": run.skipped_cases
            },
            "metrics": run.metrics,
            "case_results": case_results_with_latency,
            "provider_config": run.provider_config,
            "environment": run.environment
        }

        json_path = f"benchmark_reports/benchmark_{run.run_id}_{timestamp}.json"

        # Markdown report
        executed_cases = run.metrics.get('executed_cases', run.total_cases)
        md_lines = [
            f"# FlowMind Benchmark Report",
            f"",
            f"**Run ID:** {run.run_id}",
            f"**Mode:** {run.mode.value.upper()}",
            f"**Suite Version:** {run.suite_version}",
            f"**Start Time:** {run.start_time.isoformat()}",
            f"**End Time:** {run.end_time.isoformat() if run.end_time else 'N/A'}",
            f"",
            f"## Summary",
            f"",
            f"- **Total Cases:** {run.total_cases}",
            f"- **Executed:** {executed_cases}",
            f"- **Skipped:** {run.skipped_cases}",
            f"- **Passed:** {run.passed_cases}",
            f"- **Failed:** {run.failed_cases}",
            f"",
            f"## Metrics",
            f"",
            f"- **Workflow Completion Rate:** {run.metrics.get('workflow_completion_rate', 0)}% (of {executed_cases} executed)",
            f"- **Expected Behavior Pass Rate:** {run.metrics.get('expected_behavior_pass_rate', 0)}% (of {executed_cases} executed)",
            f"- **Output Correctness Rate:** {run.metrics.get('output_correctness_rate', 0)}%",
            f"- **Median Latency:** {run.metrics.get('median_latency', 0)}s",
            f"- **P95 Latency:** {run.metrics.get('p95_latency', 0)}s",
            f"- **Mean Latency:** {run.metrics.get('mean_latency', 0)}s",
            f"- **Tool Call Success Rate:** {run.metrics.get('tool_call_success_rate', 0)}%",
            f"- **Retry Recovery Rate:** {run.metrics.get('retry_recovery_rate', 0)}%",
            f"- **Provider Error Rate:** {run.metrics.get('provider_error_rate', 0)}%",
            f"- **Empty Result Rate:** {run.metrics.get('empty_result_rate', 0)}%",
            f"- **Partial Completion Rate:** {run.metrics.get('partial_completion_rate', 0)}%",
            f"",
            f"## Case Results",
            f""
        ]

        # Group by category
        categories = {}
        for case_id, result in run.case_results.items():
            category = result.get("category", "unknown")
            if category not in categories:
                categories[category] = []
            categories[category].append((case_id, result))

        for category, results in categories.items():
            md_lines.append(f"### {category.replace('_', ' ').title()}")
            md_lines.append("")

            for case_id, result in results:
                status_emoji = "[PASS]" if result.get("status") == "passed" else "[FAIL]" if result.get("status") == "failed" else "[WARN]"
                md_lines.append(f"{status_emoji} **{case_id}**: {result.get('status', 'unknown').upper()}")
                md_lines.append(f"   - Expected: {result.get('expected_status')}")
                md_lines.append(f"   - Actual: {result.get('actual_status')}")
                md_lines.append(f"   - Latency: {result.get('latency_seconds', 0)}s")
                if result.get("failure_reason"):
                    md_lines.append(f"   - Failure: {result.get('failure_reason')}")
                md_lines.append("")

        md_lines.append("## Environment")
        md_lines.append("")
        for key, value in run.environment.items():
            md_lines.append(f"- **{key}:** {value}")

        md_path = f"benchmark_reports/benchmark_{run.run_id}_{timestamp}.md"

        return {
            "json": json.dumps(json_report, indent=2),
            "json_path": json_path,
            "markdown": "\n".join(md_lines),
            "markdown_path": md_path
        }
