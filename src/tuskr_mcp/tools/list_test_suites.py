"""The list_test_suites tool."""

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp


@mcp.tool
async def list_test_suites(
    ctx: Context,
    filter_project: str,
    filter_name: str | None = None,
    page: int = 1,
):
    """
    Retrieves list of test suites and their associated sections in a project.

    Use this to discover suite and section IDs. Pass them to list_test_cases as
    filter_test_suite and filter_test_suite_section instead of reading the IDs
    off existing test case rows.

    Each suite row embeds its sections. Returns Tuskr's raw rows, count and meta
    for a single page; this tool does not fetch further pages.

    Args:
        filter_project: specifies the project ID to list the test suites of. Required.
        filter_name: to filter test suites with name containing the specified value
        page: controls number of records in output, every page contains 100 records. Default is 1.
    """
    params = {"page": page, "filter[project]": filter_project}

    if filter_name:
        params["filter[name]"] = filter_name

    tenant_id, access_token = await credentials.resolve(ctx)

    return tuskr_client.send(
        "test-suite",
        params,
        tuskr_client.RequestMethod.GET,
        ext_tenant_id=tenant_id,
        ext_access_token=access_token,
    )
