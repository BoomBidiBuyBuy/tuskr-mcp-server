import logging
import os
import click

from typing import List
from fastmcp import FastMCP, Context

from fastmcp.server.middleware import Middleware, MiddlewareContext

import tuskr_client


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


class UserTokenHandler(Middleware):
    async def on_call_tool(self, context: MiddlewareContext, call_next):
        """
        Executed on every tool call.
        We intercept it with goal to get secure token
        if it is in the header
        """
        logger.info(f"Raw middleware processing: {context.method}")

        self.retrieve_and_apply_token(context)

        result = await call_next(context)
        logger.info(f"Raw middleware completed: {context.method}")
        return result

    def retrieve_and_apply_token(self, context: MiddlewareContext):
        # get request to reade headers
        request = context.fastmcp_context.request_context.request

        # Read access token
        auth_header = request.headers.get("Authorization")
        token = None

        if auth_header:
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1].strip()
                if not token:
                    raise ValueError(
                        "Unauthorized: Empty Bearer token",
                    )
                logger.info(f"Got Bearer token: {token}")

        context.fastmcp_context.set_state("ext_access_token", token)

        # Try to retrieve account id.
        # It is optional, because account id can be set through env variable
        # in organization on the deployment
        account_header = request.headers.get("Account-ID")
        account_id = None

        if account_header:
            account_id = account_header.strip()

            logger.info(f"Got account id: {account_id}")
        else:
            logger.info("Account id is not defined")

        context.fastmcp_context.set_state("ext_account_id", account_id)


mcp = FastMCP(
    name="Tuskr MCP Service",
)
mcp.add_middleware(UserTokenHandler())


@mcp.tool
def list_projects(
    ctx: Context,
    filter_name: str = None,
    filter_status: str = None,
    page: int = 1,
):
    """
    Retrives list of projects based on various filter criteria.

    Args:
        filter_name: to filter projects with name containing the specified value
        filter_status: to filter projects by their status. Two supported values 'active' or 'archived'
        page: controls number of records in output, every page contains 100 records. Default is 1.
    """
    params = {}

    if filter_name:
        params["filter[name]"] = filter_name
    if filter_status:
        params["filter[status]"] = filter_status
    return tuskr_client.send(
        "project",
        {"page": page, **params},
        tuskr_client.RequestMethod.GET,
        ext_account_id=ctx.get_state("ext_account_id"),
        ext_access_token=ctx.get_state("ext_access_token"),
    )


@mcp.tool
def list_test_runs(
    ctx: Context,
    filter_project,
    filter_name: str = None,
    filter_key: str = None,
    filter_status: str = None,
    filter_assigned_to: str = None,
    page: int = 1,
):
    """
    Retrieves list of test runs of a project with support for various filters.

    Args:
        filter_project: specifies the project ID to filter the test runs associated with a particular project
        filter_name: to filter test runs with name containing the specified value
        fller_key: to filter test runs with key containing the specified value
        filter_status: to filter test runs by their status. Two supported values 'active' or 'archived'
        filter_assigned_to: id of the user to whom test runs are assigned
        page: controls number of records in output, every page contains 100 records. Default is 1.
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

    return tuskr_client.send(
        "test-run",
        {"page": page, **params},
        tuskr_client.RequestMethod.GET,
        ext_account_id=ctx.get_state("ext_account_id"),
        ext_access_token=ctx.get_state("ext_access_token"),
    )


@mcp.tool
def create_test_run(
    ctx: Context,
    name: str,
    project: str,
    test_case_inclusion_type: str,
    test_cases: List[str] = None,
    description: str = "",
    deadline: str = "",
    assigned_to: str = "",
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
            "assignedTo": assigned_to,
        },
        tuskr_client.ReuqestMethod.POST,
        ext_account_id=ctx.get_state("ext_account_id"),
        ext_access_token=ctx.get_state("ext_access_token"),
    )


@mcp.resource("resource://service_description")
def service_description():
    return """This MCP service provides tools to manage projects, test cases, tests suits
    test runs and other resources in Tuskr"""


@click.command()
@click.option("--transport", type=str, default=os.environ.get("MCP_TRANSPORT", "http"))
@click.option("--host", type=str, default=os.environ.get("MCP_HOST", "0.0.0.0"))
@click.option("--port", type=int, default=os.environ.get("MCP_PORT", 8000))
def main(transport, host, port):
    run_params = {}
    if transport == "http":
        run_params["host"] = host
        run_params["port"] = port

    mcp.run(
        transport=transport,
        **run_params,
    )


if __name__ == "__main__":
    main()
