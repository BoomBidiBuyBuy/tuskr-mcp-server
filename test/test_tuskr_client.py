import pytest 
import requests

import src.tuskr_client as tuskr_client


def test_send(monkeypatch, mocker):
    monkeypatch.setenv("TASKR_BASE_URL", "http://test")
    monkeypatch.setenv("TASKR_ACCOUNT_ID", "12345")
    monkeypatch.setenv("TASKR_ACCESS_TOKEN", "abcdef")

    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.text = "executed"
    mock_response.headers = ""

    mocker.patch("requests.post", return_value=mock_response)

    result = tuskr_client.send(
        "create_report",
        "some body",
        tuskr_client.RequestMethod.POST
    )

    assert result == "executed"
    requests.post.assert_called_once_with(
        "http://test/12345/create_report",
        headers={"Authorization": f"Bearer abcdef"},
        data="some body"
    )
