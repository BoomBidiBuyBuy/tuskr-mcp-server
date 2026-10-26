"""The delete_test_runs tool."""

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp


@mcp.tool
async def delete_test_runs(
    ctx: Context,
    projects: str | list[str],
    name_starts_with: str = "",
    older_than_days: int | None = None,
    purge: bool = False,
):
    """
    Deletes the test runs that match a set of filters, in bulk.

    The endpoint selects runs by filter only: it cannot delete one run by ID or
    key. Every run in the given projects that matches all the filters passed is
    deleted, archived runs included, so narrow the call as far as possible and
    check the candidates first with list_test_runs (filter_name;
    filter_status='archived' for archived runs).

    Two guards apply before any request is sent. At least one project is
    required, and at least one of name_starts_with or older_than_days must be
    set, because a call with projects alone deletes every run in those
    projects. To clear a project on purpose, pass older_than_days=0.

    Without purge, deleted runs go to Tuskr's recycle bin and can be restored
    from the UI. purge=True deletes them permanently and cannot be undone.

    The response is Tuskr's own, the number of runs deleted: {"count": N}.

    Args:
        projects: a project ID or name, or a list of them.
        name_starts_with: delete only runs whose name starts with this text.
            The match is case-sensitive.
        older_than_days: delete only runs created more than this many days
            ago. Age counts from the run's creation, not its last update.
            0 matches runs of any age.
        purge: delete permanently instead of moving to the recycle bin.
            Defaults to False.
    """
    if isinstance(projects, str):
        projects = [projects]

    projects = [project.strip() for project in projects if project.strip()]
    if not projects:
        raise ValueError("projects must contain at least one project ID or name")

    name_starts_with = name_starts_with.strip()

    if older_than_days is not None:
        if isinstance(older_than_days, bool) or not isinstance(older_than_days, int):
            raise TypeError("older_than_days must be an integer")
        if older_than_days < 0:
            raise ValueError("older_than_days must be 0 or greater")

    if not name_starts_with and older_than_days is None:
        raise ValueError(
            "Refusing to delete every run in the given projects: set "
            "name_starts_with or older_than_days (older_than_days=0 matches "
            "runs of any age)."
        )

    body = {"projects": projects}
    if name_starts_with:
        body["nameStartsWith"] = name_starts_with
    if older_than_days is not None:
        body["olderThanDays"] = older_than_days
    if purge:
        body["purge"] = True

    tenant_id, access_token = await credentials.resolve(ctx)

    return tuskr_client.send(
        "test-run/bulk",
        body,
        tuskr_client.RequestMethod.DELETE,
        ext_tenant_id=tenant_id,
        ext_access_token=access_token,
    )
