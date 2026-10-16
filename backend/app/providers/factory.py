from app.config import settings
from app.providers.base import LLMProvider
from app.providers.gemini import GeminiProvider
from app.providers.groq import GroqProvider

def get_provider() -> LLMProvider:
    provider_name = settings.LLM_PROVIDER.lower()
    
    # First try the configured provider
    if provider_name == "gemini" and settings.GEMINI_API_KEY:
        return GeminiProvider()
    elif provider_name == "groq" and settings.GROQ_API_KEY:
        return GroqProvider()
    
    # If configured provider doesn't have API key, try other available providers
    if settings.GROQ_API_KEY:
        return GroqProvider()
    elif settings.GEMINI_API_KEY:
        return GeminiProvider()
    
    # Fallback to Groq even without key (will fail with better error message)
    return GroqProvider()
