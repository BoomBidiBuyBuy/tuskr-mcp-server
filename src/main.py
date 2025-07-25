import os

from typing import Annotated, List
from fastmcp import FastMCP, settings
from pydantic import Field

import tuskr_client


mcp = FastMCP(
    name="Tuskr MCP Service",
    host=os.environ.get("MCP_HOST", settings.host),
    port=os.environ.get("MCP_PORT", settings.port)
)


@mcp.tool()
def list_projects(
        filter_name: str = None,
        filter_status: str = None,
        page: int = 1
    ):
    """
    Retrives list of projects based on various filter criteria.

    Args:
        filter_name: optional parameter to filter projects with name containing the specified value
        filter_status: optional paramter to filter projects by their status. Two supported values 'active' or 'archived'
        page: controls number of records in output, every page contains 100 records. Default is 1.
    """
    params = dict()
    if filter_name:
        params["filter[name]"] = filter_name
    if filter_status:
        params["filter[status]"] = filter_status
    return tuskr_client.send(
            "project",
            {
                "page": page,
                **params
            },
            tuskr_client.RequestMethod.GET
        )


@mcp.tool()
def create_test_run(
        name: str,
        project: str,
        test_case_inclusion_type: str,
        test_cases: List[str] = None,
        description: str = '',
        deadlinee: str = '',
        assigned_to: str = ''
    ):
    """
    Creates a new test run in a project.

    Args:
        name: a new test run name
        project: name or project ID where to create a test run
        test_case_inclusion_type: One of 'ALL' or 'SPECIFIC'. If you specify 'ALL', all test cases in the project will be included in the test run.
                                  If you specify 'SPECIFIC', then you will have to indicate the test cases to include as explained below.
        test_cases: list of IDs, keys or names. Required if you have set `test_case_inclusion_type` to 'SPECIFIC'.
        description: description of a test run
        deadline: YYYY-MM-DD date
        assigned_to: ID, name, or email of the user. If specified, the test run will be assigned to this user
    """
    return tuskr_client.send(
            "test-run",
            {
                "name": name,
                "project": project,
                "testCaseInclusionType": test_case_inclusion_type,
                "testCases": test_cases,
                "description": description,
                "deadline": deadline,
                "assignedTo": assignedTo
            },
            tuskr_client.ReuqestMethod.POST
        )


def main():
    mcp.run(transport="http")


if __name__ == "__main__":
    main()
