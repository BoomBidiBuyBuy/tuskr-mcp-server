from typing import Annotated, List
from fastmp import FastMCP
from pydantic import Field

import tuskr_client


mcp = FastMCP(
    name="Tuskr MCP Service"
    description="Provides tools to talk Tuskr test management system"
)


@mcp.tool()
def create_test_run(
        name: Annotated[
            str,
            Field(description="Name for a new test run"),
        ],
        project: Annotated[
            str,
            Field(description="Name or ID project where to create a test run")
        ]
        test_case_inclusion_type: Annotated[
            str,
            Field(description="One of 'ALL' or 'SPECIFIC'. If you specify 'ALL', all test cases in the project will be included in the test run.
                  If you specify 'SPECIFIC', then you will have to indicate the test cases to include as explained below.")
        ],
        test_cases: Annotated[
            List[str] = None,
            Field(description="List of of IDs, keys or names. Required if you have specified `test_case_inclusion_type` as 'SPECIFIC'.")
        ]
        description: str = '',
        deadlinee: str = '',
        assigned_to: str = ''
    ):
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
    print("Hello from tuskr-mcp-server!")


if __name__ == "__main__":
    main()
