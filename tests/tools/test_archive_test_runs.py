import pytest

import tuskr_client
from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import archive_test_runs as module

RUN_ID = "74633d5b-d97d-49ad-94a8-cf5348020cb3"
OTHER_RUN_ID = "84633d5b-d97d-49ad-94a8-cf5348020cb4"


def _archive(ctx, **kwargs):
    return call_tool(module.archive_test_runs, ctx, **kwargs)


class TestArchiveTestRuns:
    """Cover the test-run archiving wrapper."""

    def test_posts_to_the_archive_action(self, env, send):
        _archive(FakeContext(), test_runs=RUN_ID)

        action, _, method = send.call_args[0]
        assert action == "test-run/archive"
        assert method == tuskr_client.RequestMethod.POST

    def test_single_run_is_wrapped_in_a_list(self, env, send):
        """The endpoint always takes an array, even for one run."""
        _archive(FakeContext(), test_runs=RUN_ID)

        assert send.call_args[0][1]["ids"] == [RUN_ID]

    def test_multiple_runs_are_forwarded_as_given(self, env, send):
        _archive(FakeContext(), test_runs=[RUN_ID, OTHER_RUN_ID])

        assert send.call_args[0][1]["ids"] == [RUN_ID, OTHER_RUN_ID]

    def test_empty_list_raises_rather_than_calling_tuskr(self, env, send):
        """An empty archive request is a caller bug, not a no-op worth sending."""
        with pytest.raises(ValueError):
            _archive(FakeContext(), test_runs=[])

        send.assert_not_called()

    def test_only_the_ids_key_is_sent(self, env, send):
        _archive(FakeContext(), test_runs=RUN_ID)

        assert set(send.call_args[0][1]) == {"ids"}

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _archive(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            test_runs=RUN_ID,
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _archive(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            test_runs=RUN_ID,
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(self, monkeypatch, send):
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _archive(FakeContext(), test_runs=RUN_ID)

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"
