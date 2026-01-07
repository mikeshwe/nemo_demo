"""Calculate LLM costs for Langfuse tracking"""

# NVIDIA NIM API pricing (as of 2024)
# Pricing varies by model - these are example rates
# Update with actual NVIDIA pricing
PRICING = {
    "meta/llama-3.1-70b-instruct": {
        "input": 0.00088,   # per 1K tokens
        "output": 0.00088    # per 1K tokens
    },
    "meta/llama-3.1-8b-instruct": {
        "input": 0.00020,
        "output": 0.00020
    },
    "nvidia/llama-3.1-nemotron-70b-instruct": {
        "input": 0.00088,
        "output": 0.00088
    },
    # Fallback for unknown models
    "default": {
        "input": 0.00088,
        "output": 0.00088
    }
}


def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Calculate cost for LLM call

    Args:
        model: Model name
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens

    Returns:
        Cost in USD
    """
    # Get pricing for model (fallback to default if not found)
    prices = PRICING.get(model, PRICING["default"])

    input_cost = (prompt_tokens / 1000) * prices["input"]
    output_cost = (completion_tokens / 1000) * prices["output"]

    return input_cost + output_cost


def log_cost_to_langfuse(model: str, usage: dict):
    """Log cost as Langfuse score

    Args:
        model: Model name
        usage: Usage dict with prompt_tokens, completion_tokens, total_tokens
    """
    from src.observability.langfuse_integration import score_generation, is_langfuse_enabled

    if not is_langfuse_enabled():
        return

    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    cost = calculate_cost(model, prompt_tokens, completion_tokens)

    if cost > 0:
        score_generation(
            name="cost_usd",
            value=cost,
            comment=f"${cost:.6f} for {total_tokens} tokens ({prompt_tokens} prompt + {completion_tokens} completion)"
        )
