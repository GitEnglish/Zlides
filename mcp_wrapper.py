#!/usr/bin/env python3
import sys
import json
import os
import httpx
import jwt
import time
from dotenv import load_dotenv

load_dotenv()

Z_AI_API_KEY = os.getenv("Z_AI_API_KEY")
API_ENDPOINT = "https://api.z.ai/api/v1/agents"
AGENT_ID = "slides_glm_agent"


def call_zai_api(message: str) -> dict:
    api_key, secret = Z_AI_API_KEY.split(".")
    payload = {
        "api_key": api_key,
        "exp": int(time.time() * 1000) + 3600000,
        "timestamp": int(time.time() * 1000),
    }
    token = jwt.encode(
        payload,
        secret,
        algorithm="HS256",
        headers={"alg": "HS256", "sign_type": "SIGN"},
    )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    user_text = (
        f"Create a slide about {message}. Output the HTML now starting with <!DOCTYPE"
    )

    payload = {
        "agent_id": AGENT_ID,
        "stream": True,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": user_text}]}
        ],
    }

    full_text = []
    html_output = None

    with httpx.Client(timeout=120.0) as client:
        response = client.post(
            API_ENDPOINT,
            json=payload,
            headers=headers,
        )

        if response.status_code != 200:
            return {"error": f"API returned {response.status_code}"}

        for line in response.text.split("\n"):
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                continue
            try:
                chunk = json.loads(data)
                if not isinstance(chunk, dict):
                    continue

                choices = chunk.get("choices", [])
                for choice in choices:
                    if not isinstance(choice, dict):
                        continue
                    messages = choice.get("messages", [])
                    for msg in messages:
                        if not isinstance(msg, dict):
                            continue
                        content = msg.get("content")
                        if isinstance(content, list):
                            for item in content:
                                if not isinstance(item, dict):
                                    continue
                                item_type = item.get("type", "")
                                if item_type == "text":
                                    text = item.get("text", "")
                                    if text:
                                        full_text.append(text)
                                elif item_type == "object":
                                    obj = item.get("object", {})
                                    if obj.get("output"):
                                        html_output = obj["output"]
                        elif isinstance(content, dict):
                            content_type = content.get("type", "")
                            if content_type == "text":
                                text = content.get("text", "")
                                if text:
                                    full_text.append(text)
                            elif content_type == "object":
                                obj = content.get("object", {})
                                if obj.get("output"):
                                    html_output = obj["output"]
            except Exception:
                pass

    if html_output:
        return {"html": html_output}
    elif full_text:
        full_response = "".join(full_text)
        if "<html" in full_response.lower():
            return {"html": full_response}

    return {"error": "No HTML generated"}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON"}), flush=True)
            continue

        method = request.get("method", "")
        params = request.get("params", {})

        if method == "tools/call":
            arguments = params.get("arguments", {})
            message = arguments.get("message", arguments.get("slide_topic", ""))

            if message:
                result = call_zai_api(message)
            else:
                result = {"error": "No message provided"}
        else:
            result = {"error": f"Unknown method: {method}"}

        response = {
            "jsonrpc": "2.0",
            "id": request.get("id"),
            "result": result,
        }
        print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
