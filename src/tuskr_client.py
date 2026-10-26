import json
import os
import warnings
from enum import StrEnum
from urllib.parse import urljoin

import requests


class RequestMethod(StrEnum):
    GET = "get"
    POST = "post"
    PUT = "put"
    DELETE = "delete"


TUSKR_BASE_URL = "https://api.tuskr.live/api/tenant/"

# (connect, read) seconds. The read timeout bounds the wait between bytes, not
# the whole transfer, so a large export still completes while a stalled
# connection fails instead of hanging the tool call forever.
REQUEST_TIMEOUT = (10, 120)

_TENANT_DEPRECATION_MESSAGE = (
    "TUSKR_ACCOUNT_ID is deprecated and will be removed in a future "
    "release; use TUSKR_TENANT_ID instead."
)


def _resolve_tenant_id(ext_tenant_id: str | None = None) -> str | None:
    """Return the tenant ID, preferring the new TUSKR_TENANT_ID env var.

    Resolution order:
    1. Explicit ext_tenant_id argument (typically from HTTP header).
    2. TUSKR_TENANT_ID environment variable.
    3. TUSKR_ACCOUNT_ID environment variable (deprecated; warns).
    """
    if ext_tenant_id is not None:
        return ext_tenant_id

    new = os.environ.get("TUSKR_TENANT_ID")
    if new:
        return new

    old = os.environ.get("TUSKR_ACCOUNT_ID")
    if old:
        warnings.warn(
            _TENANT_DEPRECATION_MESSAGE,
            DeprecationWarning,
            stacklevel=2,
        )
        return old

    return None


def send(
    action: str,
    body: dict,
    method: RequestMethod,
    ext_tenant_id: str | None = None,
    ext_access_token: str | None = None,
    *,
    ext_account_id: str | None = None,  # deprecated alias; remove in next major version
    files: list[tuple[str, bytes, str]] | None = None,
    top_level: dict | None = None,
):
    """Sends a request to the Tuskr endpoint.

    `body` is the request payload: the JSON object sent under `data` for POST,
    PUT and DELETE, or the query parameters for GET.

    The access token is taken from `ext_access_token` (typically the caller's
    Bearer header) and falls back to the TUSKR_ACCESS_TOKEN environment
    variable, the same precedence as the tenant ID.

    `files` is a list of (filename, content, mimetype) tuples and is only valid
    for POST. When present the request goes out as multipart/form-data instead
    of JSON.

    `top_level` adds keys next to `data` in the JSON envelope, for endpoints
    that expect a sibling of `data` such as a record `id`. It is only valid for
    the JSON methods (POST, PUT and DELETE) and cannot carry its own `data` key.
    """

    if files and method != RequestMethod.POST:
        raise ValueError("Attachments can only be sent with a POST request.")

    if top_level:
        if method == RequestMethod.GET:
            raise ValueError(
                "top_level can only be sent with a POST, PUT or DELETE request."
            )
        if files:
            raise ValueError("top_level cannot be combined with attachments.")
        if "data" in top_level:
            raise ValueError("top_level cannot contain a 'data' key.")

    if ext_account_id is not None and ext_tenant_id is None:
        warnings.warn(
            "The 'ext_account_id' parameter is deprecated; "
            "use 'ext_tenant_id' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        ext_tenant_id = ext_account_id

    tenant_id = _resolve_tenant_id(ext_tenant_id)
    if tenant_id is None:
        raise ValueError(
            "Tuskr tenant ID is not set. Provide TUSKR_TENANT_ID via "
            "environment, the Tenant-ID HTTP header, or the "
            "ext_tenant_id argument."
        )

    url = urljoin(
        os.environ.get("TUSKR_BASE_URL", TUSKR_BASE_URL),
        tenant_id + f"/{action}",
    )

    access_token = ext_access_token or os.environ.get("TUSKR_ACCESS_TOKEN")
    if not access_token:
        raise ValueError(
            "Tuskr access token is not set. Provide TUSKR_ACCESS_TOKEN via "
            "environment, the Authorization: Bearer HTTP header, or the "
            "ext_access_token argument."
        )

    headers = {"Authorization": f"Bearer {access_token}"}

    if files:
        # Attachments use a multipart POST: the same {"data": ...} JSON goes in
        # a `body` form field and each file in an `attachment` field. Leave
        # Content-Type unset so requests generates the multipart boundary.
        response = requests.post(
            url,
            headers=headers,
            data={"body": json.dumps({"data": body})},
            files=[("attachment", file) for file in files],
            timeout=REQUEST_TIMEOUT,
        )
    elif method in (RequestMethod.POST, RequestMethod.PUT, RequestMethod.DELETE):
        # Tuskr's REST API expects POST, PUT and DELETE bodies as JSON wrapped
        # in a top-level "data" key (see https://tuskr.app/kb/latest/api).
        # Setting the Content-Type header and using requests' json= keyword
        # handles both. `top_level` keys sit beside "data", which is where
        # Tuskr wants the record id on a PUT. The requests function is looked
        # up at call time (its name matches the method value) so tests that
        # patch requests.post, requests.put or requests.delete still apply.
        send_json = getattr(requests, method.value)
        response = send_json(
            url,
            headers={**headers, "Content-Type": "application/json"},
            json={**(top_level or {}), "data": body},
            timeout=REQUEST_TIMEOUT,
        )
    else:
        response = requests.get(
            url, headers=headers, params=body, timeout=REQUEST_TIMEOUT
        )

    return response.text
