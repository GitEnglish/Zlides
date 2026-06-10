import sys

filename = "slide_server.py"
with open(filename, "r") as f:
    content = f.read()

cost_calc_func = """
def estimate_cost(input_tokens: int, output_tokens: int, model: str = "glm-4.5") -> float:
    # Estimate cost in USD
    rates_rmb = {
        "glm-4.5": {"in": 0.8, "out": 2.0},
        "glm-4.5-air": {"in": 0.35, "out": 0.5},
        "glm-4.6": {"in": 1.0, "out": 2.0},
        "glm-4.7": {"in": 0.5, "out": 1.0},
    }
    rate = rates_rmb.get(model, rates_rmb["glm-4.5"])
    cost_rmb = (input_tokens / 1_000_000) * rate["in"] + (output_tokens / 1_000_000) * rate["out"]
    cost_usd = cost_rmb * 2.5 * 0.14 # 2.5x agent overhead
    return round(cost_usd, 4)

"""

if "def estimate_cost" not in content:
    content = content.replace("app = FastAPI", cost_calc_func + "app = FastAPI")

with open(filename, "w") as f:
    f.write(content)
