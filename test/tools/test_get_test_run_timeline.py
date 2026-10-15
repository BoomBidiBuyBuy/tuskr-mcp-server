import json
from datetime import datetime

import tuskr_client
from test.helpers import FakeContext, call_tool
from tuskr_mcp.tools import get_test_run_timeline as module

RUN = "246d1fa7-9c30-4e21-8f7a-1b0d55e2c711"


def _naive(text):
    """A naive datetime, matching what parse_timestamp returns."""
    return datetime.fromisoformat(text)


def _timeline(ctx, **kwargs):
    return call_tool(module.get_test_run_timeline, ctx, **kwargs)


def _row(key, history=None):
    """A results row carrying only what the aggregation reads.

    The real nested testCase is the whole test case object; everything the
    aggregation ignores is left out so the expectations stay readable.
    """
    return {
        "testCase": {
            "id": f"id-{key}",
            "key": key,
            "name": f"Case {key}",
            "resultHistory": {} if history is None else history,
        },
        "latestStatus": "PASSED",
    }


def _results(rows, pages=1):
    return json.dumps({"data": rows, "meta": {"total": len(rows), "pages": pages}})


def _run_body(**overrides):
    run = {
        "id": RUN,
        "key": "R-4",
        "name": "Nightly regression",
        "status": "COMPLETED",
        "createdAt": "2026-08-24T08:00:00.000Z",
        "lockedAt": "2026-08-28T16:00:00.000Z",
        # The raw run object also embeds the whole project and the assignee's
        # UI state; both must be dropped by _RUN_FIELDS.
        "project": {"id": "p-1", "name": "Example Project"},
        "assignedTo": {"id": "u-1", "uiState": {"lastTab": "results"}},
    }
    run.update(overrides)
    return json.dumps({"data": run})


# Two cases executed against this run over two days, three events in total.
# C-3 was executed, but only in a different run; C-4 was never executed at all.
# Both count as inherited-but-untouched scope for this run.
_ROWS = [
    _row(
        "C-1",
        {
            "2026-08-24T10:00:00": {"runId": RUN, "status": "PASSED"},
            "2026-08-24T11:15:00": {"runId": RUN, "status": "FAILED"},
            "2026-01-04T09:00:00": {"runId": "run-earlier", "status": "PASSED"},
        },
    ),
    _row("C-2", {"2026-08-25T13:30:00": {"runId": RUN, "status": "PASSED"}}),
    _row("C-3", {"2026-01-04T09:00:00": {"runId": "run-earlier", "status": "PASSED"}}),
    _row("C-4"),
]


class TestParseTimestamp:
    """Both Tuskr timestamp forms have to normalise to the same naive UTC."""

    def test_run_field_with_zulu_marker(self):
        parsed = module.parse_timestamp("2026-01-21T09:59:28.103Z")

        assert parsed == _naive("2026-01-21T09:59:28.103")
        assert parsed.tzinfo is None

    def test_bare_result_history_key(self):
        assert module.parse_timestamp("2026-01-22T10:33:07") == _naive(
            "2026-01-22T10:33:07"
        )

    def test_explicit_offset_is_converted_to_utc_and_made_naive(self):
        """An aware value would raise TypeError against a bare history key."""
        parsed = module.parse_timestamp("2026-01-22T12:33:07+02:00")

        assert parsed == _naive("2026-01-22T10:33:07")
        assert parsed.tzinfo is None

    def test_the_two_forms_are_subtractable(self):
        run_field = module.parse_timestamp("2026-08-24T08:00:00.000Z")
        history_key = module.parse_timestamp("2026-08-24T10:00:00")

        assert module.span_minutes(run_field, history_key) == 120.0

    def test_unparseable_and_empty_values_are_none(self):
        for value in ("", "not-a-date", None, 17, {}):
            assert module.parse_timestamp(value) is None


class TestSpanMinutes:
    """Minutes, so an afternoon does not round to a fraction of a day."""

    def test_an_afternoon_keeps_its_resolution(self):
        start = _naive("2026-08-24T13:00:00")
        end = _naive("2026-08-24T16:30:00")

        assert module.span_minutes(start, end) == 210.0

    def test_sub_minute_span_is_kept_to_one_decimal(self):
        start = _naive("2026-08-24T13:00:00")
        end = _naive("2026-08-24T13:00:18")

        assert module.span_minutes(start, end) == 0.3

    def test_missing_end_stays_none_rather_than_zero(self):
        stamp = _naive("2026-08-24T13:00:00")

        assert module.span_minutes(stamp, None) is None
        assert module.span_minutes(None, stamp) is None


