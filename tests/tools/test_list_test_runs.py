import json

import pytest

from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import list_test_runs as module


def _run_tool(ctx, **kwargs):
    return call_tool(module.list_test_runs, ctx, **kwargs)


def _user(**overrides):
    """A Tuskr user object shaped like the real API response."""
    user = {
        "id": "9f1c0e2a",
        "fullName": "Test User",
        "email": "qa.lead@example.com",
        "applicationState": "x" * 16209,
        "passwordResetTokenExpiresAt": "2026-08-01T10:00:00Z",
        "jwtTokenInvalidBefore": "2026-07-30T09:00:00Z",
        "lastLoginAt": "2026-08-09T07:14:00Z",
    }
    user.update(overrides)
    return user


class TestTrimAssignee:
    def test_keeps_only_identifying_fields(self):
        assert module.trim_assignee(_user()) == {
            "id": "9f1c0e2a",
            "fullName": "Test User",
            "email": "qa.lead@example.com",
        }

    def test_drops_application_state_and_security_metadata(self):
        trimmed = module.trim_assignee(_user())
        for dropped in (
            "applicationState",
            "passwordResetTokenExpiresAt",
            "jwtTokenInvalidBefore",
            "lastLoginAt",
        ):
            assert dropped not in trimmed

    def test_unassigned_run_stays_none(self):
        assert module.trim_assignee(None) is None

    def test_non_dict_value_passes_through(self):
        assert module.trim_assignee("9f1c0e2a") == "9f1c0e2a"

    def test_missing_fields_are_omitted_not_nulled(self):
        assert module.trim_assignee({"id": "abc"}) == {"id": "abc"}

    def test_trimmed_row_is_orders_of_magnitude_smaller(self):
        raw_size = len(json.dumps(_user()))
        trimmed_size = len(json.dumps(module.trim_assignee(_user())))
        assert raw_size > 16_000
        assert trimmed_size < 300


class TestTrimTestRunRows:
    def test_trims_assignee_on_every_row(self):
        raw = json.dumps(
            {
                "rows": [
                    {"id": "run-1", "assignedTo": _user()},
                    {"id": "run-2", "assignedTo": _user(id="other")},
                ],
                "meta": {"pages": 1},
            }
        )
        data = json.loads(module.trim_test_run_rows(raw))
        assert [row["assignedTo"]["id"] for row in data["rows"]] == [
            "9f1c0e2a",
            "other",
        ]
        assert "applicationState" not in module.trim_test_run_rows(raw)

    def test_leaves_every_other_field_untouched(self):
        row = {
            "id": "run-1",
            "key": "TR-1",
            "name": "Regression",
            "description": "unchanged",
            "customFields": {"a": 1},
            "assignedTo": _user(),
        }
        data = json.loads(module.trim_test_run_rows(json.dumps({"rows": [row]})))
        trimmed = data["rows"][0]
        assert {k: v for k, v in trimmed.items() if k != "assignedTo"} == {
            k: v for k, v in row.items() if k != "assignedTo"
        }

    def test_meta_is_preserved(self):
        raw = json.dumps({"rows": [], "meta": {"pages": 3, "total": 250}})
        assert json.loads(module.trim_test_run_rows(raw))["meta"] == {
            "pages": 3,
            "total": 250,
        }

    def test_unassigned_row_keeps_null_assignee(self):
        raw = json.dumps({"rows": [{"id": "run-1", "assignedTo": None}]})
        assert (
            json.loads(module.trim_test_run_rows(raw))["rows"][0]["assignedTo"] is None
        )

    def test_row_without_assignee_key_is_not_given_one(self):
        raw = json.dumps({"rows": [{"id": "run-1"}]})
        assert "assignedTo" not in json.loads(module.trim_test_run_rows(raw))["rows"][0]

    def test_error_body_passes_through_unchanged(self):
        raw = json.dumps({"errors": [{"code": "NOT_FOUND"}]})
        assert module.trim_test_run_rows(raw) == raw

    def test_non_json_passes_through_unchanged(self):
        assert module.trim_test_run_rows("502 Bad Gateway") == "502 Bad Gateway"


class TestListTestRunsTrimming:
    @pytest.fixture(autouse=True)
    def _creds(self, monkeypatch):
        monkeypatch.setenv("TUSKR_TENANT_ID", "tenant-1")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-1")

    def test_incomplete_rows_carry_trimmed_assignee(self, monkeypatch):
        page = {
            "rows": [
                {
                    "id": "run-1",
                    "key": "TR-1",
                    "name": "Regression",
                    "percentDone": 42,
                    "totalTestCaseCount": 10,
                    "doneTestCaseCount": 4,
                    "assignedTo": _user(),
                    "deadline": "2026-08-20",
                    "status": "ACTIVE",
                },
                {
                    "id": "run-2",
                    "key": "TR-2",
                    "name": "Smoke",
                    "percentDone": 100,
                    "assignedTo": _user(),
                },
            ],
            "meta": {"pages": 1},
        }
        monkeypatch.setattr(
            "tuskr_client.send", lambda *args, **kwargs: json.dumps(page)
        )

        result = json.loads(
            _run_tool(FakeContext(), filter_project="p", filter_incomplete=True)
        )

        assert result["count"] == 1
        row = result["rows"][0]
        assert row["id"] == "run-1"
        assert row["assignedTo"] == {
            "id": "9f1c0e2a",
            "fullName": "Test User",
            "email": "qa.lead@example.com",
        }
        assert "applicationState" not in json.dumps(result)
        assert len(json.dumps(result)) < 500

    def test_default_path_rows_carry_trimmed_assignee(self, monkeypatch):
        page = {
            "rows": [
                {
                    "id": "run-1",
                    "key": "TR-1",
                    "name": "Regression",
                    "percentDone": 100,
                    "assignedTo": _user(),
                }
            ],
            "meta": {"pages": 1, "total": 1},
        }
        monkeypatch.setattr(
            "tuskr_client.send", lambda *args, **kwargs: json.dumps(page)
        )

        raw = _run_tool(FakeContext(), filter_project="p")
        result = json.loads(raw)

        # Completed runs are still returned here, unlike the filter_incomplete
        # path, and meta survives so pagination keeps working.
        assert result["meta"] == {"pages": 1, "total": 1}
        assert result["rows"][0]["assignedTo"] == {
            "id": "9f1c0e2a",
            "fullName": "Test User",
            "email": "qa.lead@example.com",
        }
        assert "applicationState" not in raw
        assert "passwordResetTokenExpiresAt" not in raw
