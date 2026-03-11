import json
import sys

accumulated = ""
for line in sys.stdin:
    line = line.strip()
    if not line or not line.startswith("data:"):
        continue
    data = line[5:].strip()
    if data == "[DONE]":
        continue
    try:
        j = json.loads(data)
        choices = j.get("choices", [])
        if choices:
            msgs = choices[0].get("messages", [])
            for msg in msgs:
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "object":
                            obj = item.get("object", {})
                            if "output" in obj and isinstance(obj["output"], str):
                                tool_name = obj.get("tool_name", "")
                                if "slide" in tool_name.lower() or "page" in tool_name.lower() or tool_name == "":
                                    accumulated += obj["output"]
    except Exception:
        pass

print("Final length:", len(accumulated))
print("HTML Preview:", accumulated[:200])
