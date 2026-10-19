"""The update_test_run tool."""

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp

_INCLUSION_TYPES = ("ALL", "SPECIFIC")


@mcp.tool
async def update_test_run(
    ctx: Context,
    test_run: str,
    test_case_inclusion_type: str,
    test_cases: str | list[str] | None = None,
    name: str = "",
    project: str = "",
):
    """
    Adds test cases to an existing test run and removes test cases from it.

    This is how to change which cases a run contains after it was created. It
    also switches a run between ALL and SPECIFIC case selection. Do not use
    add_test_run_results to add a case: recording a result for a case that is
    not in the run returns an empty list and stores nothing. Do not use
    copy_test_run either, which resets every result.

    To add a case: read the run's current case IDs with get_test_run_results
    (the testCase.id of each row), append the new case's ID (the id of a
    list_test_cases row), and send the full list as test_cases.

    To remove a case: send the run's current case IDs without that case. A case
    that already has a result in this run cannot be removed. Tuskr then answers
    HTTP 400 "Cannot remove test case because it already has results: <case
    name>", and this tool returns that text as is.

    test_cases is the complete selection, not a delta: it replaces the current
    one, so any case left out is removed. Cases that stay in the selection keep
    the results already recorded for them, also across a switch to ALL and back.

    Switching from SPECIFIC to ALL takes no test_cases. Switching from ALL to
    SPECIFIC needs test_cases to include every case that already has a result in
    the run.

    Every identifier here is a UUID, unlike create_test_run: keys and names are
    not accepted for the run, the project or the cases. The tool never sends the
    run's description, deadline or assignee, and a description stays unchanged.
    On success Tuskr returns the updated run.

    Args:
        test_run: ID (UUID) of the test run to update. list_test_runs returns it.
        test_case_inclusion_type: 'ALL' or 'SPECIFIC' (case-insensitive). With
            'ALL' the run holds every case in the project and test_cases must
            be omitted. With 'SPECIFIC' test_cases is required.
        test_cases: for 'SPECIFIC', the IDs (UUIDs) of every case the run should
            hold afterwards: a single ID or a list of them.
        name: new name for the run. Leave unset to keep the current name.
        project: ID (UUID) of the project the run belongs to. Leave unset to
            keep the run in its current project.
    """
    inclusion_type = test_case_inclusion_type.upper()
    if inclusion_type not in _INCLUSION_TYPES:
        raise ValueError(
            "test_case_inclusion_type must be 'ALL' or 'SPECIFIC', "
            f"got '{test_case_inclusion_type}'."
        )

    if isinstance(test_cases, str):
        test_cases = [test_cases]

    if inclusion_type == "SPECIFIC" and not test_cases:
        raise ValueError(
            "test_cases is required when test_case_inclusion_type is 'SPECIFIC'."
        )
    if inclusion_type == "ALL" and test_cases:
        raise ValueError(
            "test_cases cannot be combined with test_case_inclusion_type 'ALL'."
        )

    data = {"testCaseInclusionType": inclusion_type}

    # Tuskr accepts this call without a name or a project and then leaves both
    # as they are (verified live, each omitted on its own), so only send what
    # the caller set.
    if name:
        data["name"] = name
    if project:
        data["project"] = project
    if inclusion_type == "SPECIFIC":
        data["testCases"] = test_cases

    tenant_id, access_token = await credentials.resolve(ctx)

    # The run ID goes in the URL and again beside `data`, not inside it. Without
    # the top-level id Tuskr answers HTTP 500 with an undefined-id error.
    return tuskr_client.send(
        f"test-run/{test_run}",
        data,
        tuskr_client.RequestMethod.PUT,
        ext_tenant_id=tenant_id,
        ext_access_token=access_token,
        top_level={"id": test_run},
    )
