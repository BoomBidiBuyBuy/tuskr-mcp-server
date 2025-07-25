import os

from enum import StrEnum

import requests


from urllib.parse import urljoin


class RequestMethod(StrEnum):
    GET = 'get'
    POST = 'post'


TUSKR_BASE_URL = "https://api.tuskr.live/api/tenant/"


def send(action: str, body, method: RequestMethod):

    url = urljoin(
            os.environ.get("TASKR_BASE_URL", TUSKR_BASE_URL),
            os.environ.get("TASKR_ACCOUNT_ID") + f"/{action}",
        )

    access_token = os.environ.get("TASKR_ACCESS_TOKEN")

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    if method == RequestMethod.POST:
        response = requests.post(
                url,
                headers=headers,
                data=body
            )
    else:
        response = requests.get(
                url,
                headers=headers,
                params=body
            )


    print()
    print("Send:")
    print(url)
    print(headers)
    print(body)
    print()

    print()
    print("Response:")
    print(response.status_code)
    print(response.text)
    print(response.headers)
    print()
    return response.text
