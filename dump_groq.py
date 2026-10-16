import os

import httpx

api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY is not set")

response = httpx.get(
    "https://api.groq.com/openai/v1/models",
    headers={"Authorization": f"Bearer {api_key}"},
)
response.raise_for_status()

with open("groq_models.txt", "w") as f:
    for model in response.json().get("data", []):
        f.write(f"{model['id']}\n")
