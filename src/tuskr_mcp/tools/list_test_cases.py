"""The list_test_cases tool."""

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp


@mcp.tool
async def list_test_cases(
    ctx: Context,
    filter_project: str,
    filter_test_suite: str | None = None,
    filter_test_suite_section: str | None = None,
    filter_key: str | None = None,
    filter_name: str | None = None,
    filter_test_case_type: str | None = None,
    filter_custom_fields: dict[str, str | int | float | bool | list[str]] | None = None,
    page: int = 1,
):
    """
    Retrieves list of test cases of a project with support for various filters.

    Use this to discover the test case keys a project actually contains before
    recording results against them with add_test_run_results.

    Args:
        filter_project: specifies the project ID to filter the test cases associated with a particular project
        filter_test_suite: ID of the test suite to filter the test cases by. Only
            the ID works: a suite's key or name returns zero rows, not an error.
            Find suite IDs with list_test_suites.
        filter_test_suite_section: ID of the test suite section to filter the test
            cases by. Only the ID works: a section name returns zero rows. Find
            section IDs with list_test_suites.
        filter_key: to filter test cases with key containing the specified value
        filter_name: to filter test cases with name containing the specified value
        filter_test_case_type: ID of the test case type to filter by. Read the ID off
            the testCaseTypeId field of any case row. Only the ID form is verified;
            a type's displayed name is untested as a filter value. Verified live:
            a valid ID narrows the result set, and an unknown value returns zero
            rows rather than an error or the unfiltered set, so an empty result can
            mean a mistyped ID, not that no case has that type.
        filter_custom_fields: maps a custom field's key to the value to filter on,
            e.g. {'priority_band': '<option-id>'}. The field key is whatever the
            tenant named it, so any project's own field set can be filtered here.
            Only fields applicable to test cases can be filtered; a field scoped
            to test run results is not reachable through this endpoint.
            Verified live by field type:
              dropdown: pass the option's ID, not its displayed label. Read the
                ID off any case that already has the field set, where it is
                returned inline as customFields.<field>.id.
              checkbox: pass a bool or the lowercase string 'true'/'false'. A
                bool is normalised to the lowercase form Tuskr expects.
              text: matches on substring, not equality.
              steps: NOT filterable. Tuskr accepts the parameter and returns
                every case in the project unfiltered.
            Numbers and multi-select remain unverified.
            Tuskr ignores a filter it does not understand instead of rejecting
            it, so a filter that fails to narrow the results means the field
            type or value shape is unsupported, not that nothing matched.
        page: controls number of records in output, every page contains 100 records. Default is 1.
    """
    params = {"filter[project]": filter_project}

    if filter_test_suite:
        params["filter[testSuite]"] = filter_test_suite
    if filter_test_suite_section:
        params["filter[testSuiteSection]"] = filter_test_suite_section
    if filter_key:
        params["filter[key]"] = filter_key
    if filter_name:
        params["filter[name]"] = filter_name
    if filter_test_case_type:
        params["filter[testCaseType]"] = filter_test_case_type

    # Each custom field gets its own flattened bracket key. An earlier attempt
    # sent the whole mapping as one JSON-encoded filter[customFields] value,
    # which Tuskr ignored silently rather than rejecting, returning every case
    # in the project as though no filter had been applied.
    #
    # Booleans are normalised to lowercase strings. Tuskr matches the literal
    # text it receives for a checkbox field, and requests renders a Python bool
    # via str(), producing 'True'. Live-verified: sending 'True' returned 1369
    # of 1918 rows, most of them false, a plausible-looking but wrong result
    # rather than an error or the unfiltered set. Sending 'true' returned
    # exactly the 7 true rows out of a 38-row sample. The isinstance check has
    # to precede any int handling because bool is a subclass of int.
    if filter_custom_fields:
        for field, value in filter_custom_fields.items():
            if isinstance(value, bool):
                value = "true" if value else "false"
            params[f"filter[customFields][{field}]"] = value

    tenant_id, access_token = await credentials.resolve(ctx)

    return tuskr_client.send(
        "test-case",
        {"page": page, **params},
        tuskr_client.RequestMethod.GET,
        ext_tenant_id=tenant_id,
        ext_access_token=access_token,
    )
