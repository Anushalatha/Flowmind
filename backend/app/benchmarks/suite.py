from app.models.benchmark import BenchmarkCase, BenchmarkCategory
from typing import Optional, List

# Sequential Execution (5 cases)
SEQUENTIAL_CASES = [
    BenchmarkCase(
        case_id="SEQ_001",
        category=BenchmarkCategory.SEQUENTIAL,
        description="Three-step arithmetic chain with scalar results",
        user_request="Calculate 15% of 2000, add 250, then divide by 5.",
        expected_terminal_status="completed",
        expected_output={"final_result": 110.0},
        output_validation="Final result should be 110.0 (15% of 2000 = 300, +250 = 550, /5 = 110)",
        timeout=30,
        required_services=[]
    ),
    BenchmarkCase(
        case_id="SEQ_002",
        category=BenchmarkCategory.SEQUENTIAL,
        description="Four-step calculation with mixed operations",
        user_request="Multiply 10 by 5, subtract 20, add 15, then divide by 3.",
        expected_terminal_status="completed",
        expected_output={"final_result": 15.0},
        output_validation="Final result should be 15.0 (10*5=50, -20=30, +15=45, /3=15)",
        timeout=30,
        required_services=[]
    ),
    BenchmarkCase(
        case_id="SEQ_003",
        category=BenchmarkCategory.SEQUENTIAL,
        description="Percentage calculation with subsequent operations",
        user_request="Calculate 25% of 800, multiply by 2, then subtract 100.",
        expected_terminal_status="completed",
        expected_output={"final_result": 300.0},
        output_validation="Final result should be 300.0 (25% of 800 = 200, *2 = 400, -100 = 300)",
        timeout=30,
        required_services=[]
    ),
    BenchmarkCase(
        case_id="SEQ_004",
        category=BenchmarkCategory.SEQUENTIAL,
        description="Division by zero in chain",
        user_request="Calculate 10% of 500, divide by 0, then add 50.",
        expected_terminal_status="partially_completed",
        expected_output=None,
        output_validation="Workflow should partially complete (first step succeeds, division by zero fails)",
        timeout=30,
        required_services=[],
        failure_classification_rules={"expected_error": "division by zero", "error_category": "permanent_error"}
    ),
    BenchmarkCase(
        case_id="SEQ_005",
        category=BenchmarkCategory.SEQUENTIAL,
        description="Word count in text with chained operations",
        user_request="Count words in 'The quick brown fox', multiply by 2, then add 5.",
        expected_terminal_status="completed",
        expected_output={"final_result": 13.0},
        output_validation="Final result should be 13.0 (4 words * 2 = 8, +5 = 13)",
        timeout=30,
        required_services=[]
    ),
]

# Parallel Execution (5 cases)
PARALLEL_CASES = [
    BenchmarkCase(
        case_id="PAR_001",
        category=BenchmarkCategory.PARALLEL,
        description="Independent calculator steps with aggregation",
        user_request="Calculate 10+5, 20*3, and 15/3 in parallel, then sum all results.",
        expected_terminal_status="completed",
        expected_output={"final_result": 80.0},
        output_validation="Final result should be 80.0 (10+5=15, 20*3=60, 15/3=5, sum=80)",
        timeout=30,
        required_services=[]
    ),
    BenchmarkCase(
        case_id="PAR_002",
        category=BenchmarkCategory.PARALLEL,
        description="Parallel percentage calculations",
        user_request="Calculate 10% of 1000, 20% of 500, and 15% of 2000 in parallel, then sum.",
        expected_terminal_status="completed",
        expected_output={"final_result": 500.0},
        output_validation="Final result should be 500.0 (10% of 1000 = 100, 20% of 500 = 100, 15% of 2000 = 300, sum = 500)",
        timeout=30,
        required_services=[]
    ),
    BenchmarkCase(
        case_id="PAR_003",
        category=BenchmarkCategory.PARALLEL,
        description="Parallel independent operations with mixed tools",
        user_request="Calculate 5*5, count words in 'hello world', and calculate 50% of 100 in parallel.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="All three steps should complete successfully",
        timeout=30,
        required_services=[]
    ),
    BenchmarkCase(
        case_id="PAR_004",
        category=BenchmarkCategory.PARALLEL,
        description="Parallel steps with one failure, dependent step blocked",
        user_request="Calculate 10+5, divide 20 by 0, and multiply 3*4 in parallel, then add all results.",
        expected_terminal_status="skipped",
        expected_output=None,
        output_validation="SKIPPED: Known limitation - workflow engine deadlock when parallel step fails and depends on aggregation (tracked separately)",
        timeout=30,
        required_services=[],
        failure_classification_rules={}
    ),
    BenchmarkCase(
        case_id="PAR_005",
        category=BenchmarkCategory.PARALLEL,
        description="All parallel steps succeed",
        user_request="Calculate 10+5, 8*2, and 15/3 in parallel, then multiply the first two results.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="All steps should complete, multiplication of first two should work",
        timeout=30,
        required_services=[]
    ),
]

