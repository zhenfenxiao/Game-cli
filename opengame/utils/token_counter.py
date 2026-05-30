"""Token estimation utilities.

Provides rough token counting and model context window lookups.
"""

# Model context window sizes (in tokens)
_MODEL_TOKEN_LIMITS: dict[str, int] = {
    # OpenAI
    "gpt-4o": 128_000,
    "gpt-4o-mini": 128_000,
    "gpt-4-turbo": 128_000,
    "gpt-4": 8_192,
    "gpt-4-32k": 32_768,
    "gpt-3.5-turbo": 16_384,
    "gpt-3.5-turbo-16k": 16_384,
    "o1": 200_000,
    "o1-mini": 128_000,
    "o3-mini": 200_000,
    "o3": 200_000,
    "o4-mini": 200_000,
    # Anthropic
    "claude-3-opus": 200_000,
    "claude-3-sonnet": 200_000,
    "claude-3-haiku": 200_000,
    "claude-3.5-sonnet": 200_000,
    "claude-3.5-haiku": 200_000,
    "claude-opus-4": 200_000,
    "claude-sonnet-4": 200_000,
    "claude-haiku-4.5": 200_000,
    # DeepSeek
    "deepseek-v4": 128_000,
    "deepseek-reasoner": 64_000,
    # DashScope (Qwen)
    "qwen-turbo": 131_072,
    "qwen-plus": 131_072,
    "qwen-max": 32_768,
    # OpenRouter fallback
    "openrouter-default": 128_000,
}

# Rough heuristic: ~4 characters per token for English text
_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count for a string using a character-based heuristic.

    This is a rough approximation (~4 chars per token for English text).
    For accurate counts, use the model's tokenizer.

    Args:
        text: The text to estimate tokens for.

    Returns:
        Estimated token count. Returns 0 for empty input.
    """
    if not text:
        return 0
    return max(1, len(text) // _CHARS_PER_TOKEN)


def get_model_token_limit(model: str) -> int:
    """Get the context window size for a known model.

    Args:
        model: Model name/identifier.

    Returns:
        Context window size in tokens. Returns 128_000 as a safe default
        for unknown models.
    """
    # Exact match
    if model in _MODEL_TOKEN_LIMITS:
        return _MODEL_TOKEN_LIMITS[model]

    # Fuzzy match: check if the model name contains a known key
    model_lower = model.lower()
    for known_model, limit in _MODEL_TOKEN_LIMITS.items():
        if known_model in model_lower:
            return limit

    # Default: assume 128k context (common for modern models)
    return 128_000
