"""The create_project tool."""

from typing import Any

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp

_STATUSES = ("active", "archived")


@mcp.tool
async def create_project(
    ctx: Context,
    name: str,
    team: dict[str, str],
    description: str = "",
    status: str = "",
    external_id: str = "",
    issue_url_template: str = "",
    reference_url_template: str = "",
    integration_data: dict[str, Any] | None = None,
):
    """
    Creates a new project and returns it.

    The Tuskr API has no delete endpoint for projects, so a project created
    here can only be removed in the Tuskr UI. Use a throwaway name and
    `status="archived"` while experimenting.

    Args:
        name: name of the new project
        team: object mapping a team member's email address to a role name,
            for example `{"user@example.com": "Tester"}`. At least one entry
            is required. Role names are configured per tenant, so they are
            passed through unchecked.
        description: description of the project
        status: `active` or `archived`. Leave it unset to use Tuskr's default
        external_id: ID of the project in an external system
        issue_url_template: URL template for links to issues in an external
            tracker
        reference_url_template: URL template for links to external references
        integration_data: object of integration settings, passed through as is
    """
    if not isinstance(team, dict) or not team:
        raise ValueError(
            "team must be a non-empty object mapping an email address to a role "
            'name, for example {"user@example.com": "Tester"}.'
        )
    for email, role in team.items():
        if not isinstance(email, str) or not email.strip():
            raise ValueError("team keys must be non-empty email address strings.")
        if not isinstance(role, str) or not role.strip():
            raise ValueError(f"team role for {email!r} must be a non-empty string.")

    if status and status not in _STATUSES:
        raise ValueError(
            f"status must be one of {', '.join(_STATUSES)}; got {status!r}."
        )

    body: dict[str, Any] = {"name": name, "team": team}

    # Only send optional keys the caller actually set, so a blank value cannot
    # overwrite one of Tuskr's defaults.
    if description:
        body["description"] = description
    if status:
        body["status"] = status
    if external_id:
        body["externalId"] = external_id
    if issue_url_template:
        body["issueUrlTemplate"] = issue_url_template
    if reference_url_template:
        body["referenceUrlTemplate"] = reference_url_template
    if integration_data:
        body["integrationData"] = integration_data

    tenant_id, access_token = await credentials.resolve(ctx)

    return tuskr_client.send(
        "project",
        body,
        tuskr_client.RequestMethod.POST,
        ext_tenant_id=tenant_id,
        ext_access_token=access_token,
    )
