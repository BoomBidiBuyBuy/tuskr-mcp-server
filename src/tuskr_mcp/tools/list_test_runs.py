"""The list_test_runs tool, and the assignee trimming it needs.

The trimming helpers stay in this module rather than a shared one: they are used
by this tool alone, and a shared trimming module would be a file every future
tool branch has to touch.
"""

import json

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp

# Identifying fields kept from a Tuskr user object. The raw object also carries
# an `applicationState` UI blob (menu state and cached announcement text, up to
# ~16 KB per user) plus per-account security metadata such as
# `passwordResetTokenExpiresAt`, `jwtTokenInvalidBefore` and `lastLoginAt`.
# None of that is useful to a caller, and passing it through both defeats the
# trimming and puts account metadata into model context.
_ASSIGNEE_FIELDS = ("id", "fullName", "email")


def trim_assignee(assignee):
    """Reduce a Tuskr user object to its identifying fields.

    Returns the value unchanged when it is not a user object (e.g. None for an
    unassigned test run), so the response shape stays stable for callers.
    """
    if not isinstance(assignee, dict):
        return assignee
    return {key: assignee[key] for key in _ASSIGNEE_FIELDS if key in assignee}


def trim_test_run_rows(raw):
    """Trim the assignee on every row of a raw Tuskr test-run response.

    Takes and returns the JSON text `tuskr_client.send` produces, so every
    other field reaches the caller exactly as the API sent it. A payload that
    is not a JSON object carrying a `rows` list is returned untouched, which
    keeps error bodies and any future response shape readable rather than
    silently emptied.
    """
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return raw

    if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
        return raw

    for row in data["rows"]:
        if isinstance(row, dict) and "assignedTo" in row:
            row["assignedTo"] = trim_assignee(row["assignedTo"])

    return json.dumps(data)


@mcp.tool
async def list_test_runs(
    ctx: Context,
    filter_project: str,
    filter_name: str | None = None,
    filter_key: str | None = None,
    filter_status: str | None = None,
    filter_assigned_to: str | None = None,
    filter_incomplete: bool = False,
    page: int = 1,
):
    """
    Retrieves list of test runs of a project with support for various filters.

    Args:
        filter_project: specifies the project ID to filter the test runs associated with a particular project
        filter_name: to filter test runs with name containing the specified value
        filter_key: to filter test runs with key containing the specified value
        filter_status: to filter test runs by their status. Two supported values 'active' or 'archived'
        filter_assigned_to: id of the user to whom test runs are assigned
        filter_incomplete: if True, fetches all pages and returns only test runs that are not 100% complete,
            with a trimmed payload (id, key, name, percentDone, counts, assignee, deadline, status).
            When False (default), returns the paginated response from the Tuskr API with every field
            intact. Either way the assignee on each row is reduced to id, fullName and email.
        page: controls number of records in output, every page contains 100 records. Default is 1.
            Ignored when filter_incomplete is True.
    """
    params = {"filter[project]": filter_project}

    if filter_name:
        params["filter[name]"] = filter_name
    if filter_key:
        params["filter[key]"] = filter_key
    if filter_status:
        params["filter[status]"] = filter_status
    if filter_assigned_to:
        params["filter[assignedTo]"] = filter_assigned_to

    # Resolve credentials once up front so we don't re-await on every page.
    tenant_id, access_token = await credentials.resolve(ctx)

    if not filter_incomplete:
        # Trim the assignee here too: this path returns whole rows, so without
        # it the largest single source of bulk and the account security
        # metadata both reach the caller on the default call.
        return trim_test_run_rows(
            tuskr_client.send(
                "test-run",
                {"page": page, **params},
                tuskr_client.RequestMethod.GET,
                ext_tenant_id=tenant_id,
                ext_access_token=access_token,
            )
        )

    # Fetch all pages and filter for incomplete runs client-side,
    # returning a trimmed payload to stay under MCP transport size limits.
    incomplete = []
    current_page = 1
    while True:
        raw = tuskr_client.send(
            "test-run",
            {"page": current_page, **params},
            tuskr_client.RequestMethod.GET,
            ext_tenant_id=tenant_id,
            ext_access_token=access_token,
        )
        data = json.loads(raw)
        rows = data.get("rows", [])
        for run in rows:
            percent = run.get("percentDone", 100)
            if percent < 100:
                incomplete.append(
                    {
                        "id": run.get("id"),
                        "key": run.get("key"),
                        "name": run.get("name"),
                        "percentDone": percent,
                        "totalTestCaseCount": run.get("totalTestCaseCount", 0),
                        "doneTestCaseCount": run.get("doneTestCaseCount", 0),
                        "assignedTo": trim_assignee(run.get("assignedTo")),
                        "deadline": run.get("deadline"),
                        "status": run.get("status"),
                    }
                )
        meta = data.get("meta", {})
        if current_page >= meta.get("pages", 1):
            break
        current_page += 1

    return json.dumps({"rows": incomplete, "count": len(incomplete)})
