from src.llm.pricing import ModelPrice, estimate_cost, get_price, register_price


def test_get_price_known_model():
    p = get_price("anthropic/claude-sonnet-4.6")
    assert p.input_per_mtok == 3.00
    assert p.output_per_mtok == 15.00


def test_get_price_unknown_returns_zero():
    p = get_price("nonexistent/model-x")
    assert p.input_per_mtok == 0
    assert p.output_per_mtok == 0


def test_estimate_cost_basic():
    cost = estimate_cost(
        "moonshot/kimi-k2.6",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    # input $0.74 + output $3.50 = $4.24
    assert cost == 4.24


def test_estimate_cost_cache_tokens():
    cost = estimate_cost(
        "anthropic/claude-sonnet-4.6",
        input_tokens=0,
        output_tokens=0,
        cache_write_tokens=1_000_000,
        cache_read_tokens=1_000_000,
    )
    # 3.75 + 0.30
    assert cost == 4.05


def test_estimate_cost_unknown_model_is_zero():
    assert estimate_cost("foo/bar", input_tokens=1_000_000) == 0


def test_register_price_roundtrip():
    register_price("custom/x", ModelPrice(1.0, 2.0))
    assert get_price("custom/x").input_per_mtok == 1.0