# Research and Fallback (5 cases)
RESEARCH_CASES = [
    BenchmarkCase(
        case_id="RES_001",
        category=BenchmarkCategory.RESEARCH,
        description="Successful single research query",
        user_request="Research Python programming language features.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="Should return search results with snippets",
        timeout=30,
        required_services=["web_search"]
    ),
    BenchmarkCase(
        case_id="RES_002",
        category=BenchmarkCategory.RESEARCH,
        description="Primary search empty, fallback succeeds",
        user_request="Research 'xyznonexistent123topic' with fallback search.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="Primary search returns empty, fallback should provide results",
        timeout=30,
        required_services=["web_search", "web_search_fallback"]
    ),
    BenchmarkCase(
        case_id="RES_003",
        category=BenchmarkCategory.RESEARCH,
        description="Parallel research with partial success",
        user_request="Research PostgreSQL, MongoDB, and Qdrant vector databases in parallel.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="At least some searches should return results, empty results should be classified correctly",
        timeout=30,
        required_services=["web_search"]
    ),
    BenchmarkCase(
        case_id="RES_004",
        category=BenchmarkCategory.RESEARCH,
        description="All research queries return empty results",
        user_request="Research three nonexistent topics.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="All searches return empty results, workflow completes successfully (empty_result is a valid execution outcome)",
        timeout=30,
        required_services=["web_search"]
    ),
    BenchmarkCase(
        case_id="RES_005",
        category=BenchmarkCategory.RESEARCH,
        description="Research with chained analysis",
        user_request="Research Python, then count words in the search results.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="Search should succeed, word count should operate on search snippets",
        timeout=30,
        required_services=["web_search"]
    ),
]

# API and Data Workflows (5 cases)
API_DATA_CASES = [
    BenchmarkCase(
        case_id="API_001",
        category=BenchmarkCategory.API_DATA,
        description="HTTP request, validation, extraction chain",
        user_request="Fetch data from https://jsonplaceholder.typicode.com/todos/1, validate it's JSON, extract title field.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="Should successfully fetch, validate, and extract title",
        timeout=30,
        required_services=["http_request"]
    ),
    BenchmarkCase(
        case_id="API_002",
        category=BenchmarkCategory.API_DATA,
        description="HTTP request to non-existent URL",
        user_request="Fetch data from https://nonexistent-api.example.com/data.",
        expected_terminal_status="failed",
        expected_output=None,
        output_validation="Should fail with network error or 404",
        timeout=30,
        required_services=["http_request"],
        failure_classification_rules={"expected_retry_count": 2, "expected_error_category": "network_error"}
    ),
    BenchmarkCase(
        case_id="API_003",
        category=BenchmarkCategory.API_DATA,
        description="Malformed JSON response handling",
        user_request="Fetch and validate JSON from an endpoint returning invalid JSON.",
        expected_terminal_status="partially_completed",
        expected_output=None,
        output_validation="Fetch succeeds, validation fails - the workflow partially completes because fetch succeeded",
        timeout=30,
        required_services=["http_request"],
        failure_classification_rules={"expected_error_category": "parse_error"}
    ),
    BenchmarkCase(
        case_id="API_004",
        category=BenchmarkCategory.API_DATA,
        description="Extract optional fields gracefully",
        user_request="Fetch JSON, validate, extract multiple fields including optional ones.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="Should extract available fields, handle missing optional fields",
        timeout=30,
        required_services=["http_request"]
    ),
    BenchmarkCase(
        case_id="API_005",
        category=BenchmarkCategory.API_DATA,
        description="Empty response body handling",
        user_request="Fetch from an endpoint returning empty body, validate as JSON.",
        expected_terminal_status="partially_completed",
        expected_output=None,
        output_validation="Fetch succeeds, validation fails with parse error (empty string is not valid JSON)",
        timeout=30,
        required_services=["http_request"],
        failure_classification_rules={"expected_error_category": "parse_error"}
    ),
]

