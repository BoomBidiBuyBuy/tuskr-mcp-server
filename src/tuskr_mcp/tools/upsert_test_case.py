"""The upsert_test_case tool."""

from typing import Any

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp


@mcp.tool
async def upsert_test_case(
    ctx: Context,
    project: str,
    test_case_id: str = "",
    external_id: str = "",
    name: str = "",
    test_suite: str = "",
    test_suite_section: str = "",
    description: str = "",
    test_case_type: str = "",
    estimated_time_in_minutes: int | None = None,
    custom_fields: dict[str, Any] | None = None,
    create_missing_suite: bool = False,
    create_missing_section: bool = False,
):
    """
    Creates a test case or updates an existing one, and returns it.

    This tool can both create new test cases and modify existing ones. Exactly
    one of `test_case_id` or `external_id` must be given:
    - `test_case_id` updates the test case with that ID; the case must already exist.
    - `external_id` updates the case with that external ID in the project, or
      creates a new case carrying that external ID when none exists.

    Only the fields you pass are sent. A field left unset keeps its current
    value on an update, so this tool cannot clear a field to empty. Pass `name`
    when the call may create a case.

    Args:
        project: ID, name or external ID of the project
        test_case_id: UUID of an existing test case to update
        external_id: external ID used to find the case to update, or to assign
            to the case being created
        name: name of the test case
        test_suite: ID or name of the test suite
        test_suite_section: ID or name of the section in the suite
        description: description of the test case
        test_case_type: ID or name of the test case type
        estimated_time_in_minutes: estimated execution time, whole minutes
        custom_fields: object of custom field values, keyed by the field's key.
            Keys and value shapes are specific to the tenant and depend on the
            field type. Tuskr's own example uses `stepsWithExpectedResults`,
            a `multi_select` field and a `date` field.
        create_missing_suite: create the test suite when it does not exist
            (Tuskr default: it does not)
        create_missing_section: create the section when it does not exist
            (Tuskr default: it does not)
    """
    if not test_case_id and not external_id:
        raise ValueError("Provide either `test_case_id` or `external_id`.")
    if test_case_id and external_id:
        raise ValueError(
            "Provide only one of `test_case_id` or `external_id`, not both."
        )

    body: dict[str, Any] = {"project": project}

    # Only send keys the caller actually set. On an update a blank value sent
    # by mistake could overwrite real data, and Tuskr resolves suite, section
    # and type against existing records, so a blank is a failed lookup rather
    # than a no-op. The estimate is tested against None so that 0 is still sent.
    if test_case_id:
        body["id"] = test_case_id
    if external_id:
        body["externalId"] = external_id
    if name:
        body["name"] = name
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

    options = {}
    if create_missing_suite:
        options["createMissingSuite"] = True
    if create_missing_section:
        options["createMissingSection"] = True
    if options:
        body["options"] = options

    tenant_id, access_token = await credentials.resolve(ctx)

    return tuskr_client.send(
        "test-case/upsert",
        body,
        tuskr_client.RequestMethod.POST,
        ext_tenant_id=tenant_id,
        ext_access_token=access_token,
    )
