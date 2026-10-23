import json

import tuskr_client
from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import get_test_run_results as module


def _get_results(ctx, **kwargs):
    return call_tool(module.get_test_run_results, ctx, **kwargs)


def _result_row(key="C-5", status="FAILED"):
    """A results row shaped like the real API response.

    The nested testCase is the whole test case object, so the bulk of the
    payload sits inside it rather than at row level.
    """
    return {
        "testCase": {
            "id": "24921ff9-1512-4340-b43b-852a32e82f03",
            "key": key,
            "name": "Filter by brand",
            "description": "d" * 4000,
            "customFields": {"stepsWithExpectedResults": [{"step": 1}]},
            "resultHistory": {
                f"2024-07-04T08:19:0{n}": {"runId": "old", "status": "FAILED"}
                for n in range(9)
            },
            "openIssueIds": [f"ISSUE-{n}" for n in range(400)],
            "testRunTestCases": [
                {
                    "final": True,
                    "status": status,
                    "issueIds": ["BUG-712"],
                    "testRunId": "run-1",
                    "assignedToId": None,
                }
            ],
        },
        "latestStatus": status,
    }


class TestGetTestRunResultsRequest:
    """The run is addressed in the path; filters are plain comma separated."""

    def test_run_id_goes_in_the_path(self, env, send):
        _get_results(FakeContext(), test_run="246d1fa7")

        action, body, method = send.call_args[0]
        assert action == "test-run/246d1fa7/results"
        assert method == tuskr_client.RequestMethod.GET
        assert body == {"page": 1}

    def test_single_status_is_sent_as_is(self, env, send):
        _get_results(FakeContext(), test_run="run-1", status="FAILED")

        assert send.call_args[0][1]["status"] == "FAILED"

    def test_status_list_becomes_comma_separated(self, env, send):
        _get_results(FakeContext(), test_run="run-1", status=["RETEST", "FAILED"])

        # Tuskr documents `status` as a comma separated string, not a repeated
        # or bracketed parameter like the filter[...] endpoints use.
        assert send.call_args[0][1]["status"] == "RETEST,FAILED"

    def test_test_cases_list_becomes_comma_separated(self, env, send):
        _get_results(
            FakeContext(),
            test_run="run-1",
            test_cases=["C-1", "Pagination", "7911ff67"],
        )

        assert send.call_args[0][1]["testCases"] == "C-1,Pagination,7911ff67"

    def test_absent_filters_are_omitted(self, env, send):
        _get_results(FakeContext(), test_run="run-1", status=None, test_cases=[])

        assert set(send.call_args[0][1]) == {"page"}

    def test_page_is_forwarded(self, env, send):
        _get_results(FakeContext(), test_run="run-1", page=3)

        assert send.call_args[0][1]["page"] == 3

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        _get_results(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            test_run="run-1",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        _get_results(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            test_run="run-1",
        )

        assert send.call_args[1]["ext_tenant_id"] == "tenant-from-header"


class TestGetTestRunResultsTrimming:
    """Trimming bounds the response without dropping result information."""

    def test_nested_test_case_is_reduced_by_default(self, env, send):
        send.return_value = json.dumps({"data": [_result_row()], "meta": {"pages": 1}})

        row = json.loads(_get_results(FakeContext(), test_run="run-1"))["data"][0]

        assert set(row["testCase"]) == {"id", "key", "name", "testRunTestCases"}
        assert row["testCase"]["key"] == "C-5"
        assert row["testCase"]["name"] == "Filter by brand"

    def test_unbounded_history_fields_are_dropped(self, env, send):
        """resultHistory and openIssueIds are what blow the transport limit."""
        send.return_value = json.dumps({"data": [_result_row()]})

        trimmed = _get_results(FakeContext(), test_run="run-1")

        for dropped in ("resultHistory", "openIssueIds", "customFields"):
            assert dropped not in trimmed

    def test_this_runs_result_and_issue_keys_are_kept(self, env, send):
        """testRunTestCases is run-scoped, so it stays: it names the bug filed."""
        send.return_value = json.dumps({"data": [_result_row()]})

        row = json.loads(_get_results(FakeContext(), test_run="run-1"))["data"][0]

        assert row["testCase"]["testRunTestCases"][0]["issueIds"] == ["BUG-712"]
        assert row["testCase"]["testRunTestCases"][0]["final"] is True

    def test_latest_status_survives_trimming(self, env, send):
        send.return_value = json.dumps({"data": [_result_row(status="RETEST")]})

        row = json.loads(_get_results(FakeContext(), test_run="run-1"))["data"][0]

        assert row["latestStatus"] == "RETEST"

    def test_meta_is_preserved(self, env, send):
        send.return_value = json.dumps({"data": [], "meta": {"total": 110, "pages": 2}})

        result = json.loads(_get_results(FakeContext(), test_run="run-1"))

        assert result["meta"] == {"total": 110, "pages": 2}

    def test_trimming_is_orders_of_magnitude_smaller(self, env, send):
        raw = json.dumps({"data": [_result_row()]})
        send.return_value = raw

        trimmed = _get_results(FakeContext(), test_run="run-1")

        assert len(raw) > 8000
        assert len(trimmed) < 500

    def test_trim_response_false_returns_the_raw_body(self, env, send):
        raw = json.dumps({"data": [_result_row()], "meta": {"pages": 1}})
        send.return_value = raw

        assert _get_results(FakeContext(), test_run="run-1", trim_response=False) == raw

    def test_row_without_a_test_case_is_untouched(self, env, send):
        send.return_value = json.dumps({"data": [{"latestStatus": "PASSED"}]})

        row = json.loads(_get_results(FakeContext(), test_run="run-1"))["data"][0]

        assert row == {"latestStatus": "PASSED"}

    def test_error_body_passes_through_unchanged(self, env, send):
        send.return_value = "403 Forbidden"

        assert _get_results(FakeContext(), test_run="run-1") == "403 Forbidden"


class TestGetTestRunResultsPagination:
    """fetch_all_pages walks meta.pages; the default fetches exactly one page."""

    def test_default_fetches_one_page_only(self, env, send):
        send.return_value = json.dumps(
            {"data": [_result_row()], "meta": {"total": 110, "pages": 2}}
        )

        _get_results(FakeContext(), test_run="run-1")

        send.assert_called_once()

    def test_all_pages_are_combined(self, env, send):
        send.side_effect = [
            json.dumps(
                {"data": [_result_row(key="C-1")], "meta": {"total": 3, "pages": 3}}
            ),
            json.dumps({"data": [_result_row(key="C-2")], "meta": {"pages": 3}}),
            json.dumps({"data": [_result_row(key="C-3")], "meta": {"pages": 3}}),
        ]

        result = json.loads(
            _get_results(FakeContext(), test_run="run-1", fetch_all_pages=True)
        )

        assert [row["testCase"]["key"] for row in result["data"]] == [
            "C-1",
            "C-2",
            "C-3",
        ]
        assert [call[0][1]["page"] for call in send.call_args_list] == [1, 2, 3]
        assert result["meta"] == {"total": 3, "pages": 3}

    def test_all_pages_ignores_the_page_argument(self, env, send):
        send.return_value = json.dumps({"data": [], "meta": {"pages": 1}})

        _get_results(FakeContext(), test_run="run-1", page=7, fetch_all_pages=True)

        assert send.call_args[0][1]["page"] == 1

    def test_all_pages_still_trims(self, env, send):
        send.return_value = json.dumps({"data": [_result_row()], "meta": {"pages": 1}})

        combined = _get_results(FakeContext(), test_run="run-1", fetch_all_pages=True)

        assert "customFields" not in combined

    def test_all_pages_passes_through_a_non_json_body(self, env, send):
        send.return_value = "502 Bad Gateway"

        assert (
            _get_results(FakeContext(), test_run="run-1", fetch_all_pages=True)
            == "502 Bad Gateway"
        )
