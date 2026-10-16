import os

import httpx

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set")

response = httpx.get(
    "https://generativelanguage.googleapis.com/v1beta/models",
    params={"key": api_key},
)
response.raise_for_status()

with open("models_out.txt", "w") as f:
    for model in response.json().get("models", []):
        f.write(f"{model['name']} - {model.get('supportedGenerationMethods')}\n")
