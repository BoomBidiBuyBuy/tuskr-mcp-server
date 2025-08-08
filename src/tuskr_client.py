import os

from enum import StrEnum

import requests


from urllib.parse import urljoin


class RequestMethod(StrEnum):
    GET = "get"
    POST = "post"


TUSKR_BASE_URL = "https://api.tuskr.live/api/tenant/"


def send(
    action: str,
    body: str,
    method: RequestMethod,
    ext_account_id: str = None,
    ext_access_token: str = None,
):
    """Sends a request to the Tuskr endpoint"""

    url = urljoin(
        os.environ.get("TUSKR_BASE_URL", TUSKR_BASE_URL),
        os.environ.get("TUSKR_ACCOUNT_ID", ext_account_id) + f"/{action}",
    )

    access_token = os.environ.get("TUSKR_ACCESS_TOKEN", ext_access_token)

    headers = {"Authorization": f"Bearer {access_token}"}

    if method == RequestMethod.POST:
        response = requests.post(url, headers=headers, data=body)
    else:
        response = requests.get(url, headers=headers, params=body)

    return response.text
