import json

with open('/Users/thelaw/.gemini/tmp/zlides/tool-outputs/session-9282ce6c-7a10-4d9a-84eb-3c9fc39ca96b/run_shell_command_1772823847852_0.txt', 'r') as f:
    for line in f:
        line = line.strip()
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            continue
        try:
            chunk = json.loads(data)
            if "choices" in chunk:
                choice = chunk["choices"][0]
                messages = choice.get("messages", [])
                for msg in messages:
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for item in content:
                            if item.get("type") == "object":
                                obj = item.get("object", {})
                                if "output" in obj and isinstance(obj["output"], str):
                                    tool_name = obj.get("tool_name", "")
                                    print(f"Tool Name: {tool_name}, Length: {len(obj['output'])}")
        except Exception:
            pass
