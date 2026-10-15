import json

import tuskr_client
from test.helpers import FakeContext, call_tool
from tuskr_mcp.tools import bulk_export_test_runs as module


def _export(ctx, **kwargs):
    return call_tool(module.bulk_export_test_runs, ctx, **kwargs)


def _case(key="C-5", status="FAILED"):
    """A nested test case shaped like the real export, bulky fields included."""
    return {
        "ProjectId": "proj-1",
        "ID": "case-" + key,
        "Key": key,
        "Name": "Filter by brand",
        "Suite": "Catalog",
        "Section": "Filters",
        "Estimated Time": 0,
        "Type": "Functional",
        "Test Case Steps (Instructions)": "s" * 1000,
        "Test Case Steps (Expected Result)": "e" * 1000,
        "Test Case Preconditions": "p" * 500,
        "Test Run Id": "run-1",
        "Assigned To": None,
        "Result Id": "result-1",
        "Result Status": status,
        "Result Status Label": status.title(),
        "Result Comments": "c" * 2000,
        "Result Created At": "2026-10-01",
        "Result Created By": "someone",
        "Result Issue Ids": ["BUG-712"],
    }


def _run(cases=None):
    """A run row; `cases=None` omits testCases, as when they are excluded."""
    row = {
        "ID": "run-1",
        "Key": "R-1",
        "Name": "Smoke",
        "Status": "active",
        "Percent Done": 40,
        "Created At": "2026-09-30",
        "Updated At": "2026-10-01",
    }
    if cases is not None:
        row["testCases"] = cases
    return row


def _body(rows, **extra):
    return json.dumps(
        {"count": len(rows), "rows": rows, "meta": {"total": len(rows), "pages": 1}}
        | extra
    )


class TestBulkExportRequest:
    """The endpoint takes filter[...] query parameters; absent ones are omitted."""

    def test_project_only_request(self, env, send):
        _export(FakeContext(), filter_project="proj-1")

        action, body, method = send.call_args[0]
        assert action == "test-run/bulk-export"
        assert method == tuskr_client.RequestMethod.GET
        assert body == {"page": 1, "filter[project]": "proj-1"}

    def test_absent_filters_are_omitted(self, env, send):
        _export(
            FakeContext(),
            filter_project="proj-1",
            filter_assigned_to=None,
            filter_ids=[],
            filter_status=None,
            filter_completion_status=None,
        )

        assert set(send.call_args[0][1]) == {"page", "filter[project]"}

    def test_exclude_test_cases_is_sent_only_when_true(self, env, send):
        _export(FakeContext(), filter_project="proj-1")
        assert "filter[excludeTestCases]" not in send.call_args[0][1]

        _export(FakeContext(), filter_project="proj-1", filter_exclude_test_cases=True)
        assert send.call_args[0][1]["filter[excludeTestCases]"] == "true"

    def test_assigned_to_is_forwarded(self, env, send):
        _export(FakeContext(), filter_project="proj-1", filter_assigned_to="user-1")

        assert send.call_args[0][1]["filter[assignedTo]"] == "user-1"

    def test_single_id_is_sent_as_is(self, env, send):
        _export(FakeContext(), filter_project="proj-1", filter_ids="run-1")

        assert send.call_args[0][1]["filter[ids]"] == "run-1"

    def test_id_list_becomes_comma_separated(self, env, send):
        _export(FakeContext(), filter_project="proj-1", filter_ids=["run-1", "run-2"])

        assert send.call_args[0][1]["filter[ids]"] == "run-1,run-2"

    def test_status_and_completion_status_are_forwarded(self, env, send):
        _export(
            FakeContext(),
            filter_project="proj-1",
            filter_status="active",
            filter_completion_status="incomplete",
        )

        body = send.call_args[0][1]
        assert body["filter[status]"] == "active"
        assert body["filter[completionStatus]"] == "incomplete"

    def test_page_is_forwarded(self, env, send):
        _export(FakeContext(), filter_project="proj-1", page=3)

        assert send.call_args[0][1]["page"] == 3

    def test_fetches_exactly_one_page(self, env, send):
        send.return_value = json.dumps({"count": 250, "rows": [], "meta": {"pages": 3}})

        _export(FakeContext(), filter_project="proj-1")

        send.assert_called_once()


