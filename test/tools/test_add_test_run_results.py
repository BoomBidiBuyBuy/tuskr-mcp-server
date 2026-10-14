import pytest

import tuskr_client
from test.helpers import FakeContext, call_tool
from tuskr_mcp.tools import add_test_run_results as module


def _add_result(ctx, **kwargs):
    return call_tool(module.add_test_run_results, ctx, **kwargs)


class TestAddTestRunResults:
    """Cover the bulk result endpoint wrapper."""

    def test_single_test_case_is_wrapped_in_a_list(self, env, send):
        """A bare string becomes a one-element testCases array."""
        _add_result(
            FakeContext(),
            test_run="Release Build 22-10-2021",
            status="PASSED",
            test_cases="C-2",
        )

        action, body, method = send.call_args[0]
        assert action == "test-run-result/bulk"
        assert method == tuskr_client.RequestMethod.POST
        assert body["testCases"] == ["C-2"]
        assert body["testRun"] == "Release Build 22-10-2021"
        assert body["status"] == "PASSED"

    def test_many_test_cases_are_sent_in_one_call(self, env, send):
        """A list of test cases produces exactly one request, not one per case."""
        _add_result(
            FakeContext(),
            test_run="Alpha 3",
            status="FAILED",
            test_cases=["C-1", "Pagination", "4ded1648-6fc9-499b-a057-0482263d2f26"],
        )

        send.assert_called_once()
        body = send.call_args[0][1]
        assert body["testCases"] == [
            "C-1",
            "Pagination",
            "4ded1648-6fc9-499b-a057-0482263d2f26",
        ]

    def test_unset_optional_fields_are_omitted(self, env, send):
        """Blank optional values are never sent; Tuskr rejects them."""
        _add_result(
            FakeContext(),
            test_run="Alpha 3",
            status="PASSED",
            test_cases="C-1",
        )

        body = send.call_args[0][1]
        assert set(body) == {"testRun", "status", "testCases"}

    def test_optional_fields_are_forwarded_when_set(self, env, send):
        """Every optional parameter maps onto its documented Tuskr key."""
        _add_result(
            FakeContext(),
            test_run="Alpha 3",
            status="FAILED",
            test_cases="C-1",
            assigned_to="peter@mycompany.co",
            comments="failed on checkout",
            time_spent_in_minutes=10,
            custom_fields={"integer": 108, "checkbox": True},
        )

        body = send.call_args[0][1]
        assert body["assignedTo"] == "peter@mycompany.co"
        assert body["comments"] == "failed on checkout"
        assert body["timeSpentInMinutes"] == 10
        assert body["customFields"] == {"integer": 108, "checkbox": True}

    def test_zero_time_spent_is_still_forwarded(self, env, send):
        """0 minutes is a real value, not an absent one."""
        _add_result(
            FakeContext(),
            test_run="Alpha 3",
            status="PASSED",
            test_cases="C-1",
            time_spent_in_minutes=0,
        )

        assert send.call_args[0][1]["timeSpentInMinutes"] == 0

    def test_empty_test_case_list_raises(self, env, send):
        """An empty list is a caller bug, not a request worth sending."""
        with pytest.raises(ValueError, match="at least one test case"):
            _add_result(
                FakeContext(),
                test_run="Alpha 3",
                status="PASSED",
                test_cases=[],
            )

        send.assert_not_called()


class TestAddTestRunResultsCredentials:
    """Header state must win over env vars; env vars must still work in stdio."""

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        """Middleware sets state to None in stdio mode, so env vars are used."""
        _add_result(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            test_run="Alpha 3",
            status="PASSED",
            test_cases="C-1",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        """Values from HTTP headers take precedence over the environment."""
        _add_result(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            test_run="Alpha 3",
            status="PASSED",
            test_cases="C-1",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(
        self, monkeypatch, mocker, send
    ):
        """TUSKR_ACCOUNT_ID remains a working fallback after the tenant rename."""
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _add_result(
            FakeContext(),
            test_run="Alpha 3",
            status="PASSED",
            test_cases="C-1",
        )

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"


class TestAddTestRunResultsAttachments:
    """Attachments ride along as `files`; everything else stays unchanged."""

    @pytest.fixture
    def attach_dir(self, tmp_path, monkeypatch):
        root = tmp_path / "attachments"
        root.mkdir()
        monkeypatch.setenv("TUSKR_ATTACHMENT_DIR", str(root))
        return root

    def test_files_are_forwarded_to_send(self, env, send, attach_dir):
        (attach_dir / "log.txt").write_bytes(b"boom")

        _add_result(
            FakeContext(),
            test_run="Alpha 3",
            status="FAILED",
            test_cases=["C-1", "C-2"],
            attachments=["log.txt"],
        )

        assert send.call_args[1]["files"] == [("log.txt", b"boom", "text/plain")]
        # The JSON body is unaffected: attachments never enter it.
        assert set(send.call_args[0][1]) == {"testRun", "status", "testCases"}

    def test_no_files_keyword_without_attachments(self, env, send):
        """The plain call must not grow a `files` kwarg, even for an empty list."""
        _add_result(
            FakeContext(),
            test_run="Alpha 3",
            status="PASSED",
            test_cases="C-1",
            attachments=[],
        )

        assert "files" not in send.call_args[1]

    def test_invalid_attachment_sends_nothing(self, env, send, attach_dir):
        """A bad file fails the whole call before any request is made."""
        with pytest.raises(ValueError, match="not an existing file"):
            _add_result(
                FakeContext(),
                test_run="Alpha 3",
                status="PASSED",
                test_cases="C-1",
                attachments=["missing.png"],
            )

        send.assert_not_called()

    def test_attachments_disabled_without_attachment_dir(self, env, send, monkeypatch):
        monkeypatch.delenv("TUSKR_ATTACHMENT_DIR", raising=False)

        with pytest.raises(ValueError, match="Attachments are disabled"):
            _add_result(
                FakeContext(),
                test_run="Alpha 3",
                status="PASSED",
                test_cases="C-1",
                attachments=["log.txt"],
            )

        send.assert_not_called()
