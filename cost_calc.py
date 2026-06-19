def estimate_cost(input_tokens: int, output_tokens: int, model: str = "glm-4.5") -> float:
    """
    Estimates the cost of a Zhipu AI GLM API call in USD.

    Rates per 1M tokens (RMB to USD ~0.14 conversion):
    GLM-4.5: Input ¥0.8 ($0.11), Output ¥2.0 ($0.28)
    Multiplier: Agent tasks consume ~2.5x tokens (thinking + tool overhead)
    """
    rates_rmb = {
        "glm-4.5": {"in": 0.8, "out": 2.0},
        "glm-4.5-air": {"in": 0.35, "out": 0.5},
        "glm-4.6": {"in": 1.0, "out": 2.0},
        "glm-4.7": {"in": 0.5, "out": 1.0},
    }

    rate = rates_rmb.get(model, rates_rmb["glm-4.5"])

    # Cost in RMB
    cost_rmb = (input_tokens / 1_000_000) * rate["in"] + (output_tokens / 1_000_000) * rate["out"]

    # Apply agent overhead multiplier (2.5x average)
    cost_rmb *= 2.5

    # Convert to USD (~0.14)
    cost_usd = cost_rmb * 0.14

    return cost_usd