class TestBulkExportCredentials:
    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _export(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            filter_project="proj-1",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _export(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            filter_project="proj-1",
        )

        assert send.call_args[1]["ext_tenant_id"] == "tenant-from-header"


class TestBulkExportTrimming:
    """Trimming bounds the response without dropping result information."""

    def test_nested_cases_are_reduced_by_default(self, env, send):
        send.return_value = _body([_run([_case()])])

        row = json.loads(_export(FakeContext(), filter_project="proj-1"))["rows"][0]

        assert set(row["testCases"][0]) == {
            "ID",
            "Key",
            "Name",
            "Suite",
            "Section",
            "Assigned To",
            "Result Status",
            "Result Created At",
            "Result Created By",
            "Result Issue Ids",
        }

    def test_bulky_fields_are_dropped(self, env, send):
        send.return_value = _body([_run([_case()])])

        trimmed = _export(FakeContext(), filter_project="proj-1")

        for dropped in (
            "Test Case Steps (Instructions)",
            "Test Case Steps (Expected Result)",
            "Test Case Preconditions",
            "Result Comments",
        ):
            assert dropped not in trimmed

    def test_result_and_issue_keys_are_kept(self, env, send):
        send.return_value = _body([_run([_case(key="C-9", status="RETEST")])])

        case = json.loads(_export(FakeContext(), filter_project="proj-1"))["rows"][0][
            "testCases"
        ][0]

        assert case["Key"] == "C-9"
        assert case["Result Status"] == "RETEST"
        assert case["Result Issue Ids"] == ["BUG-712"]

    def test_run_level_fields_and_envelope_are_untouched(self, env, send):
        send.return_value = _body([_run([_case()])])

        result = json.loads(_export(FakeContext(), filter_project="proj-1"))

        assert result["count"] == 1
        assert result["meta"] == {"total": 1, "pages": 1}
        row = result["rows"][0]
        assert row["Key"] == "R-1"
        assert row["Percent Done"] == 40
        assert row["Updated At"] == "2026-10-01"

    def test_trimming_is_orders_of_magnitude_smaller(self, env, send):
        raw = _body([_run([_case(key=f"C-{n}") for n in range(25)])])
        send.return_value = raw

        trimmed = _export(FakeContext(), filter_project="proj-1")

        assert len(raw) > 100_000
        assert len(trimmed) < 10_000

    def test_trim_response_false_returns_the_raw_body(self, env, send):
        raw = _body([_run([_case()])])
        send.return_value = raw

        assert (
            _export(FakeContext(), filter_project="proj-1", trim_response=False) == raw
        )

    def test_rows_without_test_cases_are_untouched(self, env, send):
        send.return_value = _body([_run()])

        row = json.loads(_export(FakeContext(), filter_project="proj-1"))["rows"][0]

        assert row == _run()

    def test_non_dict_case_passes_through(self, env, send):
        send.return_value = _body([_run(["not-a-case"])])

        row = json.loads(_export(FakeContext(), filter_project="proj-1"))["rows"][0]

        assert row["testCases"] == ["not-a-case"]

    def test_error_body_passes_through_unchanged(self, env, send):
        send.return_value = "403 Forbidden"

        assert _export(FakeContext(), filter_project="proj-1") == "403 Forbidden"


class TestBulkExportSizeCap:
    """A response too big for an MCP client becomes an explanation, not a failure."""

    def test_oversized_response_is_replaced_by_an_error(self, env, send, monkeypatch):
        monkeypatch.setattr(module, "_MAX_RESPONSE_BYTES", 100)
        send.return_value = _body([_run([_case()])])

        result = json.loads(_export(FakeContext(), filter_project="proj-1"))

        assert "rows" not in result
        assert result["response_bytes"] > 100
        assert "filter_ids" in result["error"]
        assert "filter_exclude_test_cases" in result["error"]

    def test_error_carries_count_and_meta_but_no_row_content(
        self, env, send, monkeypatch
    ):
        monkeypatch.setattr(module, "_MAX_RESPONSE_BYTES", 100)
        send.return_value = _body([_run([_case()])])

        result = _export(FakeContext(), filter_project="proj-1")

        assert json.loads(result)["count"] == 1
        assert json.loads(result)["meta"] == {"total": 1, "pages": 1}
        assert "Smoke" not in result

    def test_response_under_the_cap_is_returned_whole(self, env, send, monkeypatch):
        monkeypatch.setattr(module, "_MAX_RESPONSE_BYTES", 10_000)
        send.return_value = _body([_run([_case()])])

        result = json.loads(_export(FakeContext(), filter_project="proj-1"))

        assert result["rows"][0]["Key"] == "R-1"

    def test_cap_applies_when_trimming_is_off(self, env, send, monkeypatch):
        monkeypatch.setattr(module, "_MAX_RESPONSE_BYTES", 100)
        send.return_value = _body([_run([_case()])])

        result = json.loads(
            _export(FakeContext(), filter_project="proj-1", trim_response=False)
        )

        assert "error" in result

    def test_non_json_body_is_not_measured(self, env, send, monkeypatch):
        monkeypatch.setattr(module, "_MAX_RESPONSE_BYTES", 5)
        send.return_value = "502 Bad Gateway"

        assert _export(FakeContext(), filter_project="proj-1") == "502 Bad Gateway"
