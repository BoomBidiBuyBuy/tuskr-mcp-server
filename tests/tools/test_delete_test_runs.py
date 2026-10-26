import pytest

import tuskr_client
from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import delete_test_runs as module

PROJECT_ID = "5d2f1c3a-8b7e-4f6a-9c0d-1e2f3a4b5c6d"
OTHER_PROJECT_ID = "6e3f2d4b-9c8f-4a7b-8d1e-2f3a4b5c6d7e"


def _delete(ctx, **kwargs):
    return call_tool(module.delete_test_runs, ctx, **kwargs)


def _body(send):
    return send.call_args[0][1]


class TestDeleteTestRuns:
    """Cover the bulk test-run deletion wrapper and its guards."""

    def test_sends_a_delete_to_the_bulk_action(self, env, send):
        _delete(FakeContext(), projects=PROJECT_ID, name_starts_with="probe")

        action, _, method = send.call_args[0]
        assert action == "test-run/bulk"
        assert method == tuskr_client.RequestMethod.DELETE

    def test_single_project_is_wrapped_in_a_list(self, env, send):
        _delete(FakeContext(), projects=PROJECT_ID, name_starts_with="probe")

        assert _body(send)["projects"] == [PROJECT_ID]

    def test_multiple_projects_are_forwarded_as_given(self, env, send):
        _delete(
            FakeContext(),
            projects=[PROJECT_ID, OTHER_PROJECT_ID],
            name_starts_with="probe",
        )

        assert _body(send)["projects"] == [PROJECT_ID, OTHER_PROJECT_ID]

    def test_filters_map_to_the_api_keys(self, env, send):
        _delete(
            FakeContext(),
            projects=PROJECT_ID,
            name_starts_with="probe",
            older_than_days=30,
        )

        assert _body(send) == {
            "projects": [PROJECT_ID],
            "nameStartsWith": "probe",
            "olderThanDays": 30,
        }

    def test_purge_is_absent_by_default(self, env, send):
        """Without purge the runs go to the recycle bin, which is the safe default."""
        _delete(FakeContext(), projects=PROJECT_ID, name_starts_with="probe")

        assert "purge" not in _body(send)

    def test_purge_is_sent_only_on_explicit_opt_in(self, env, send):
        _delete(
            FakeContext(), projects=PROJECT_ID, name_starts_with="probe", purge=True
        )

        assert _body(send)["purge"] is True

    def test_older_than_days_zero_is_sent(self, env, send):
        """0 is the explicit way to match runs of any age, not an unset value."""
        _delete(FakeContext(), projects=PROJECT_ID, older_than_days=0)

        assert _body(send) == {"projects": [PROJECT_ID], "olderThanDays": 0}

    def test_projects_alone_is_refused(self, env, send):
        """A call with no narrowing filter would delete every run in the project."""
        with pytest.raises(ValueError, match="name_starts_with or older_than_days"):
            _delete(FakeContext(), projects=PROJECT_ID)

        send.assert_not_called()

    def test_blank_name_counts_as_no_filter(self, env, send):
        with pytest.raises(ValueError, match="name_starts_with or older_than_days"):
            _delete(FakeContext(), projects=PROJECT_ID, name_starts_with="   ")

        send.assert_not_called()

    @pytest.mark.parametrize("projects", ["", "  ", [], ["", " "]])
    def test_missing_projects_are_refused(self, env, send, projects):
        with pytest.raises(ValueError, match="at least one project"):
            _delete(FakeContext(), projects=projects, name_starts_with="probe")

        send.assert_not_called()

    def test_negative_age_is_refused(self, env, send):
        with pytest.raises(ValueError, match="0 or greater"):
            _delete(FakeContext(), projects=PROJECT_ID, older_than_days=-1)

        send.assert_not_called()

    @pytest.mark.parametrize("value", [True, "30", 1.5])
    def test_non_integer_age_is_refused(self, env, send, value):
        with pytest.raises(TypeError, match="integer"):
            _delete(FakeContext(), projects=PROJECT_ID, older_than_days=value)

        send.assert_not_called()

    def test_values_are_stripped(self, env, send):
        _delete(FakeContext(), projects=[f" {PROJECT_ID} "], name_starts_with=" probe ")

        assert _body(send) == {"projects": [PROJECT_ID], "nameStartsWith": "probe"}

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _delete(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            projects=PROJECT_ID,
            name_starts_with="probe",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _delete(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            projects=PROJECT_ID,
            name_starts_with="probe",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"
