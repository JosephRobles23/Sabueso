"""Per-model pricing for cost tracking.

Prices are USD per 1M tokens. Source: S-05 technical notes in
docs/linear-tasks.md. Promo deals expire — keep the dates as comments so
we know when to revisit.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok: float
    output_per_mtok: float
    # Anthropic cache pricing: write tier ~1.25x input, read tier ~0.1x input.
    cache_write_per_mtok: float | None = None
    cache_read_per_mtok: float | None = None


PRICING: dict[str, ModelPrice] = {
    "anthropic/claude-sonnet-4.6": ModelPrice(
        input_per_mtok=3.00,
        output_per_mtok=15.00,
        cache_write_per_mtok=3.75,
        cache_read_per_mtok=0.30,
    ),
    "anthropic/claude-opus-4.7": ModelPrice(
        input_per_mtok=15.00,
        output_per_mtok=75.00,
        cache_write_per_mtok=18.75,
        cache_read_per_mtok=1.50,
    ),
    "moonshot/kimi-k2.6": ModelPrice(
        input_per_mtok=0.74,
        output_per_mtok=3.50,
    ),
    "deepseek/deepseek-v4-flash": ModelPrice(
        input_per_mtok=0.14,
        output_per_mtok=0.28,
    ),
    # Promo V4-Pro valid through 2026-05-31.
    "deepseek/deepseek-v4-pro": ModelPrice(
        input_per_mtok=0.435,
        output_per_mtok=0.87,
    ),
    "openai/gpt-4o": ModelPrice(
        input_per_mtok=2.50,
        output_per_mtok=10.00,
    ),
}


_DEFAULT_PRICE = ModelPrice(input_per_mtok=0.0, output_per_mtok=0.0)


def get_price(model: str) -> ModelPrice:
    return PRICING.get(model, _DEFAULT_PRICE)


def estimate_cost(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_read_tokens: int = 0,
) -> float:
    """Compute USD cost for a single LLM call.

    Cache write/read tokens are billed separately from the base input
    tokens; callers should pass the *non-cached* input separately.
    """
    p = get_price(model)
    cost = (
        input_tokens * p.input_per_mtok
        + output_tokens * p.output_per_mtok
    ) / 1_000_000
    if cache_write_tokens and p.cache_write_per_mtok is not None:
        cost += cache_write_tokens * p.cache_write_per_mtok / 1_000_000
    if cache_read_tokens and p.cache_read_per_mtok is not None:
        cost += cache_read_tokens * p.cache_read_per_mtok / 1_000_000
    return round(cost, 8)


def register_price(model: str, price: ModelPrice) -> None:
    """Test hook to inject a price for a custom model id."""
    PRICING[model] = price
