from enum import Enum
from pydantic import BaseModel, validator
from typing import Callable, Any, Dict, Type, Awaitable
from inspect import iscoroutinefunction

class PermissionType(str, Enum):
    SAFE = "safe"
    EXTERNAL_READ = "external_read"
    EXTERNAL_WRITE = "external_write"
    DESTRUCTIVE = "destructive"

class ToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: Dict[str, Any]
    permission: PermissionType = PermissionType.SAFE
    handler: Any
    
    class Config:
        arbitrary_types_allowed = True

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition):
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> ToolDefinition:
        if name not in self._tools:
            raise KeyError(f"Tool {name} not found")
        return self._tools[name]
        
    def list_tools(self) -> Dict[str, ToolDefinition]:
        return self._tools

registry = ToolRegistry()
