import pytest
import os
import asyncio
from datetime import datetime

# Set test database URL before any imports
os.environ['DB_URL'] = 'sqlite:///:memory:'

from app.models.benchmark import BenchmarkCase, BenchmarkCategory, BenchmarkMode, BenchmarkCaseStatus, BenchmarkMetrics
from app.benchmarks.suite import ALL_BENCHMARK_CASES, get_case_by_id, get_cases_by_category
from app.benchmarks.runner import BenchmarkRunner
from app.persistence.database import init_db, SessionLocal, BenchmarkRunRecord, BenchmarkCaseResult
from app.models.workflow import WorkflowStatus

init_db()

def test_benchmark_suite_size():
    """Test that benchmark suite has exactly 30 cases."""
    assert len(ALL_BENCHMARK_CASES) == 30

def test_benchmark_categories():
    """Test that all 6 categories have exactly 5 cases."""
    categories = {
        BenchmarkCategory.SEQUENTIAL: 5,
        BenchmarkCategory.PARALLEL: 5,
        BenchmarkCategory.RESEARCH: 5,
        BenchmarkCategory.API_DATA: 5,
        BenchmarkCategory.FAILURE_RECOVERY: 5,
        BenchmarkCategory.PERSISTENCE: 5
    }

    for category, expected_count in categories.items():
        cases = get_cases_by_category(category)
        assert len(cases) == expected_count, f"Category {category} should have {expected_count} cases, got {len(cases)}"

def test_benchmark_case_structure():
    """Test that each benchmark case has required fields."""
    for case in ALL_BENCHMARK_CASES:
        assert case.case_id, f"Case missing case_id"
        assert case.category, f"Case {case.case_id} missing category"
        assert case.description, f"Case {case.case_id} missing description"
        assert case.user_request, f"Case {case.case_id} missing user_request"
        assert case.expected_terminal_status, f"Case {case.case_id} missing expected_terminal_status"
        assert case.timeout > 0, f"Case {case.case_id} has invalid timeout"

def test_benchmark_case_ids_unique():
    """Test that all case IDs are unique."""
    case_ids = [case.case_id for case in ALL_BENCHMARK_CASES]
    assert len(case_ids) == len(set(case_ids)), "Case IDs must be unique"

def test_get_case_by_id():
    """Test case lookup by ID."""
    case = get_case_by_id("SEQ_001")
    assert case is not None
    assert case.case_id == "SEQ_001"
    assert case.category == BenchmarkCategory.SEQUENTIAL

    nonexistent = get_case_by_id("NONEXISTENT")
    assert nonexistent is None

def test_benchmark_runner_initialization():
    """Test BenchmarkRunner initialization."""
    runner = BenchmarkRunner(mode=BenchmarkMode.CONTROLLED)
    assert runner.run_id
    assert runner.mode == BenchmarkMode.CONTROLLED
    assert runner.mock_handlers == {}
    assert runner.original_handlers == {}

def test_benchmark_runner_setup_mocks():
    """Test that mock handlers are set up correctly."""
    runner = BenchmarkRunner(mode=BenchmarkMode.CONTROLLED)
    runner.setup_mocks()

    assert "web_search" in runner.mock_handlers
    assert "http_request" in runner.mock_handlers
    assert "web_search" in runner.original_handlers
    assert "http_request" in runner.original_handlers

    runner.restore_mocks()
    assert runner.mock_handlers == {}
    assert runner.original_handlers == {}

def test_benchmark_metrics_zero_denominator():
    """Test metric calculations with zero cases."""
    runner = BenchmarkRunner(mode=BenchmarkMode.CONTROLLED)
    run = runner.calculate_metrics(
        type('obj', (object,), {
            'total_cases': 0,
            'skipped_cases': 0,
            'case_results': {}
        })()
    )

    assert run['workflow_completion_rate'] == 0.0
    assert run['expected_behavior_pass_rate'] == 0.0
    assert run['output_correctness_rate'] == 0.0
    assert run['median_latency'] == 0.0
    assert run['p95_latency'] == 0.0
    assert run['mean_latency'] == 0.0

def test_benchmark_metrics_all_passed():
    """Test metric calculations with all passed cases."""
    runner = BenchmarkRunner(mode=BenchmarkMode.CONTROLLED)
    mock_run = type('obj', (object,), {
        'total_cases': 3,
        'skipped_cases': 0,
        'case_results': {
            'case1': {'status': 'passed', 'actual_status': 'completed', 'latency_seconds': 1000, 'workflow_id': 'wf1'},
            'case2': {'status': 'passed', 'actual_status': 'completed', 'latency_seconds': 2000, 'workflow_id': 'wf2'},
            'case3': {'status': 'passed', 'actual_status': 'completed', 'latency_seconds': 3000, 'workflow_id': 'wf3'}
        }
    })()

    metrics = runner.calculate_metrics(mock_run)

    assert metrics['workflow_completion_rate'] == 100.0
    assert metrics['expected_behavior_pass_rate'] == 100.0
    assert metrics['median_latency'] == 2.0
    assert metrics['mean_latency'] == 2.0

