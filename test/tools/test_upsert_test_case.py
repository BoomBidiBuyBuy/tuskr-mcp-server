import pytest

import tuskr_client
from test.helpers import FakeContext, call_tool
from tuskr_mcp.tools import upsert_test_case as module


def _upsert(ctx, **kwargs):
    return call_tool(module.upsert_test_case, ctx, **kwargs)


class TestUpsertTestCase:
    """Cover the create-or-update test-case wrapper."""

    def test_external_id_body_is_sent(self, env, send):
        _upsert(FakeContext(), project="Sandbox", external_id="ext-1")

        action, body, method = send.call_args[0]
        assert action == "test-case/upsert"
        assert method == tuskr_client.RequestMethod.POST
        assert body == {"project": "Sandbox", "externalId": "ext-1"}

    def test_test_case_id_body_is_sent(self, env, send):
        _upsert(FakeContext(), project="Sandbox", test_case_id="uuid-1")

        assert send.call_args[0][1] == {"project": "Sandbox", "id": "uuid-1"}

    def test_neither_identifier_is_rejected_before_sending(self, env, send):
        with pytest.raises(ValueError, match="either"):
            _upsert(FakeContext(), project="Sandbox", name="Login works")

        send.assert_not_called()

    def test_both_identifiers_are_rejected_before_sending(self, env, send):
        with pytest.raises(ValueError, match="only one"):
            _upsert(
                FakeContext(),
                project="Sandbox",
                test_case_id="uuid-1",
                external_id="ext-1",
            )

        send.assert_not_called()

    def test_unset_optional_fields_are_omitted(self, env, send):
        """A blank sent on an update could overwrite real data.

        Only the keys the caller set may reach the request body.
        """
        _upsert(FakeContext(), project="Sandbox", external_id="ext-1")

        assert set(send.call_args[0][1]) == {"project", "externalId"}

    def test_blank_optional_fields_are_not_forwarded(self, env, send):
        """Explicitly blank arguments are treated the same as unset ones."""
        _upsert(
            FakeContext(),
            project="Sandbox",
            external_id="ext-1",
            name="",
            test_suite="",
            test_suite_section="",
            description="",
            test_case_type="",
            estimated_time_in_minutes=None,
            custom_fields={},
            create_missing_suite=False,
            create_missing_section=False,
        )

        assert set(send.call_args[0][1]) == {"project", "externalId"}

    def test_optional_fields_are_forwarded_when_set(self, env, send):
        """Every optional parameter maps onto its documented Tuskr key."""
        _upsert(
            FakeContext(),
            project="Sandbox",
            external_id="ext-1",
            name="Login works",
            test_suite="Smoke",
            test_suite_section="Auth",
            description="User can sign in",
            test_case_type="Functional",
            estimated_time_in_minutes=5,
            custom_fields={"is_automated": True},
        )

        assert send.call_args[0][1] == {
            "project": "Sandbox",
            "externalId": "ext-1",
            "name": "Login works",
            "testSuite": "Smoke",
            "testSuiteSection": "Auth",
            "description": "User can sign in",
            "testCaseType": "Functional",
            "estimatedTimeInMinutes": 5,
            "customFields": {"is_automated": True},
        }

    def test_zero_minute_estimate_is_forwarded(self, env, send):
        """0 is a real value, so only None counts as unset."""
        _upsert(
            FakeContext(),
            project="Sandbox",
            external_id="ext-1",
            estimated_time_in_minutes=0,
        )

        assert send.call_args[0][1]["estimatedTimeInMinutes"] == 0

    def test_custom_fields_are_passed_through_unchanged(self, env, send):
        """Custom-field keys and value shapes are tenant specific."""
        fields = {
            "stepsWithExpectedResults": [{"step": "Open page", "expected": "Loads"}],
            "multi_select": ["a", "b"],
            "date": "2026-10-07",
        }

        _upsert(
            FakeContext(),
            project="Sandbox",
            external_id="ext-1",
            custom_fields=fields,
        )

        assert send.call_args[0][1]["customFields"] == fields

    def test_options_are_omitted_by_default(self, env, send):
        _upsert(FakeContext(), project="Sandbox", external_id="ext-1")

        assert "options" not in send.call_args[0][1]

    def test_only_enabled_options_are_sent(self, env, send):
        _upsert(
            FakeContext(),
            project="Sandbox",
            external_id="ext-1",
            create_missing_suite=True,
        )

        assert send.call_args[0][1]["options"] == {"createMissingSuite": True}

    def test_both_options_are_sent_when_enabled(self, env, send):
        _upsert(
            FakeContext(),
            project="Sandbox",
            external_id="ext-1",
            create_missing_suite=True,
            create_missing_section=True,
        )

        assert send.call_args[0][1]["options"] == {
            "createMissingSuite": True,
            "createMissingSection": True,
        }

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _upsert(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            project="Sandbox",
            external_id="ext-1",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _upsert(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            project="Sandbox",
            external_id="ext-1",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(self, monkeypatch, send):
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _upsert(FakeContext(), project="Sandbox", external_id="ext-1")

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"
