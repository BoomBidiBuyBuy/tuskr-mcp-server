import tuskr_client
from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import create_test_run as module


def _create_run(ctx, **kwargs):
    return call_tool(module.create_test_run, ctx, **kwargs)


def _required(**overrides):
    """The three arguments every create_test_run call must supply."""
    args = {
        "name": "Regression 2026-08-17",
        "project": "P5",
        "test_case_inclusion_type": "ALL",
    }
    args.update(overrides)
    return args


class TestCreateTestRun:
    """Cover the test-run creation wrapper."""

    def test_required_fields_are_sent(self, env, send):
        _create_run(FakeContext(), **_required())

        action, body, method = send.call_args[0]
        assert action == "test-run"
        assert method == tuskr_client.RequestMethod.POST
        assert body["name"] == "Regression 2026-08-17"
        assert body["project"] == "P5"
        assert body["testCaseInclusionType"] == "ALL"

    def test_unset_optional_fields_are_omitted(self, env, send):
        """Blank optional values must never be sent.

        Tuskr validates `deadline` even when it is an empty string and rejects
        the whole request with "Deadline must be today or a future date", so
        forwarding a blank made the tool unusable without an explicit deadline.
        """
        _create_run(FakeContext(), **_required())

        assert set(send.call_args[0][1]) == {
            "name",
            "project",
            "testCaseInclusionType",
        }

    def test_blank_deadline_is_not_forwarded(self, env, send):
        """The specific field whose blank value Tuskr rejects."""
        _create_run(FakeContext(), **_required(deadline=""))

        assert "deadline" not in send.call_args[0][1]

    def test_optional_fields_are_forwarded_when_set(self, env, send):
        """Every optional parameter maps onto its documented Tuskr key."""
        _create_run(
            FakeContext(),
            **_required(
                test_case_inclusion_type="SPECIFIC",
                test_cases=["C-1", "C-2"],
                description="nightly smoke",
                deadline="2026-08-24",
                assigned_to="qa.lead@example.com",
            ),
        )

        body = send.call_args[0][1]
        assert body["testCases"] == ["C-1", "C-2"]
        assert body["description"] == "nightly smoke"
        assert body["deadline"] == "2026-08-24"
        assert body["assignedTo"] == "qa.lead@example.com"

    def test_empty_test_case_list_is_omitted(self, env, send):
        """An empty list carries no more information than an absent one."""
        _create_run(FakeContext(), **_required(test_cases=[]))

        assert "testCases" not in send.call_args[0][1]

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _create_run(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            **_required(),
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _create_run(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            **_required(),
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(self, monkeypatch, send):
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _create_run(FakeContext(), **_required())

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"
