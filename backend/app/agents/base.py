from abc import ABC, abstractmethod
from app.providers.factory import get_provider
from app.config import settings
from typing import Any

class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name
        self.provider = get_provider()
        self.model = settings.AGENT_MODEL
        
    @abstractmethod
    async def execute(self, state: Any, **kwargs) -> Any:
        pass
