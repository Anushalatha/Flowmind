from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

class BenchmarkMode(str, Enum):
    CONTROLLED = "controlled"
    LIVE = "live"

class BenchmarkCategory(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    RESEARCH = "research"
    API_DATA = "api_data"
    FAILURE_RECOVERY = "failure_recovery"
    PERSISTENCE = "persistence"

class BenchmarkCaseStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"

class BenchmarkCase(BaseModel):
    case_id: str
    category: BenchmarkCategory
    description: str
    user_request: str
    expected_terminal_status: str
    expected_output: Optional[Dict[str, Any]] = None
    output_validation: Optional[str] = None  # Description of validation criteria
    timeout: int = 30
    required_services: List[str] = Field(default_factory=list)
    failure_classification_rules: Optional[Dict[str, Any]] = None

class BenchmarkRun(BaseModel):
    run_id: str
    suite_version: str = "1.0.0"
    mode: BenchmarkMode
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    total_cases: int = 0
    passed_cases: int = 0
    failed_cases: int = 0
    skipped_cases: int = 0
    case_results: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    provider_config: Optional[Dict[str, str]] = None  # Provider/model identifiers without secrets
    environment: Dict[str, str] = Field(default_factory=dict)

class BenchmarkMetrics(BaseModel):
    workflow_completion_rate: float
    expected_behavior_pass_rate: float
    output_correctness_rate: float
    median_latency: float
    p95_latency: float
    mean_latency: float
    tool_call_success_rate: float
    retry_recovery_rate: float
    provider_error_rate: float
    empty_result_rate: float
    partial_completion_rate: float
