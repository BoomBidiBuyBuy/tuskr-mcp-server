import json
import os
import warnings
from enum import StrEnum
from urllib.parse import urljoin

import requests


class RequestMethod(StrEnum):
    GET = "get"
    POST = "post"


TUSKR_BASE_URL = "https://api.tuskr.live/api/tenant/"

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
    body: str,
    method: RequestMethod,
    ext_tenant_id: str | None = None,
    ext_access_token: str | None = None,
    *,
    ext_account_id: str | None = None,  # deprecated alias; remove in next major version
    files: list[tuple[str, bytes, str]] | None = None,
):
    """Sends a request to the Tuskr endpoint.

    `files` is a list of (filename, content, mimetype) tuples and is only valid
    for POST. When present the request goes out as multipart/form-data instead
    of JSON.
    """

    if files and method != RequestMethod.POST:
        raise ValueError("Attachments can only be sent with a POST request.")

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

    access_token = os.environ.get("TUSKR_ACCESS_TOKEN", ext_access_token)

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
        )
    elif method == RequestMethod.POST:
        # Tuskr's REST API expects POST bodies as JSON wrapped in a top-level
        # "data" key (see https://tuskr.app/kb/latest/api). Setting the
        # Content-Type header and using requests' json= keyword handles both.
        response = requests.post(
            url,
            headers={**headers, "Content-Type": "application/json"},
            json={"data": body},
        )
    else:
        response = requests.get(url, headers=headers, params=body)

    return response.text
