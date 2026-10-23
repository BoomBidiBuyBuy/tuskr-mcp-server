"""The add_test_case tool."""

from typing import Any

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp


@mcp.tool
async def add_test_case(
    ctx: Context,
    name: str,
    project: str,
    test_suite: str = "",
    test_suite_section: str = "",
    description: str = "",
    test_case_type: str = "",
    estimated_time_in_minutes: int | None = None,
    custom_fields: dict[str, Any] | None = None,
):
    """
    Creates a new test case in a project and returns it.

    The test suite and section must already exist: this tool does not create
    them. There is no delete endpoint for test cases in the Tuskr API, so use
    a sandbox project while experimenting and name throwaway cases clearly.

    Pass `test_case_type` as well: Tuskr rejects a create without one with
    "Type is required", at least on a tenant with no default type. Find a
    type's ID on the testCaseTypeId field of any list_test_cases row.

    Args:
        name: name of the new test case
        project: ID or name of the project where to create the test case
        test_suite: ID or name of an existing test suite
        test_suite_section: ID or name of an existing section in the suite
        description: description of the test case
        test_case_type: ID or name of the test case type. Leave it unset
            only if the tenant has a default type
        estimated_time_in_minutes: estimated execution time, whole minutes,
            at least 1. Tuskr silently replaces 0 with its default (15), so
            0 is rejected here before any request
        custom_fields: object of custom field values, keyed by the field's key.
            Keys and value shapes are specific to the tenant and depend on the
            field type. Tuskr's own example uses `stepsWithExpectedResults`,
            a `multi_select` field and a `date` field.
    """
    if estimated_time_in_minutes is not None and estimated_time_in_minutes < 1:
        raise ValueError(
            "estimated_time_in_minutes must be at least 1; leave it unset to "
            "use Tuskr's default."
        )

    body: dict[str, Any] = {"name": name, "project": project}

    # Only send optional keys the caller actually set. Tuskr resolves the
    # suite, section and type against existing records, so a blank value is a
    # lookup that fails rather than a no-op.
    if test_suite:
        body["testSuite"] = test_suite
    if test_suite_section:
        body["testSuiteSection"] = test_suite_section
    if description:
        body["description"] = description
    if test_case_type:
        body["testCaseType"] = test_case_type
    if estimated_time_in_minutes is not None:
        body["estimatedTimeInMinutes"] = estimated_time_in_minutes
    if custom_fields:
        body["customFields"] = custom_fields

    tenant_id, access_token = await credentials.resolve(ctx)

    return tuskr_client.send(
        "test-case",
        body,
        tuskr_client.RequestMethod.POST,
        ext_tenant_id=tenant_id,
        ext_access_token=access_token,
    )
