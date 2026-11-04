"""The import_test_cases tool."""

from typing import Any

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp


@mcp.tool
async def import_test_cases(
    ctx: Context,
    project: str,
    test_cases: list[dict[str, Any]],
    create_missing_suites: bool = False,
    create_missing_sections: bool = False,
):
    """
    Imports many test cases into a project in one call and returns a summary.

    The import can partially succeed. Tuskr answers HTTP 200 even when some
    records were rejected, so always read the summary: `totalTestCases`,
    `successCount`, `errorCount`, and `rowsWithError`, which lists each
    rejected record by its `record` index with an `errorMessage`. A non-zero
    `errorCount` means those records were not imported; fix them and import
    only those records again. A response that is not this summary is Tuskr's
    error message for the whole request.

    The import is not idempotent: running the same records twice creates
    duplicate test cases, and the Tuskr API has no endpoint to delete test
    cases. To re-run safely, use upsert_test_case with an external ID instead.
    Use a sandbox project while experimenting.

    Each object in `test_cases` uses Tuskr's own keys and is sent unchanged:
    `name`, `description`, `testSuite`, `testSuiteSection`, `testCaseType`,
    `estimatedTimeInMinutes` and `customFields`, the same fields as
    add_test_case. Custom-field keys and value shapes are specific to the
    tenant.

    Args:
        project: ID or name of the project to import into
        test_cases: list of test case objects, at least one
        create_missing_suites: create a test suite named in a record when it
            does not exist in the project (Tuskr default: it does not, and
            returns an error)
        create_missing_sections: create a section named in a record when it
            does not exist in the suite (Tuskr default: it does not, and
            returns an error)
    """
    if not test_cases:
        raise ValueError("Provide at least one test case to import.")

    body: dict[str, Any] = {"project": project, "testCases": test_cases}

    # The import endpoint's option keys are plural, unlike upsert's
    # createMissingSuite and createMissingSection. Tuskr defaults both to
    # false, so send only the ones the caller enabled.
    options = {}
    if create_missing_suites:
        options["createMissingSuites"] = True
    if create_missing_sections:
        options["createMissingSections"] = True
    if options:
        body["options"] = options

    tenant_id, access_token = await credentials.resolve(ctx)

    return tuskr_client.send(
        "test-case/import",
        body,
        tuskr_client.RequestMethod.POST,
        ext_tenant_id=tenant_id,
        ext_access_token=access_token,
    )
