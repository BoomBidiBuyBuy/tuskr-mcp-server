"""The get_test_run_details tool."""

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp


@mcp.tool
async def get_test_run_details(
    ctx: Context,
    test_run: str,
):
    """
    Fetches a test run's details, including when execution started and ended.

    Besides the run's metadata (id, key, name, project, description,
    references, assignedTo, externalId, deadline, status), the response
    carries three timing fields:

    - firstResultAt: timestamp of the first result marked in the run
    - lastResultAt: timestamp of the last result marked in the run
    - durationInMinutes: time between the two, computed by Tuskr

    This is the direct way to answer "when did this run finish" or "how long
    did execution take". Deriving the same from each case's resultHistory via
    get_test_run_results is slower and needs one large call per run.

    Caveat: Tuskr says it timestamps only results marked after this endpoint
    shipped (8 Sept 2026), so older runs may return null firstResultAt and
    lastResultAt with a meaningless durationInMinutes. This is not guaranteed:
    a run whose only result predates the release still returned real
    timestamps. A run with no results also returns nulls. A null therefore
    means unknown, not "no results yet"; check the run's results before
    concluding that.

    The endpoint takes one test run per call. Tuskr rate-limits every plan at
    10 requests/second.

    Args:
        test_run: ID (UUID) of the test run. A key such as "R-2" is rejected
            with "Invalid test run ID". Resolve a key to its ID with
            list_test_runs(filter_key=...).
    """
    tenant_id, access_token = await credentials.resolve(ctx)

    return tuskr_client.send(
        f"test-run/{test_run}/details",
        {},
        tuskr_client.RequestMethod.GET,
        ext_tenant_id=tenant_id,
        ext_access_token=access_token,
    )
