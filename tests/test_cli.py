from click.testing import CliRunner

import main


def _invoke(mocker, *args):
    run = mocker.patch.object(main.mcp, "run")
    result = CliRunner().invoke(main.main, list(args))
    assert result.exit_code == 0, result.output
    return run


def test_http_transport_passes_host_and_port(mocker):
    run = _invoke(
        mocker, "--transport", "http", "--host", "127.0.0.1", "--port", "9000"
    )

    run.assert_called_once_with(transport="http", host="127.0.0.1", port=9000)


def test_stdio_transport_passes_no_host_or_port(mocker):
    run = _invoke(mocker, "--transport", "stdio", "--host", "127.0.0.1")

    run.assert_called_once_with(transport="stdio")


def test_non_numeric_port_is_rejected(mocker):
    mocker.patch.object(main.mcp, "run")

    result = CliRunner().invoke(main.main, ["--port", "abc"])

    assert result.exit_code != 0
