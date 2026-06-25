import uvicorn
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import asyncio
import json
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CommandRequest(BaseModel):
    message: str
    format: str = "slides"
    style: str = "auto"
    page_count: int = 5
    layout: str = ""

@app.post("/command")
async def send_command(req: CommandRequest):
    async def event_generator():
        yield "data: " + json.dumps({"type": "thinking", "text": "1. Analyzing request..."}) + "\n\n"
        await asyncio.sleep(1.0)
        yield "data: " + json.dumps({"type": "tool", "tool_name": "search", "input": "cute puppies"}) + "\n\n"
        yield "data: " + json.dumps({"type": "thinking", "text": "2. Looking at search results for cute puppies..."}) + "\n\n"
        await asyncio.sleep(2.0)
        yield "data: " + json.dumps({"type": "tool", "tool_name": "image_search", "input": "golden retriever"}) + "\n\n"
        yield "data: " + json.dumps({"type": "thinking", "text": "3. Found a great image! ![golden retriever](https://images.unsplash.com/photo-1552053831-71594a27632d?w=200)"}) + "\n\n"
        yield "data: " + json.dumps({"type": "slide_page", "html": "<html><body style='display:flex;flex-direction:column;align-items:center;justify-content:center;height:100vh;background:#262424;color:#9e9e9e;font-family:sans-serif;'><h3>Active Mock Stream Preview</h3><p>Chunk 1 loaded...</p></body></html>"}) + "\n\n"
        await asyncio.sleep(1.0)
        yield "data: " + json.dumps({"type": "slide_page", "html": "<p>Chunk 2 loaded...</p>"}) + "\n\n"
        await asyncio.sleep(4.0)
        yield "data: " + json.dumps({"type": "answer", "text": "Here are your slides!"}) + "\n\n"
        await asyncio.sleep(1.0)
        yield "data: " + json.dumps({"type": "final_html", "html": "<h1>Test Slide</h1>"}) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/estimate-cost")
async def estimate_cost():
    return {"cost_usd": 0.05}

@app.get("/styles")
async def get_styles():
    return [{"id": "auto", "name": "Auto Style"}]

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=2828)
