import sys
import re

filename = "slide_server.py"
with open(filename, "r") as f:
    content = f.read()

# We need to expose an endpoint for the frontend to predict cost based on prompt length
cost_endpoint = """
class CostEstimateRequest(BaseModel):
    prompt: str
    files_attached: int = 0

@app.post("/estimate-cost")
async def api_estimate_cost(req: CostEstimateRequest):
    # Rough token estimation: 1 word ~ 1.5 tokens
    # Average output for a slide deck is ~8000 tokens
    estimated_input_tokens = len(req.prompt.split()) * 1.5
    if req.files_attached > 0:
        estimated_input_tokens += req.files_attached * 3000 # Assume ~3k tokens per file

    estimated_output_tokens = 8000

    cost_usd = estimate_cost(estimated_input_tokens, estimated_output_tokens)
    return {"cost_usd": cost_usd, "input_tokens": estimated_input_tokens, "output_tokens": estimated_output_tokens}

"""

if "@app.post(\"/estimate-cost\")" not in content:
    content = content.replace("def load_style_bank():", cost_endpoint + "def load_style_bank():")

with open(filename, "w") as f:
    f.write(content)
