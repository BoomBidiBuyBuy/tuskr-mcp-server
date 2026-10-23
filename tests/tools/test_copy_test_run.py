import tuskr_client
from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import copy_test_run as module


def _copy_run(ctx, **kwargs):
    return call_tool(module.copy_test_run, ctx, **kwargs)


class TestCopyTestRun:
    """Cover the test-run copy wrapper."""

    def test_source_run_is_sent(self, env, send):
        _copy_run(FakeContext(), test_run="Basic run")

        action, body, method = send.call_args[0]
        assert action == "test-run/copy"
        assert method == tuskr_client.RequestMethod.POST
        assert body["testRun"] == "Basic run"

    def test_unset_optional_fields_are_omitted(self, env, send):
        """An absent key means "inherit from the source run".

        A blank one does not: Tuskr resolves `assignedTo` against real users
        and validates `deadline` against today's date, so forwarding either
        empty turns an inherit into a rejected request.
        """
        _copy_run(FakeContext(), test_run="Basic run")

        assert set(send.call_args[0][1]) == {"testRun"}

    def test_blank_optional_fields_are_not_forwarded(self, env, send):
        """Explicitly blank arguments are treated the same as unset ones."""
        _copy_run(
            FakeContext(),
            test_run="Basic run",
            name="",
            description="",
            deadline="",
            assigned_to="",
        )

        assert set(send.call_args[0][1]) == {"testRun"}

    def test_optional_fields_are_forwarded_when_set(self, env, send):
        """Every optional parameter maps onto its documented Tuskr key."""
        _copy_run(
            FakeContext(),
            test_run="Basic run",
            name="Copy of Basic run",
            description="nightly smoke, re-run",
            deadline="2026-08-24",
            assigned_to="qa.lead@example.com",
        )

        body = send.call_args[0][1]
        assert body["name"] == "Copy of Basic run"
        assert body["description"] == "nightly smoke, re-run"
        assert body["deadline"] == "2026-08-24"
        assert body["assignedTo"] == "qa.lead@example.com"

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _copy_run(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            test_run="Basic run",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _copy_run(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            test_run="Basic run",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(self, monkeypatch, send):
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _copy_run(FakeContext(), test_run="Basic run")

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"
