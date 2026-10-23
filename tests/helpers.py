"""Scaffolding shared by the per-tool test modules.

Kept deliberately small and stable: a tool's own fixtures and payload builders
belong in that tool's test module, so a branch adding a tool adds one file and
edits nothing here.
"""

import asyncio


class FakeContext:
    """Minimal stand-in for the FastMCP Context used by the tool functions.

    `get_state` is async because it is async on the real Context from fastmcp
    3.0 on; test_credentials pins that, so this fake cannot drift from it.
    """

    def __init__(self, state=None):
        self._state = state or {}

    async def get_state(self, key):
        return self._state.get(key)


def call_tool(tool, ctx, **kwargs):
    """Invoke an @mcp.tool-decorated coroutine synchronously.

    Depending on the fastmcp version, @mcp.tool either leaves the plain function
    in place or wraps it in a Tool object exposing the original as `.fn`.
    asyncio.run keeps the callers plain sync tests, so the suite needs no
    pytest-asyncio dependency.
    """
    fn = getattr(tool, "fn", tool)
    return asyncio.run(fn(ctx, **kwargs))