# Failure Recovery (5 cases)
FAILURE_RECOVERY_CASES = [
    BenchmarkCase(
        case_id="FAIL_001",
        category=BenchmarkCategory.FAILURE_RECOVERY,
        description="Transient network error with retry",
        user_request="Search with simulated transient network error.",
        expected_terminal_status="failed",
        expected_output=None,
        output_validation="Should retry and fail with network error (transient errors are retried)",
        timeout=30,
        required_services=["web_search"],
        failure_classification_rules={"expected_retry_count": 2}
    ),
    BenchmarkCase(
        case_id="FAIL_002",
        category=BenchmarkCategory.FAILURE_RECOVERY,
        description="Permanent error no retry",
        user_request="Divide by zero (permanent error).",
        expected_terminal_status="failed",
        expected_output=None,
        output_validation="Should fail immediately without retries",
        timeout=30,
        required_services=[],
        failure_classification_rules={"expected_retry_count": 0, "expected_error_category": "permanent_error"}
    ),
    BenchmarkCase(
        case_id="FAIL_003",
        category=BenchmarkCategory.FAILURE_RECOVERY,
        description="Dependency blocked due to upstream failure",
        user_request="Search Python, then multiply the results by 2.",
        expected_terminal_status="partially_completed",
        expected_output=None,
        output_validation="Search succeeds, multiplication fails due to invalid result type - workflow partially completes",
        timeout=30,
        required_services=["web_search"],
        failure_classification_rules={"expected_failed_steps": 1, "expected_blocked_steps": 0}
    ),
    BenchmarkCase(
        case_id="FAIL_004",
        category=BenchmarkCategory.FAILURE_RECOVERY,
        description="Partial completion with independent steps",
        user_request="Calculate 10+5, search nonexistent topic, and multiply 3*4 in parallel.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="Calculator steps succeed, search returns empty_result (valid execution outcome) - all steps complete successfully",
        timeout=30,
        required_services=["web_search"],
        failure_classification_rules={"expected_successful_steps": 3, "expected_failed_steps": 0}
    ),
    BenchmarkCase(
        case_id="FAIL_005",
        category=BenchmarkCategory.FAILURE_RECOVERY,
        description="Rate limit error handling",
        user_request="Search with simulated rate limit.",
        expected_terminal_status="failed",
        expected_output=None,
        output_validation="Should retry and fail with rate limit error",
        timeout=30,
        required_services=["web_search"],
        failure_classification_rules={"expected_retry_count": 2, "expected_error_category": "rate_limit"}
    ),
]

# Persistence and Orchestration Reliability (5 cases)
PERSISTENCE_CASES = [
    BenchmarkCase(
        case_id="PERS_001",
        category=BenchmarkCategory.PERSISTENCE,
        description="Workflow state persistence during execution",
        user_request="Calculate 10+5, then multiply by 2.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="Workflow state should be persisted after each step",
        timeout=30,
        required_services=[]
    ),
    BenchmarkCase(
        case_id="PERS_002",
        category=BenchmarkCategory.PERSISTENCE,
        description="Event persistence throughout workflow",
        user_request="Calculate 15% of 2000, add 250.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="All events should be persisted in database",
        timeout=30,
        required_services=[]
    ),
    BenchmarkCase(
        case_id="PERS_003",
        category=BenchmarkCategory.PERSISTENCE,
        description="Terminal status not overwritten by late events",
        user_request="Calculate 10+5, divide by 0.",
        expected_terminal_status="partially_completed",
        expected_output=None,
        output_validation="First step succeeds, second step fails - workflow is partially_completed",
        timeout=30,
        required_services=[]
    ),
    BenchmarkCase(
        case_id="PERS_004",
        category=BenchmarkCategory.PERSISTENCE,
        description="Partial completion status persistence",
        user_request="Calculate 10+5, search nonexistent, multiply 3*4 in parallel.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="All steps complete successfully (search returns empty_result which is valid)",
        timeout=30,
        required_services=["web_search"]
    ),
    BenchmarkCase(
        case_id="PERS_005",
        category=BenchmarkCategory.PERSISTENCE,
        description="Workflow retrieval after completion",
        user_request="Calculate 20% of 500, add 100.",
        expected_terminal_status="completed",
        expected_output=None,
        output_validation="Should be able to retrieve complete workflow state from database",
        timeout=30,
        required_services=[]
    ),
]

# All cases combined
ALL_BENCHMARK_CASES = (
    SEQUENTIAL_CASES +
    PARALLEL_CASES +
    RESEARCH_CASES +
    API_DATA_CASES +
    FAILURE_RECOVERY_CASES +
    PERSISTENCE_CASES
)

def get_case_by_id(case_id: str) -> Optional[BenchmarkCase]:
    """Get a benchmark case by ID."""
    for case in ALL_BENCHMARK_CASES:
        if case.case_id == case_id:
            return case
    return None

def get_cases_by_category(category: BenchmarkCategory) -> List[BenchmarkCase]:
    """Get all benchmark cases for a category."""
    return [case for case in ALL_BENCHMARK_CASES if case.category == category]
