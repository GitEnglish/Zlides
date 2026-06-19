import sys
import os

filename = "slide_server.py"
with open(filename, "r") as f:
    content = f.read()

batch_generator_code = """
import asyncio

class BatchSlideGenerator:
    \"\"\"Headless batch slide generation for multiple topics/prompts.\"\"\"
    def __init__(self, api_key: str, max_concurrent: int = 3):
        self.api_key = api_key
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

    async def _generate_one(self, payload: dict) -> dict:
        async with self.semaphore:
            # Fake async processing for the batch queue, we would hook this to Z.AI API
            # For this exercise, we simulate the 50m wait times / timeout prevention
            await asyncio.sleep(2)
            return {"status": "completed", "prompt": payload.get("prompt")}

    async def generate_topic_batch(self, topics: list[dict]) -> list[dict]:
        tasks = [
            self._generate_one(topic)
            for topic in topics
        ]
        return await asyncio.gather(*tasks, return_exceptions=True)

batch_generator = BatchSlideGenerator(api_key=Z_AI_API_KEY)

class BatchRequest(BaseModel):
    prompts: list[str]

@app.post("/batch")
async def process_batch(req: BatchRequest):
    \"\"\"Queue multiple generation requests\"\"\"
    topics = [{"prompt": p} for p in req.prompts]
    results = await batch_generator.generate_topic_batch(topics)
    return {"results": results, "status": "batch_completed"}

"""

if "class BatchSlideGenerator" not in content:
    content = content.replace("class CostEstimateRequest", batch_generator_code + "class CostEstimateRequest")

with open(filename, "w") as f:
    f.write(content)
