import tuskr_client
from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import set_test_run_lock as module


def _set_lock(ctx, **kwargs):
    return call_tool(module.set_test_run_lock, ctx, **kwargs)


class TestSetTestRunLock:
    """Cover the test-run lock/unlock wrapper."""

    def test_locking_posts_to_the_set_lock_action(self, env, send):
        _set_lock(FakeContext(), test_run="R-7", lock=True)

        action, body, method = send.call_args[0]
        assert action == "test-run/set-lock"
        assert method == tuskr_client.RequestMethod.POST
        assert body["testRun"] == "R-7"

    def test_lock_true_is_sent_as_a_boolean(self, env, send):
        """The API expects a JSON boolean, not a stringified one."""
        _set_lock(FakeContext(), test_run="R-7", lock=True)

        assert send.call_args[0][1]["lock"] is True

    def test_unlocking_sends_lock_false(self, env, send):
        """False is a meaningful value here and must survive the call.

        The sibling write tools omit optional keys whose value is falsy. That
        pattern must not be copied onto `lock`: dropping it would silently turn
        every unlock request into a no-op.
        """
        _set_lock(FakeContext(), test_run="R-7", lock=False)

        body = send.call_args[0][1]
        assert "lock" in body
        assert body["lock"] is False

    def test_only_the_two_documented_keys_are_sent(self, env, send):
        _set_lock(FakeContext(), test_run="R-7", lock=True)

        assert set(send.call_args[0][1]) == {"testRun", "lock"}

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _set_lock(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            test_run="R-7",
            lock=True,
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _set_lock(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            test_run="R-7",
            lock=True,
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(self, monkeypatch, send):
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _set_lock(FakeContext(), test_run="R-7", lock=True)

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"