class TestGetTestRunTimelineRequest:
    """Untrimmed results pages, then the run object; both GET, run in the path."""

    def test_results_are_fetched_untrimmed_from_the_run_path(self, env, send):
        send.side_effect = [_results(_ROWS), _run_body()]

        _timeline(FakeContext(), test_run=RUN)

        action, body, method = send.call_args_list[0][0]
        assert action == f"test-run/{RUN}/results"
        assert method == tuskr_client.RequestMethod.GET
        # No trim flag exists on the endpoint: the history is what this tool
        # reads, so the page must come back whole.
        assert body == {"page": 1}

    def test_run_object_is_fetched_after_the_results(self, env, send):
        send.side_effect = [_results(_ROWS), _run_body()]

        _timeline(FakeContext(), test_run=RUN)

        action, body, method = send.call_args_list[-1][0]
        assert action == f"test-run/{RUN}"
        assert method == tuskr_client.RequestMethod.GET
        assert body == {}

    def test_all_pages_are_walked_before_the_run_is_fetched(self, env, send):
        send.side_effect = [
            _results([_ROWS[0]], pages=2),
            _results([_ROWS[1]], pages=2),
            _run_body(),
        ]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        assert [call[0][0] for call in send.call_args_list] == [
            f"test-run/{RUN}/results",
            f"test-run/{RUN}/results",
            f"test-run/{RUN}",
        ]
        assert [call[0][1].get("page") for call in send.call_args_list[:2]] == [1, 2]
        assert result["totalExecutionEvents"] == 3

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        send.side_effect = [_results(_ROWS), _run_body()]

        _timeline(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            test_run=RUN,
        )

        kwargs = send.call_args_list[0][1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        send.side_effect = [_results(_ROWS), _run_body()]

        _timeline(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            test_run=RUN,
        )

        assert send.call_args_list[0][1]["ext_tenant_id"] == "tenant-from-header"


class TestGetTestRunTimelineAggregation:
    """Only this run's history entries count towards the execution window."""

    def test_execution_window_ignores_other_runs(self, env, send):
        send.side_effect = [_results(_ROWS), _run_body()]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        # C-1's 2026-01-04 entry belongs to run-earlier and would otherwise
        # stretch the window by seven months.
        assert result["firstExecutedAt"] == "2026-08-24T10:00:00"
        assert result["lastExecutedAt"] == "2026-08-25T13:30:00"
        assert result["executionSpanMinutes"] == 1650.0
        assert result["totalExecutionEvents"] == 3

    def test_case_counts_separate_executed_from_inherited(self, env, send):
        send.side_effect = [_results(_ROWS), _run_body()]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        assert result["casesInRun"] == 4
        assert result["casesExecuted"] == 2
        assert result["casesNeverExecuted"] == 2
        # C-3 has history, but none of it against this run.
        assert result["neverExecutedKeys"] == ["C-3", "C-4"]
        assert "neverExecutedKeysTruncated" not in result

    def test_distinct_days_and_daily_breakdown(self, env, send):
        send.side_effect = [_results(_ROWS), _run_body()]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        assert result["distinctExecutionDays"] == 2
        assert result["executionsByDay"] == {"2026-08-24": 2, "2026-08-25": 1}

    def test_daily_breakdown_can_be_switched_off(self, env, send):
        send.side_effect = [_results(_ROWS), _run_body()]

        result = json.loads(
            _timeline(FakeContext(), test_run=RUN, include_daily_breakdown=False)
        )

        assert "executionsByDay" not in result
        assert result["distinctExecutionDays"] == 2

    def test_history_bulk_never_reaches_the_caller(self, env, send):
        """The reduction is the point: pages in, a handful of numbers out."""
        noisy = _row(
            "C-9",
            {
                f"2026-08-24T10:{minute:02d}:00": {"runId": RUN, "status": "PASSED"}
                for minute in range(60)
            },
        )
        raw = _results([noisy])
        send.side_effect = [raw, _run_body()]

        result = _timeline(FakeContext(), test_run=RUN)

        assert "resultHistory" not in result
        assert len(result) < len(raw)
        assert json.loads(result)["totalExecutionEvents"] == 60

    def test_malformed_history_key_is_dropped_not_fatal(self, env, send):
        rows = [
            _row(
                "C-1",
                {
                    "not-a-timestamp": {"runId": RUN, "status": "PASSED"},
                    "2026-08-24T10:00:00": {"runId": RUN, "status": "PASSED"},
                },
            )
        ]
        send.side_effect = [_results(rows), _run_body()]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        assert result["totalExecutionEvents"] == 1
        assert result["firstExecutedAt"] == "2026-08-24T10:00:00"

    def test_never_executed_keys_are_capped(self, env, send):
        rows = [_row(f"C-{n:03d}") for n in range(60)]
        send.side_effect = [_results(rows), _run_body()]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        assert result["casesNeverExecuted"] == 60
        assert len(result["neverExecutedKeys"]) == module._MAX_LISTED_KEYS
        assert result["neverExecutedKeysTruncated"] is True

    def test_genuinely_untested_run_reports_zeros_without_mismatch(self, env, send):
        send.side_effect = [_results([_row("C-1"), _row("C-2")]), _run_body()]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        assert result["casesExecuted"] == 0
        assert result["firstExecutedAt"] is None
        assert result["executionSpanMinutes"] is None
        assert "runIdMismatch" not in result

    def test_wrong_identifier_is_flagged_instead_of_zeroed(self, env, send):
        """A clean zero here would read as "nobody tested this run"."""
        send.side_effect = [_results(_ROWS), _run_body()]

        result = json.loads(_timeline(FakeContext(), test_run="R-4"))

        assert result["casesExecuted"] == 0
        assert result["runIdMismatch"]["requested"] == "R-4"
        assert RUN in result["runIdMismatch"]["runIdsInHistory"]


class TestGetTestRunTimelineRunMetadata:
    """The run object supplies the administrative bracket, and may be absent."""

    def test_administrative_and_real_durations_sit_side_by_side(self, env, send):
        send.side_effect = [_results(_ROWS), _run_body()]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        assert result["runMetadataAvailable"] is True
        assert result["key"] == "R-4"
        assert result["status"] == "COMPLETED"
        # createdAt to lockedAt spans four days; the testing itself spans one.
        assert result["createdToLockedMinutes"] == 6240.0
        assert result["createdToFirstExecutionMinutes"] == 120.0
        assert result["lastExecutionToLockedMinutes"] == 4470.0

    def test_project_and_ui_state_are_not_carried_through(self, env, send):
        send.side_effect = [_results(_ROWS), _run_body()]

        result = _timeline(FakeContext(), test_run=RUN)

        for dropped in ("project", "assignedTo", "uiState"):
            assert dropped not in result

    def test_missing_locked_at_leaves_its_spans_none(self, env, send):
        send.side_effect = [_results(_ROWS), _run_body(lockedAt=None)]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        assert result["createdToLockedMinutes"] is None
        assert result["lastExecutionToLockedMinutes"] is None
        assert result["createdToFirstExecutionMinutes"] == 120.0

    def test_unretrievable_run_degrades_instead_of_failing(self, env, send):
        """The execution window does not depend on the run object."""
        send.side_effect = [_results(_ROWS), "403 Forbidden"]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        assert result["runMetadataAvailable"] is False
        assert result["firstExecutedAt"] == "2026-08-24T10:00:00"
        assert "createdToLockedMinutes" not in result

    def test_run_body_without_a_data_envelope_is_accepted(self, env, send):
        send.side_effect = [_results(_ROWS), json.dumps({"id": RUN, "key": "R-4"})]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        assert result["runMetadataAvailable"] is True
        assert result["key"] == "R-4"


class TestGetTestRunTimelineErrorBodies:
    """A non-JSON results body is returned as-is, and stops the walk."""

    def test_error_body_passes_through_unchanged(self, env, send):
        send.return_value = "403 Forbidden"

        assert _timeline(FakeContext(), test_run=RUN) == "403 Forbidden"
        send.assert_called_once()

    def test_json_without_a_data_list_passes_through(self, env, send):
        send.return_value = json.dumps({"error": "not found"})

        assert _timeline(FakeContext(), test_run=RUN) == json.dumps(
            {"error": "not found"}
        )

    def test_a_broken_later_page_stops_the_walk_and_keeps_page_one(self, env, send):
        send.side_effect = [
            _results([_ROWS[0]], pages=3),
            "502 Bad Gateway",
            _run_body(),
        ]

        result = json.loads(_timeline(FakeContext(), test_run=RUN))

        # Page 3 is never requested: the walk breaks, and the run fetch is the
        # third and last call.
        assert send.call_count == 3
        assert result["casesExecuted"] == 1
        assert result["totalExecutionEvents"] == 2
        assert result["runMetadataAvailable"] is True
