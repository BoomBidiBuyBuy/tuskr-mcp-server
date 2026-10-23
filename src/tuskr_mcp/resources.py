"""MCP resources exposed alongside the tools."""

from tuskr_mcp.server import mcp


@mcp.resource("resource://service_description")
def service_description():
    return """This MCP service provides tools to manage projects, test cases, test suites,
    test runs and other resources in Tuskr"""
