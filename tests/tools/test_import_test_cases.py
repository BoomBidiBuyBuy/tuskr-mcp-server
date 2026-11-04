import json

import pytest

import tuskr_client
from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import import_test_cases as module

CASES = [
    {"name": "Login works", "testSuite": "Smoke", "testSuiteSection": "Auth"},
    {"name": "Logout works", "testSuite": "Smoke", "testSuiteSection": "Auth"},
]


def _import(ctx, **kwargs):
    return call_tool(module.import_test_cases, ctx, **kwargs)


class TestImportTestCases:
    """Cover the bulk test-case import wrapper."""

    def test_required_fields_are_sent(self, env, send):
        _import(FakeContext(), project="Sandbox", test_cases=CASES)

        action, body, method = send.call_args[0]
        assert action == "test-case/import"
        assert method == tuskr_client.RequestMethod.POST
        assert body == {"project": "Sandbox", "testCases": CASES}

    def test_test_case_objects_are_passed_through_unchanged(self, env, send):
        """Record keys and custom-field shapes are Tuskr's and tenant specific."""
        cases = [
            {
                "name": "Checkout works",
                "description": "Pays by card",
                "testSuite": "Checkout",
                "testSuiteSection": "Payment",
                "testCaseType": "Functional",
                "estimatedTimeInMinutes": 20,
                "customFields": {
                    "stepsWithExpectedResults": [
                        {"step": 1, "description": "s1", "expectedResult": "e1"}
                    ],
                    "multi": ["option 1", "option 2"],
                },
            }
        ]

        _import(FakeContext(), project="Sandbox", test_cases=cases)

        assert send.call_args[0][1]["testCases"] == cases

    def test_empty_list_is_rejected_before_sending(self, env, send):
        with pytest.raises(ValueError, match="at least one"):
            _import(FakeContext(), project="Sandbox", test_cases=[])

        send.assert_not_called()

    def test_options_are_omitted_by_default(self, env, send):
        _import(FakeContext(), project="Sandbox", test_cases=CASES)

        assert "options" not in send.call_args[0][1]

    def test_option_keys_are_plural(self, env, send):
        """The import endpoint spells its options in the plural.

        upsert uses createMissingSuite and createMissingSection; a singular key
        here would be ignored and every record in a new suite would fail.
        """
        _import(
            FakeContext(),
            project="Sandbox",
            test_cases=CASES,
            create_missing_suites=True,
            create_missing_sections=True,
        )

        assert send.call_args[0][1]["options"] == {
            "createMissingSuites": True,
            "createMissingSections": True,
        }

    def test_only_enabled_options_are_sent(self, env, send):
        _import(
            FakeContext(),
            project="Sandbox",
            test_cases=CASES,
            create_missing_sections=True,
        )

        assert send.call_args[0][1]["options"] == {"createMissingSections": True}

    def test_partial_failure_summary_is_returned_unchanged(self, env, send):
        """A 200 can still carry rejected records; the caller must see them."""
        summary = json.dumps(
            {
                "totalTestCases": 2,
                "successCount": 1,
                "errorCount": 1,
                "rowsWithError": [
                    {"record": 2, "errorMessage": "No entry found for Manager."}
                ],
            }
        )
        send.return_value = summary

        result = _import(FakeContext(), project="Sandbox", test_cases=CASES)

        assert result == summary

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _import(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            project="Sandbox",
            test_cases=CASES,
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _import(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            project="Sandbox",
            test_cases=CASES,
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(self, monkeypatch, send):
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _import(FakeContext(), project="Sandbox", test_cases=CASES)

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"
