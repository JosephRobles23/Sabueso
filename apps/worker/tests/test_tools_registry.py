import pytest

from src.tools.registry import ToolDef, ToolRegistry


@pytest.fixture(autouse=True)
def _clean():
    ToolRegistry.clear()
    yield
    ToolRegistry.clear()


@pytest.mark.asyncio
async def test_register_decorator_async_handler():
    @ToolRegistry.register(country="pe", description="demo tool")
    async def my_tool(x: int = 1) -> int:
        return x * 2

    tool = ToolRegistry.get("pe", "my_tool")
    assert tool is not None
    assert tool.country == "pe"
    assert tool.description == "demo tool"
    assert await tool.handler(x=5) == 10


@pytest.mark.asyncio
async def test_get_tools_for_filters_allowed():
    async def a():
        return None

    ToolRegistry.register_tool(ToolDef(name="a", country="pe", handler=a))
    ToolRegistry.register_tool(ToolDef(name="b", country="pe", handler=a))
    ToolRegistry.register_tool(ToolDef(name="c", country="cl", handler=a))

    tools = ToolRegistry.get_tools_for("pe", ["a", "c", "missing"])
    names = sorted(t.name for t in tools)
    # 'c' is cl, not pe; 'missing' doesn't exist
    assert names == ["a"]


def test_qualified_name():
    async def h():
        return None

    t = ToolDef(name="foo", country="pe", handler=h)
    assert t.qualified_name == "pe:foo"


def test_clear_and_all():
    async def h():
        return None

    ToolRegistry.register_tool(ToolDef(name="x", country="pe", handler=h))
    assert len(ToolRegistry.all()) == 1
    ToolRegistry.clear()
    assert ToolRegistry.all() == []
