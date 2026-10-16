from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from enum import Enum
from datetime import datetime

class WorkflowStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING = "waiting"
    RETRYING = "retrying"
    COMPLETED = "completed"
    PARTIALLY_COMPLETED = "partially_completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ErrorCategory(str, Enum):
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    PARSE_ERROR = "parse_error"
    PERMANENT_ERROR = "permanent_error"
    UNKNOWN = "unknown"

class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    EMPTY_RESULT = "empty_result"
    DEPENDENCY_BLOCKED = "dependency_blocked"
    SKIPPED = "skipped"

class StepDependencyInfo(BaseModel):
    step_id: str
    Wait_for_completion: bool = True

class WorkflowStepDefinition(BaseModel):
    step_id: str
    agent: str
    action: str
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)

class WorkflowPlan(BaseModel):
    goal: str
    steps: List[WorkflowStepDefinition]

class StepResult(BaseModel):
    step_id: str
    status: StepStatus = StepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    error_category: Optional[ErrorCategory] = None
    retry_count: int = 0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

class WorkflowState(BaseModel):
    workflow_id: str
    user_request: str
    status: WorkflowStatus = WorkflowStatus.PENDING
    current_step: Optional[str] = None
    plan: Optional[WorkflowPlan] = None
    agents: List[str] = Field(default_factory=list)
    step_results: Dict[str, StepResult] = Field(default_factory=dict)
    tool_results: Dict[str, Any] = Field(default_factory=dict)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    retry_counts: Dict[str, int] = Field(default_factory=dict)
    execution_trace: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    final_response: Optional[str] = None
