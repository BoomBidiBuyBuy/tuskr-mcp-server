import os
import pytest
import requests

import src.tuskr_client as tuskr_client

from urllib.parse import urljoin


class TestSend:
    @pytest.fixture(params=[("http://test-url", "abcdef"), (None, "xxx")])
    def mock_envs(self, monkeypatch, request):
        base_url, access_token = request.param

        if base_url:
            monkeypatch.setenv("TUSKR_BASE_URL", base_url)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "12345")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", access_token)

        expected_base_url = os.environ.get(
            "TUSKR_BASE_URL", tuskr_client.TUSKR_BASE_URL
        )
        expected_base_url = urljoin(expected_base_url, os.environ["TUSKR_ACCOUNT_ID"])

        yield expected_base_url, os.environ.get("TUSKR_ACCESS_TOKEN")

    def test_post(self, mocker, mock_envs):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "executed"
        mock_response.headers = ""

        expected_base_url, access_token = mock_envs

        mocker.patch("requests.post", return_value=mock_response)

        result = tuskr_client.send(
            "create_report", "some body", tuskr_client.RequestMethod.POST
        )

        assert result == "executed"
        requests.post.assert_called_once_with(
            f"{expected_base_url}/create_report",
            headers={"Authorization": f"Bearer {access_token}"},
            data="some body",
        )

    def test_get(self, mocker, mock_envs):
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.text = "executed"
        mock_response.headers = ""

        expected_base_url, access_token = mock_envs

        mocker.patch("requests.get", return_value=mock_response)

        result = tuskr_client.send(
            "create_report", "some body", tuskr_client.RequestMethod.GET
        )

        assert result == "executed"
        requests.get.assert_called_once_with(
            f"{expected_base_url}/create_report",
            headers={"Authorization": f"Bearer {access_token}"},
            params="some body",
        )
