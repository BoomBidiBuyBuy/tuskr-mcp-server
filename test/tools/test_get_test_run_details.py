import json

import tuskr_client
from test.helpers import FakeContext, call_tool
from tuskr_mcp.tools import get_test_run_details as module

RUN_ID = "0b6f3c2e-5d1a-4c8e-9f7b-2a4d6e8f0a1c"


def _get_details(ctx, **kwargs):
    return call_tool(module.get_test_run_details, ctx, **kwargs)


class TestGetTestRunDetails:
    """Cover the test-run details wrapper."""

    def test_gets_the_details_action_for_the_run(self, env, send):
        _get_details(FakeContext(), test_run=RUN_ID)

        action, _body, method = send.call_args[0]
        assert action == f"test-run/{RUN_ID}/details"
        assert method == tuskr_client.RequestMethod.GET

    def test_sends_no_query_parameters(self, env, send):
        """The run is addressed in the path; the endpoint takes no filters."""
        _get_details(FakeContext(), test_run=RUN_ID)

        assert send.call_args[0][1] == {}

    def test_returns_the_response_untouched(self, env, send):
        payload = json.dumps(
            {
                "id": RUN_ID,
                "key": "R-7",
                "name": "Nightly regression",
                "firstResultAt": "2026-09-30T06:00:00.000Z",
                "lastResultAt": "2026-09-30T07:30:00.000Z",
                "durationInMinutes": 90,
            }
        )
        send.return_value = payload

        assert _get_details(FakeContext(), test_run=RUN_ID) == payload

    def test_null_timestamps_are_passed_through(self, env, send):
        """A run with no recorded timestamps comes back with nulls.

        The tool must not drop or rewrite them: the docstring tells callers a
        null means "unknown", so the null has to reach them intact.
        """
        payload = json.dumps(
            {
                "id": RUN_ID,
                "firstResultAt": None,
                "lastResultAt": None,
                "durationInMinutes": None,
            }
        )
        send.return_value = payload

        result = json.loads(_get_details(FakeContext(), test_run=RUN_ID))
        assert result["firstResultAt"] is None
        assert result["lastResultAt"] is None
        assert result["durationInMinutes"] is None

    def test_plain_text_error_is_returned_unchanged(self, env, send):
        """Tuskr answers an unknown run ID with plain text, not JSON.

        `tuskr_client.send` returns the body whatever the status, so a run key
        (the endpoint takes IDs only) comes back as a bare message that the
        tool must hand over untouched.
        """
        message = "Invalid test run ID: R-2"
        send.return_value = message

        assert _get_details(FakeContext(), test_run="R-2") == message

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _get_details(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            test_run=RUN_ID,
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _get_details(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            test_run=RUN_ID,
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(self, monkeypatch, send):
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _get_details(FakeContext(), test_run=RUN_ID)

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"
