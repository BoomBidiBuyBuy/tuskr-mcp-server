import pytest

import tuskr_client
from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import update_test_run as module

RUN = "11111111-1111-4111-8111-111111111111"
PROJECT = "22222222-2222-4222-8222-222222222222"
CASE_A = "33333333-3333-4333-8333-333333333333"
CASE_B = "44444444-4444-4444-8444-444444444444"


def _update_run(ctx, **kwargs):
    kwargs.setdefault("test_run", RUN)
    kwargs.setdefault("test_case_inclusion_type", "SPECIFIC")
    return call_tool(module.update_test_run, ctx, **kwargs)


class TestUpdateTestRun:
    """Cover the test-run update wrapper."""

    def test_specific_selection_is_sent_as_a_put_with_the_id_beside_data(
        self, env, send
    ):
        _update_run(
            FakeContext(),
            test_cases=[CASE_A, CASE_B],
            name="Regression run",
            project=PROJECT,
        )

        action, body, method = send.call_args[0]
        assert action == f"test-run/{RUN}"
        assert method == tuskr_client.RequestMethod.PUT
        assert body == {
            "name": "Regression run",
            "project": PROJECT,
            "testCaseInclusionType": "SPECIFIC",
            "testCases": [CASE_A, CASE_B],
        }
        # The id is a sibling of `data`, not a key inside it.
        assert "id" not in body
        assert send.call_args[1]["top_level"] == {"id": RUN}

    def test_name_and_project_are_omitted_when_unset(self, env, send):
        """Tuskr keeps the current name and project when they are not sent."""
        _update_run(FakeContext(), test_cases=[CASE_A])

        assert send.call_args[0][1] == {
            "testCaseInclusionType": "SPECIFIC",
            "testCases": [CASE_A],
        }

    def test_blank_name_and_project_are_not_forwarded(self, env, send):
        _update_run(FakeContext(), test_cases=[CASE_A], name="", project="")

        body = send.call_args[0][1]
        assert "name" not in body
        assert "project" not in body

    def test_single_test_case_id_is_promoted_to_a_list(self, env, send):
        _update_run(FakeContext(), test_cases=CASE_A)

        assert send.call_args[0][1]["testCases"] == [CASE_A]

    def test_all_selection_sends_no_test_cases_key(self, env, send):
        _update_run(FakeContext(), test_case_inclusion_type="ALL")

        body = send.call_args[0][1]
        assert body == {"testCaseInclusionType": "ALL"}
        assert send.call_args[1]["top_level"] == {"id": RUN}

    def test_all_selection_accepts_an_empty_list(self, env, send):
        _update_run(FakeContext(), test_case_inclusion_type="ALL", test_cases=[])

        assert "testCases" not in send.call_args[0][1]

    def test_inclusion_type_is_case_insensitive_and_sent_upper_case(self, env, send):
        _update_run(
            FakeContext(), test_case_inclusion_type="specific", test_cases=[CASE_A]
        )

        assert send.call_args[0][1]["testCaseInclusionType"] == "SPECIFIC"

    def test_wire_body_carries_the_id_beside_data(self, env, mocker):
        """Through the real client: Tuskr answers 500 without the top-level id."""
        put = mocker.patch("requests.put", return_value=mocker.Mock(text="{}"))

        _update_run(
            FakeContext(),
            test_cases=[CASE_A],
            name="Regression run",
            project=PROJECT,
        )

        assert put.call_args[0][0].endswith(f"/tenant-from-env/test-run/{RUN}")
        assert put.call_args[1]["json"] == {
            "id": RUN,
            "data": {
                "name": "Regression run",
                "project": PROJECT,
                "testCaseInclusionType": "SPECIFIC",
                "testCases": [CASE_A],
            },
        }


class TestUpdateTestRunValidation:
    """Bad input fails locally, before any request leaves the process."""

    def test_unknown_inclusion_type_raises(self, env, send):
        with pytest.raises(ValueError, match="'ALL' or 'SPECIFIC'"):
            _update_run(
                FakeContext(), test_case_inclusion_type="SOME", test_cases=[CASE_A]
            )

        send.assert_not_called()

    @pytest.mark.parametrize("test_cases", [None, []])
    def test_specific_without_test_cases_raises(self, env, send, test_cases):
        with pytest.raises(ValueError, match="required"):
            _update_run(FakeContext(), test_cases=test_cases)

        send.assert_not_called()

    def test_all_with_test_cases_raises(self, env, send):
        with pytest.raises(ValueError, match="cannot be combined"):
            _update_run(
                FakeContext(), test_case_inclusion_type="ALL", test_cases=[CASE_A]
            )

        send.assert_not_called()


class TestUpdateTestRunCredentials:
    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _update_run(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            test_cases=[CASE_A],
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _update_run(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            test_cases=[CASE_A],
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(self, monkeypatch, send):
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _update_run(FakeContext(), test_cases=[CASE_A])

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"
