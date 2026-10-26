import pytest

import tuskr_client
from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import create_project as module

TEAM = {"tester@example.com": "Tester"}


def _create(ctx, **kwargs):
    return call_tool(module.create_project, ctx, **kwargs)


class TestCreateProject:
    """Cover the project creation wrapper."""

    def test_required_fields_are_sent(self, env, send):
        _create(FakeContext(), name="Sandbox", team=TEAM)

        action, body, method = send.call_args[0]
        assert action == "project"
        assert method == tuskr_client.RequestMethod.POST
        assert body == {"name": "Sandbox", "team": TEAM}

    def test_unset_optional_fields_are_omitted(self, env, send):
        _create(FakeContext(), name="Sandbox", team=TEAM)

        assert set(send.call_args[0][1]) == {"name", "team"}

    def test_blank_optional_fields_are_not_forwarded(self, env, send):
        """Explicitly blank arguments are treated the same as unset ones."""
        _create(
            FakeContext(),
            name="Sandbox",
            team=TEAM,
            description="",
            status="",
            external_id="",
            issue_url_template="",
            reference_url_template="",
            integration_data={},
        )

        assert set(send.call_args[0][1]) == {"name", "team"}

    def test_optional_fields_are_forwarded_when_set(self, env, send):
        """Every optional parameter maps onto its documented Tuskr key."""
        _create(
            FakeContext(),
            name="Sandbox",
            team=TEAM,
            description="Throwaway project",
            status="archived",
            external_id="ext-1",
            issue_url_template="https://tracker.example.com/issues/{issue}",
            reference_url_template="https://tracker.example.com/refs/{ref}",
            integration_data={"key": "value"},
        )

        assert send.call_args[0][1] == {
            "name": "Sandbox",
            "team": TEAM,
            "description": "Throwaway project",
            "status": "archived",
            "externalId": "ext-1",
            "issueUrlTemplate": "https://tracker.example.com/issues/{issue}",
            "referenceUrlTemplate": "https://tracker.example.com/refs/{ref}",
            "integrationData": {"key": "value"},
        }

    def test_role_names_are_passed_through_unchecked(self, env, send):
        """Role names are tenant specific, so no enum is enforced."""
        team = {"a@example.com": "Custom Role", "b@example.com": "Another"}

        _create(FakeContext(), name="Sandbox", team=team)

        assert send.call_args[0][1]["team"] == team

    @pytest.mark.parametrize("team", [{}, None])
    def test_empty_team_is_rejected_before_any_request(self, env, send, team):
        with pytest.raises(ValueError, match="team"):
            _create(FakeContext(), name="Sandbox", team=team)

        send.assert_not_called()

    @pytest.mark.parametrize(
        "team",
        [
            {"": "Tester"},
            {"tester@example.com": ""},
            {"tester@example.com": None},
        ],
    )
    def test_blank_team_entries_are_rejected_before_any_request(
        self, env, send, team
    ):
        with pytest.raises(ValueError, match="team"):
            _create(FakeContext(), name="Sandbox", team=team)

        send.assert_not_called()

    def test_unknown_status_is_rejected_before_any_request(self, env, send):
        with pytest.raises(ValueError, match="status"):
            _create(FakeContext(), name="Sandbox", team=TEAM, status="deleted")

        send.assert_not_called()

    def test_active_status_is_forwarded(self, env, send):
        _create(FakeContext(), name="Sandbox", team=TEAM, status="active")

        assert send.call_args[0][1]["status"] == "active"

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _create(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            name="Sandbox",
            team=TEAM,
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _create(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            name="Sandbox",
            team=TEAM,
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(self, monkeypatch, send):
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _create(FakeContext(), name="Sandbox", team=TEAM)

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"
