import re

with open("mock_backend.py", "r") as f:
    code = f.read()

# Make the mock backend simulate some tools and images
mock_generator = """
    async def event_generator():
        yield "data: " + json.dumps({"type": "thinking", "text": "1. Analyzing request..."}) + "\\n\\n"
        await asyncio.sleep(0.5)
        yield "data: " + json.dumps({"type": "tool", "tool_name": "search", "input": "cute puppies"}) + "\\n\\n"
        yield "data: " + json.dumps({"type": "thinking", "text": "2. Looking at search results for cute puppies..."}) + "\\n\\n"
        await asyncio.sleep(0.5)
        yield "data: " + json.dumps({"type": "tool", "tool_name": "image_search", "input": "golden retriever"}) + "\\n\\n"
        yield "data: " + json.dumps({"type": "thinking", "text": "3. Found a great image! ![golden retriever](https://images.unsplash.com/photo-1552053831-71594a27632d?w=200)"}) + "\\n\\n"
        await asyncio.sleep(0.5)
        yield "data: " + json.dumps({"type": "answer", "text": "Here are your slides!"}) + "\\n\\n"
        await asyncio.sleep(0.5)
        yield "data: " + json.dumps({"type": "final_html", "html": "<h1>Test Slide</h1>"}) + "\\n\\n"
        yield "data: [DONE]\\n\\n"
"""

code = re.sub(r"async def event_generator\(\):.*?yield \"data: \[DONE\]\\\\n\\\\n\"", mock_generator.strip(), code, flags=re.DOTALL)

with open("mock_backend.py", "w") as f:
    f.write(code)
