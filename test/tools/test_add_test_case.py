import tuskr_client
from test.helpers import FakeContext, call_tool
from tuskr_mcp.tools import add_test_case as module


def _add_case(ctx, **kwargs):
    return call_tool(module.add_test_case, ctx, **kwargs)


class TestAddTestCase:
    """Cover the test-case creation wrapper."""

    def test_required_fields_are_sent(self, env, send):
        _add_case(FakeContext(), name="Login works", project="Sandbox")

        action, body, method = send.call_args[0]
        assert action == "test-case"
        assert method == tuskr_client.RequestMethod.POST
        assert body == {"name": "Login works", "project": "Sandbox"}

    def test_unset_optional_fields_are_omitted(self, env, send):
        """Tuskr resolves suite, section and type against existing records.

        A blank value is therefore a failed lookup, not an absent field, so
        only the keys the caller set may reach the request body.
        """
        _add_case(FakeContext(), name="Login works", project="Sandbox")

        assert set(send.call_args[0][1]) == {"name", "project"}

    def test_blank_optional_fields_are_not_forwarded(self, env, send):
        """Explicitly blank arguments are treated the same as unset ones."""
        _add_case(
            FakeContext(),
            name="Login works",
            project="Sandbox",
            test_suite="",
            test_suite_section="",
            description="",
            test_case_type="",
            estimated_time_in_minutes=None,
            custom_fields={},
        )

        assert set(send.call_args[0][1]) == {"name", "project"}

    def test_optional_fields_are_forwarded_when_set(self, env, send):
        """Every optional parameter maps onto its documented Tuskr key."""
        _add_case(
            FakeContext(),
            name="Login works",
            project="Sandbox",
            test_suite="Smoke",
            test_suite_section="Auth",
            description="User can sign in",
            test_case_type="Functional",
            estimated_time_in_minutes=5,
            custom_fields={"is_automated": True},
        )

        assert send.call_args[0][1] == {
            "name": "Login works",
            "project": "Sandbox",
            "testSuite": "Smoke",
            "testSuiteSection": "Auth",
            "description": "User can sign in",
            "testCaseType": "Functional",
            "estimatedTimeInMinutes": 5,
            "customFields": {"is_automated": True},
        }

    def test_zero_minute_estimate_is_forwarded(self, env, send):
        """0 is a real value, so only None counts as unset."""
        _add_case(
            FakeContext(),
            name="Login works",
            project="Sandbox",
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

        _add_case(
            FakeContext(),
            name="Login works",
            project="Sandbox",
            custom_fields=fields,
        )

        assert send.call_args[0][1]["customFields"] == fields

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _add_case(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            name="Login works",
            project="Sandbox",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _add_case(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            name="Login works",
            project="Sandbox",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(self, monkeypatch, send):
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _add_case(FakeContext(), name="Login works", project="Sandbox")

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"