def test_benchmark_persistence():
    """Test that benchmark results can be persisted."""
    runner = BenchmarkRunner(mode=BenchmarkMode.CONTROLLED)

    mock_run = type('obj', (object,), {
        'run_id': 'test-run-123',
        'suite_version': '1.0.0',
        'mode': BenchmarkMode.CONTROLLED,
        'start_time': datetime.utcnow(),
        'end_time': datetime.utcnow(),
        'total_cases': 1,
        'passed_cases': 1,
        'failed_cases': 0,
        'skipped_cases': 0,
        'case_results': {
            'case1': {
                'category': 'sequential',
                'status': 'passed',
                'workflow_id': 'wf1',
                'latency_seconds': 1,
                'error_message': None,
                'failure_reason': None,
                'expected_status': 'completed',
                'actual_status': 'completed',
                'output_correct': True,
                'execution_trace': []
            }
        },
        'metrics': {
            'workflow_completion_rate': 100.0,
            'expected_behavior_pass_rate': 100.0,
            'output_correctness_rate': 100.0,
            'median_latency': 1.0,
            'p95_latency': 1.0,
            'mean_latency': 1.0,
            'tool_call_success_rate': 100.0,
            'retry_recovery_rate': 0.0,
            'provider_error_rate': 0.0,
            'empty_result_rate': 0.0,
            'partial_completion_rate': 0.0
        },
        'provider_config': {'mode': 'controlled'},
        'environment': {'test': 'true'}
    })()

    runner.persist_results(mock_run)

    with SessionLocal() as db:
        run_record = db.query(BenchmarkRunRecord).filter(BenchmarkRunRecord.id == 'test-run-123').first()
        assert run_record is not None
        assert run_record.total_cases == 1
        assert run_record.passed_cases == 1

        case_records = db.query(BenchmarkCaseResult).filter(BenchmarkCaseResult.benchmark_run_id == 'test-run-123').all()
        assert len(case_records) == 1
        assert case_records[0].status == 'passed'

def test_benchmark_report_generation():
    """Test that benchmark reports can be generated."""
    runner = BenchmarkRunner(mode=BenchmarkMode.CONTROLLED)

    mock_run = type('obj', (object,), {
        'run_id': 'test-report-123',
        'suite_version': '1.0.0',
        'mode': BenchmarkMode.CONTROLLED,
        'start_time': datetime.utcnow(),
        'end_time': datetime.utcnow(),
        'total_cases': 1,
        'passed_cases': 1,
        'failed_cases': 0,
        'skipped_cases': 0,
        'case_results': {
            'case1': {
                'category': 'sequential',
                'status': 'passed',
                'actual_status': 'completed',
                'latency_seconds': 1,
                'expected_status': 'completed',
                'output_correct': True,
                'failure_reason': None
            }
        },
        'metrics': {
            'workflow_completion_rate': 100.0,
            'expected_behavior_pass_rate': 100.0,
            'output_correctness_rate': 100.0,
            'median_latency': 1.0,
            'p95_latency': 1.0,
            'mean_latency': 1.0,
            'tool_call_success_rate': 100.0,
            'retry_recovery_rate': 0.0,
            'provider_error_rate': 0.0,
            'empty_result_rate': 0.0,
            'partial_completion_rate': 0.0
        },
        'provider_config': {'mode': 'controlled'},
        'environment': {'test': 'true'}
    })()

    reports = runner.generate_reports(mock_run)

    assert 'json' in reports
    assert 'markdown' in reports
    assert 'json_path' in reports
    assert 'markdown_path' in reports

    # Verify JSON report structure
    import json
    json_data = json.loads(reports['json'])
    assert json_data['run_id'] == 'test-report-123'
    assert json_data['summary']['total_cases'] == 1
    assert json_data['summary']['passed_cases'] == 1

    # Verify Markdown report contains key sections
    md = reports['markdown']
    assert '# FlowMind Benchmark Report' in md
    assert '## Summary' in md
    assert '## Metrics' in md
    assert '## Case Results' in md

def test_sequential_cases_expected_outputs():
    """Test that sequential cases have correct expected outputs."""
    seq_cases = get_cases_by_category(BenchmarkCategory.SEQUENTIAL)

    # SEQ_001: 15% of 2000 = 300, +250 = 550, /5 = 110
    seq_001 = get_case_by_id("SEQ_001")
    assert seq_001.expected_output["final_result"] == 110.0

    # SEQ_002: 10*5=50, -20=30, +15=45, /3=15
    seq_002 = get_case_by_id("SEQ_002")
    assert seq_002.expected_output["final_result"] == 15.0

def test_failure_cases_have_classification_rules():
    """Test that failure recovery cases have classification rules."""
    fail_cases = get_cases_by_category(BenchmarkCategory.FAILURE_RECOVERY)

    for case in fail_cases:
        if "division by zero" in case.description.lower():
            assert case.failure_classification_rules is not None
            assert case.failure_classification_rules.get("expected_error_category") == "permanent_error"

def test_benchmark_modes_enum():
    """Test that benchmark mode enum has correct values."""
    assert BenchmarkMode.CONTROLLED.value == "controlled"
    assert BenchmarkMode.LIVE.value == "live"

def test_benchmark_status_enum():
    """Test that benchmark case status enum has correct values."""
    assert BenchmarkCaseStatus.PASSED.value == "passed"
    assert BenchmarkCaseStatus.FAILED.value == "failed"
    assert BenchmarkCaseStatus.SKIPPED.value == "skipped"
    assert BenchmarkCaseStatus.ERROR.value == "error"
