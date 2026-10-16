import httpx
import json
from typing import Any, Dict, Optional
from pydantic import BaseModel
from app.providers.base import LLMProvider
from app.config import settings

class GroqProvider(LLMProvider):
    def __init__(self):
        self.api_key = settings.GROQ_API_KEY
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"

    async def generate(self, prompt: str, model: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY is not set")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 4096  # Increase max tokens for longer responses
        }

        print(f"Groq request: model={model}, messages count={len(messages)}")
        print(f"Payload: {payload}")

        async with httpx.AsyncClient() as client:
            response = await client.post(self.base_url, headers=headers, json=payload, timeout=60.0)
            if response.status_code != 200:
                print(f"Groq error: {response.status_code} - {response.text}")
                print(f"Response headers: {response.headers}")
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            if not content:
                raise ValueError("LLM returned empty content")

            return content

    async def structured_generate(self, prompt: str, schema: type[BaseModel], model: str, system_prompt: Optional[str] = None) -> BaseModel:
        schema_json_str = schema.schema_json()
        augmented_prompt = (
            f"{prompt}\n\n"
            f"You MUST return ONLY valid JSON that matches the following JSON Schema:\n{schema_json_str}\n"
            f"Do not include Markdown formatting or any other text. Return raw JSON."
        )

        text_response = await self.generate(augmented_prompt, model, system_prompt)

        if not text_response:
            raise ValueError("LLM returned an empty response")

        print(f"Raw LLM response: {text_response[:500]}...")  # Log first 500 chars

        text_response = text_response.strip()
        if text_response.startswith("```json"):
            text_response = text_response[7:]
        if text_response.startswith("```"):
            text_response = text_response[3:]
        if text_response.endswith("```"):
            text_response = text_response[:-3]

        text_response = text_response.strip()

        if not text_response:
            raise ValueError("Response is empty after stripping markdown")

        try:
            parsed_json = json.loads(text_response)
            return schema(**parsed_json)
        except json.JSONDecodeError as e:
            # Check if response is truncated
            if "Unterminated string" in str(e) or "Expecting" in str(e):
                raise Exception(f"LLM response was truncated or incomplete. This may be due to max_tokens limit. Error: {e}\nResponse length: {len(text_response)}\nResponse (first 1000 chars): {text_response[:1000]}")
            raise Exception(f"Failed to parse JSON: {e}\nResponse was: {text_response}")
        except Exception as e:
            raise Exception(f"Failed to parse structured output: {e}\nResponse was: {text_response}")
