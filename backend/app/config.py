from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    GEMINI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    OPENROUTER_API_KEY: Optional[str] = None
    TOGETHER_API_KEY: Optional[str] = None
    HUGGINGFACE_API_KEY: Optional[str] = None

    LLM_PROVIDER: str = "groq"
    PLANNER_MODEL: str = "llama-3.1-8b-instant"
    AGENT_MODEL: str = "llama-3.1-8b-instant"
    SYNTHESIS_MODEL: str = "llama-3.1-8b-instant"

    MAX_AGENT_STEPS: int = 20
    DB_URL: str = "sqlite:///./flowmind.db"

    class Config:
        env_file = ".env"

settings = Settings()
