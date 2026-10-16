from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict, Any

class ExecutionEvent(BaseModel):
    event_id: str
    workflow_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str
    step_id: Optional[str] = None
    agent_id: Optional[str] = None
    tool_name: Optional[str] = None
    status: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
