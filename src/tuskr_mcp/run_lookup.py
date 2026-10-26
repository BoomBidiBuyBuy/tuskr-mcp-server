"""Lookup of a test run by key or name inside one project.

Tuskr resolves a run given by key or name across the whole tenant, so a key such
as R-1 that exists in several projects is ambiguous. Tools that address a run
can call `resolve_test_run` first to turn the key or name into the run's UUID
within one project.
"""

import json
import uuid

import tuskr_client


def _is_uuid(value):
    try:
        uuid.UUID(value)
    except (AttributeError, ValueError):
        return False
    return True


def _list_rows(filter_field, value, project, tenant_id, access_token):
    """Return every row of `GET test-run` for one project and one filter.

    `filter[key]` and `filter[name]` are contains-matches, so a single value can
    match many runs over several pages. Every page is walked, because the exact
    match may sit on any of them.
    """
    rows = []
    page = 1
    while True:
        raw = tuskr_client.send(
            "test-run",
            {
                "page": page,
                "filter[project]": project,
                f"filter[{filter_field}]": value,
            },
            tuskr_client.RequestMethod.GET,
            ext_tenant_id=tenant_id,
            ext_access_token=access_token,
        )
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            data = None
        if not isinstance(data, dict) or not isinstance(data.get("rows"), list):
            # An error body must not read as "no such run". ValueError, not
            # TypeError: the response is bad, not an argument's type.
            raise ValueError(  # noqa: TRY004
                f"Could not look up test run {value!r} in project {project!r}: "
                f"unexpected response from Tuskr: {str(raw)[:200]}"
            )
        rows.extend(row for row in data["rows"] if isinstance(row, dict))

        meta = data.get("meta")
        pages = meta.get("pages", 1) if isinstance(meta, dict) else 1
        if not isinstance(pages, int) or page >= pages:
            return rows
        page += 1


def _ids(rows):
    """Distinct run IDs of the rows, in order."""
    return list(dict.fromkeys(row["id"] for row in rows if row.get("id")))


def resolve_test_run(test_run, project, tenant_id, access_token):
    """Return the UUID of the run named by `test_run` inside `project`.

    A UUID is returned unchanged without a request. Anything else is matched by
    exact key (case-insensitive) first, then by exact name. Raises ValueError
    when no run matches, or when several do, naming their IDs.
    """
    if _is_uuid(test_run):
        return test_run

    wanted = test_run.casefold()
    ids = _ids(
        row
        for row in _list_rows("key", test_run, project, tenant_id, access_token)
        if str(row.get("key", "")).casefold() == wanted
    )
    if not ids:
        ids = _ids(
            row
            for row in _list_rows("name", test_run, project, tenant_id, access_token)
            if row.get("name") == test_run
        )

    if not ids:
        raise ValueError(
            f"No test run with key or name {test_run!r} in project {project!r}. "
            "Check the project ID: Tuskr answers an unknown project with an "
            "empty list, not an error."
        )
    if len(ids) > 1:
        raise ValueError(
            f"Several test runs match {test_run!r} in project {project!r}: "
            f"{', '.join(ids)}. Pass one of these IDs as test_run."
        )
    return ids[0]
