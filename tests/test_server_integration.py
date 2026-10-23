"""End-to-end credential flow through fastmcp's real Context and middleware.

These run the actual server object, so they catch what the unit tests cannot:
a state call that is not awaited silently drops the caller's headers.
"""

import asyncio
import json

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.utilities.tests import run_server_async

import main


def _list_projects(client_factory):
    async def run():
        async with client_factory() as client:
            result = await client.call_tool("list_projects", {})
            return result.content[0].text

    return asyncio.run(run())


def _credentials_sent(send):
    kwargs = send.call_args.kwargs
    return kwargs["ext_tenant_id"], kwargs["ext_access_token"]


def test_in_process_client_falls_back_to_env(env, send):
    _list_projects(lambda: Client(main.mcp))

    assert _credentials_sent(send) == ("tenant-from-env", "token-from-env")


def test_http_headers_win_and_env_is_the_fallback(env, send):
    # A real uvicorn server on a free loopback port, so the requests go through
    # the same HTTP stack and middleware as a deployed instance. Both calls
    # share one server: fastmcp's run state is bound to the first event loop,
    # so the server object cannot be started again under a second asyncio.run.
    headers = {"Authorization": "Bearer token-header", "Tenant-ID": "tenant-header"}
    sent = []

    async def call(url, client_headers):
        async with Client(StreamableHttpTransport(url, headers=client_headers)) as c:
            await c.call_tool("list_projects", {})
        sent.append(_credentials_sent(send))

    async def run():
        async with run_server_async(main.mcp) as url:
            await call(url, headers)
            await call(url, {})

    asyncio.run(run())

    assert sent == [
        ("tenant-header", "token-header"),
        ("tenant-from-env", "token-from-env"),
    ]


def test_service_description_resource():
    async def run():
        async with Client(main.mcp) as client:
            return await client.read_resource("resource://service_description")

    text = asyncio.run(run())[0].text

    assert "Tuskr" in text


def test_list_projects_returns_the_api_text(env, send):
    send.return_value = json.dumps({"rows": []})

    assert json.loads(_list_projects(lambda: Client(main.mcp))) == {"rows": []}
