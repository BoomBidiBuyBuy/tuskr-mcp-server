import os

from enum import StrEnum

import requests

import urllib.parse


class RequestMethods(StrEnum):
    GET = 'get'
    POST = 'post'


TUSKR_BASE_URL = "https://api.tuskr.live/api/tenant/"


def send(action : str, body, method: RequestMethods):
    url = urllib.parse.urljoin(
                os.environ.get("TASKR_BASE_URL", TUSKR_BASE_URL),
                os.environ.get("TAKSR_ACCOUNT_ID"),
                action
                )

    return requests.getattr(method)(url, data=body)
