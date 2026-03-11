import asyncio
import httpx
import os
import json
import time
import jwt
from dotenv import load_dotenv

load_dotenv()
Z_AI_API_KEY = os.getenv("Z_AI_API_KEY")

def generate_token(apikey: str):
    api_key, secret = apikey.split(".")
    payload = {
        "api_key": api_key,
        "exp": int(round(time.time() * 1000)) + 3 * 60 * 1000 + 30 * 1000,
        "timestamp": int(round(time.time() * 1000)),
    }
    return jwt.encode(payload, secret, algorithm="HS256", headers={"alg": "HS256", "sign_type": "SIGN"})

async def main():
    headers = {
        "Authorization": f"Bearer {generate_token(Z_AI_API_KEY)}",
        "Content-Type": "application/json",
    }
    payload = {
        "agent_id": "slides_glm_agent",
        "stream": True,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": "Create a slide about dogs."}]}
        ],
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("POST", "https://api.z.ai/api/v1/agents", json=payload, headers=headers) as response:
            async for line in response.aiter_lines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data == "[DONE]": continue
                    try:
                        chunk = json.loads(data)
                        print(json.dumps(chunk))
                    except: pass

asyncio.run(main())
