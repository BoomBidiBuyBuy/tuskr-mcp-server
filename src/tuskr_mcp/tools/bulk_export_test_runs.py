"""The bulk_export_test_runs tool, and the trimming and size guard it needs.

The helpers stay in this module rather than a shared one: they are used by this
tool alone, and a shared helper module would be a file every future tool branch
has to touch.
"""

import json

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp

# Fields kept from each test case nested in an exported run. The raw case row
# carries the full instruction and expected-result text, preconditions, field
# sets and the latest result's comments, about 2 KB per case. A run holds
# hundreds of cases and a page holds up to 100 runs, so a page measured tens of
# megabytes live. What stays is what identifies the case and says how it did.
# The API's own key capitalisation is kept as is.
_TEST_CASE_FIELDS = (
    "ID",
    "Key",
    "Name",
    "Suite",
    "Section",
    "Assigned To",
    "Result Status",
    "Result Created At",
    "Result Created By",
    "Result Issue Ids",
)

# MCP clients reject tool responses of about 1 MB. Stay under that with margin.
_MAX_RESPONSE_BYTES = 900_000


def _as_csv(value):
    """Render a str-or-list argument in the comma separated form Tuskr expects.

    Returns None for an absent value so the caller can leave the query
    parameter out entirely rather than sending an empty filter.
    """
    if value is None:
        return None
    if isinstance(value, str):
        return value or None
    joined = ",".join(str(item) for item in value)
    return joined or None


def _trim_test_case(case):
    """Reduce one nested test case to its identifying and result fields."""
    if not isinstance(case, dict):
        return case
    return {key: case[key] for key in _TEST_CASE_FIELDS if key in case}


def trim_export(raw):
    """Trim the test cases nested in every row of a raw bulk-export response.

    Takes and returns the JSON text `tuskr_client.send` produces, so every
    run-level field reaches the caller exactly as the API sent it. A payload
    that is not a JSON object carrying a `rows` list is returned untouched,
    which keeps error bodies readable. Rows without test cases, as returned
    when they are excluded, pass through as they are.
    """
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return raw

    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        return raw

    for row in data["rows"]:
        if isinstance(row, dict) and isinstance(row.get("testCases"), list):
            row["testCases"] = [_trim_test_case(case) for case in row["testCases"]]

    return json.dumps(data)


def enforce_size_cap(raw):
    """Replace a response too large for an MCP client with an explanation.

    A transport-level rejection tells the caller nothing; this says what was
    too big and which arguments narrow it. Only a JSON object carrying a
    `rows` list is measured, so other bodies, error pages included, are
    returned untouched.
    """
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return raw

    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        return raw

    size = len(raw.encode("utf-8"))
    if size <= _MAX_RESPONSE_BYTES:
        return raw

    return json.dumps(
        {
            "error": (
                f"Response is {size} bytes, over the {_MAX_RESPONSE_BYTES} byte "
                "limit MCP clients accept, so it was not returned. Narrow it "
                "with filter_ids (test run IDs), filter_status, "
                "filter_completion_status or filter_assigned_to, or set "
                "filter_exclude_test_cases to True."
            ),
            "response_bytes": size,
            "count": data.get("count"),
            "meta": data.get("meta"),
        }
    )


@mcp.tool
async def bulk_export_test_runs(
    ctx: Context,
    filter_project,
    filter_exclude_test_cases: bool = False,
    filter_assigned_to: str | None = None,
    filter_ids: str | list[str] | None = None,
    filter_status: str | None = None,
    filter_completion_status: str | None = None,
    page: int = 1,
    trim_response: bool = True,
):
    """
    Exports test runs of a project together with their test cases and the
    latest result of each case, in one call.

    One call can return several runs, where get_test_run_results needs a call
    per run and per page. Always narrow the export with filter_ids or the other
    filters when test cases are included: a project's runs with all their cases
    run to tens of megabytes. A response over the MCP size limit is replaced
    by an error saying how large it was and how to narrow it.

    Run fields and the response envelope ({count, rows, meta}) are passed
    through as the API sends them, keys in the API's own capitalisation.

    Args:
        filter_project: ID of the project whose test runs are exported
        filter_exclude_test_cases: if True, rows carry the runs without their
            test cases, a few hundred bytes each. The API has been seen to
            return every matching run on the first page in this mode.
            Default is False.
        filter_assigned_to: id of the user to whom test runs are assigned
        filter_ids: a test run ID, or a list of them, to export only those
            runs. These are the run IDs (UUIDs) the API returns, not the
            R-numbered keys: a key matches no run.
        filter_status: to filter test runs by their status. Two supported
            values 'active' or 'archived'
        filter_completion_status: to filter test runs by completion. Two
            supported values 'completed' or 'incomplete'
        page: page number to fetch, 100 runs per page. Default is 1.
        trim_response: if True (default), each nested test case is reduced to
            ID, Key, Name, Suite, Section, Assigned To, Result Status,
            Result Created At, Result Created By and Result Issue Ids. The full
            case also carries its steps, expected results, preconditions and
            the latest result's comments, about 2 KB per case. Set it to False
            when those are genuinely needed, and narrow the export to a few
            runs.
    """
    params = {"filter[project]": filter_project}

    if filter_exclude_test_cases:
        params["filter[excludeTestCases]"] = "true"
    if filter_assigned_to:
        params["filter[assignedTo]"] = filter_assigned_to

    ids_param = _as_csv(filter_ids)
    if ids_param:
        params["filter[ids]"] = ids_param

    if filter_status:
        params["filter[status]"] = filter_status
    if filter_completion_status:
        params["filter[completionStatus]"] = filter_completion_status

    tenant_id, access_token = await credentials.resolve(ctx)

    raw = tuskr_client.send(
        "test-run/bulk-export",
        {"page": page, **params},
        tuskr_client.RequestMethod.GET,
        ext_tenant_id=tenant_id,
        ext_access_token=access_token,
    )

    if trim_response:
        raw = trim_export(raw)

    return enforce_size_cap(raw)
