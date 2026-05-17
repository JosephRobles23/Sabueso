import pytest

from src.llm.caching import (
    CacheBreakpointError,
    apply_cache_breakpoints,
    count_cache_markers,
    openrouter_respects_cache,
)


def _msgs():
    return [
        {"role": "system", "content": "identity"},
        {"role": "system", "content": "roster"},
        {"role": "system", "content": "tools"},
        {"role": "system", "content": "examples"},
        {"role": "user", "content": "do the thing"},
    ]


def test_apply_4_breakpoints():
    out = apply_cache_breakpoints(_msgs(), [0, 1, 2, 3])
    assert count_cache_markers(out) == 4
    for i in range(4):
        assert out[i]["content"][0]["cache_control"] == {"type": "ephemeral"}
    # user message untouched
    assert out[4]["content"] == "do the thing"


def test_apply_preserves_input_messages():
    msgs = _msgs()
    apply_cache_breakpoints(msgs, [0])
    assert msgs[0]["content"] == "identity", "input should not be mutated"


def test_apply_to_structured_content():
    msgs = [
        {
            "role": "system",
            "content": [
                {"type": "text", "text": "part a"},
                {"type": "text", "text": "part b"},
            ],
        }
    ]
    out = apply_cache_breakpoints(msgs, [0])
    assert out[0]["content"][0] == {"type": "text", "text": "part a"}
    assert out[0]["content"][1]["cache_control"] == {"type": "ephemeral"}


def test_too_many_breakpoints_raises():
    with pytest.raises(CacheBreakpointError):
        apply_cache_breakpoints(_msgs(), [0, 1, 2, 3, 4])


def test_out_of_range_breakpoint_raises():
    with pytest.raises(CacheBreakpointError):
        apply_cache_breakpoints(_msgs(), [99])


def test_empty_content_raises():
    with pytest.raises(CacheBreakpointError):
        apply_cache_breakpoints([{"role": "system", "content": []}], [0])


def test_invalid_content_type_raises():
    with pytest.raises(CacheBreakpointError):
        apply_cache_breakpoints([{"role": "system", "content": 42}], [0])


def test_openrouter_cache_detection_present():
    assert openrouter_respects_cache(
        {"cache_creation_input_tokens": 100, "cache_read_input_tokens": 0}
    )
    assert openrouter_respects_cache({"cache_read_input_tokens": 50})


def test_openrouter_cache_detection_absent():
    assert not openrouter_respects_cache(None)
    assert not openrouter_respects_cache({})
    assert not openrouter_respects_cache(
        {"prompt_tokens": 100, "completion_tokens": 50}
    )
