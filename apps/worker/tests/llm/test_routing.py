from src.llm.routing import RouteResolver


def test_default_routes_to_openrouter():
    r = RouteResolver()
    d = r.resolve("anthropic/claude-sonnet-4.6", needs_cache=True)
    assert d.provider == "openrouter"
    assert d.model == "anthropic/claude-sonnet-4.6"


def test_marks_openrouter_broken_when_cache_missing():
    r = RouteResolver()
    r.observe("anthropic/claude-sonnet-4.6", cache_stats_present=False)
    assert r.openrouter_cache_ok is False
    d = r.resolve("anthropic/claude-sonnet-4.6", needs_cache=True)
    assert d.provider == "anthropic"
    assert d.model == "claude-sonnet-4.6"  # provider prefix stripped


def test_observation_only_affects_anthropic_models():
    r = RouteResolver()
    r.observe("moonshot/kimi-k2.6", cache_stats_present=False)
    assert r.openrouter_cache_ok is None


def test_sticky_ok():
    r = RouteResolver()
    r.observe("anthropic/claude-sonnet-4.6", cache_stats_present=True)
    # a later miss should not flip back to broken
    r.observe("anthropic/claude-sonnet-4.6", cache_stats_present=False)
    assert r.openrouter_cache_ok is True


def test_non_anthropic_always_openrouter():
    r = RouteResolver()
    r.observe("anthropic/claude-sonnet-4.6", cache_stats_present=False)
    d = r.resolve("moonshot/kimi-k2.6", needs_cache=True)
    assert d.provider == "openrouter"


def test_no_cache_need_uses_openrouter_even_when_broken():
    r = RouteResolver()
    r.observe("anthropic/claude-sonnet-4.6", cache_stats_present=False)
    d = r.resolve("anthropic/claude-sonnet-4.6", needs_cache=False)
    assert d.provider == "openrouter"
