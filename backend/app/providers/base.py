from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class LLMProvider(ABC):
    
    @abstractmethod
    async def generate(self, prompt: str, model: str, system_prompt: Optional[str] = None) -> str:
        """Generate unstructured text"""
        pass
        
    @abstractmethod
    async def structured_generate(self, prompt: str, schema: type[BaseModel], model: str, system_prompt: Optional[str] = None) -> BaseModel:
        """Generate structured output that conforms to the given Pydantic schema"""
        pass
