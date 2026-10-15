"""The get_test_run_timeline tool, and the resultHistory aggregation it needs.

A run's own record carries no execution timestamps. `createdAt` is when the run
was opened and `lockedAt` is when someone locked it afterwards, so the span
between them overstates how long testing actually took, often by days at either
end. Tuskr's run-details endpoint (see get_test_run_details) now reports the
first and last result times, but only as a single span with no daily breakdown,
and it may return nulls for results recorded before the endpoint shipped. This
tool derives the same numbers from resultHistory, which Tuskr records for every
execution, so it also works for older runs.

The real per-execution timestamps live in `testCase.resultHistory`, a map of
timestamp to `{runId, status}` covering the case's entire life across every run
it has ever appeared in. Filtering those entries by the run being asked about
gives the true first and last execution.

That field is why `get_test_run_results` trims by default: it grows without
bound, and a busy run's untrimmed pages exceed the MCP transport limit. This
tool fetches untrimmed pages, reduces them to a handful of numbers, and returns
only those, so the history never reaches the caller.

The aggregation helpers stay in this module rather than a shared one: they are
used by this tool alone, and a shared module would be a file every future tool
branch has to touch.
"""

import json
from collections import Counter
from datetime import UTC, datetime

from fastmcp import Context

import tuskr_client
from tuskr_mcp import credentials
from tuskr_mcp.server import mcp

# Run fields carried through when the run object is available. The raw object
# also embeds the entire project (counts, key sequences, timestamps) and the
# assignee's UI state, none of which belongs in a timing summary.
_RUN_FIELDS = ("id", "key", "name", "createdAt", "lockedAt", "status")

_SECONDS_PER_MINUTE = 60.0

# Cap on any key list this tool returns. The tool exists to reduce an unbounded
# payload to a handful of numbers, so a run that inherited thousands of
# untouched cases must not turn its own summary into a dump.
_MAX_LISTED_KEYS = 50


def parse_timestamp(value):
    """Parse a Tuskr timestamp into a naive UTC datetime, or None.

    Tuskr is inconsistent about zone markers: run fields come back as
    `2026-01-21T09:59:28.103Z` while resultHistory keys are bare, as in
    `2026-01-22T10:33:07`. Both denote UTC, so the marker is stripped and every
    value compared naive. Mixing the two forms raises TypeError at subtraction
    time, which is why this is normalised in one place.

    An explicit offset (`+02:00`) is handled too, by converting to UTC and
    dropping the tzinfo. Nothing observed emits one today, but returning an
    aware value here would raise TypeError on the first subtraction against a
    bare resultHistory key.
    """
    if not isinstance(value, str) or not value:
        return None
    text = value.removesuffix("Z")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def span_minutes(start, end):
    """Minutes between two datetimes, to one decimal.

    Minutes rather than days: the question this tool answers is usually whether
    a run was executed in a single afternoon or spread across a week, and a
    two-decimal fraction of a day gives 14-minute granularity, rounding that
    afternoon down to a meaningless 0.15. Minutes also match the unit Tuskr's
    own run-details endpoint reports, so the two stay directly comparable.

    Returns None when either end is missing, so an absent value stays absent
    rather than becoming a misleading zero.
    """
    if start is None or end is None:
        return None
    return round((end - start).total_seconds() / _SECONDS_PER_MINUTE, 1)


def executions_for_run(test_case, test_run_id):
    """Timestamps from one case's resultHistory that belong to this run.

    Returns `(stamps, run_ids_seen)`: naive datetimes recorded against this run,
    and every runId the case's history mentions. The second element exists so
    the caller can tell "this run was never executed" apart from "the
    identifier passed in is not the one the history references".

    Entries whose key does not parse are dropped: a malformed key would
    otherwise poison the min and max for the whole run.
    """
    history = test_case.get("resultHistory")
    if not isinstance(history, dict):
        return [], set()

    stamps = []
    run_ids = set()
    for raw_stamp, entry in history.items():
        if not isinstance(entry, dict):
            continue
        run_ids.add(entry.get("runId"))
        if entry.get("runId") != test_run_id:
            continue
        parsed = parse_timestamp(raw_stamp)
        if parsed is not None:
            stamps.append(parsed)
    return stamps, run_ids


def summarise_executions(rows, test_run_id, include_daily_breakdown):
    """Reduce untrimmed result rows to this run's execution timing.

    `casesNeverExecuted` counts cases attached to the run that carry no history
    entry for it. Those are the cases a run inherited but nobody touched, and
    they are the reason a nominally complete run can still hide untested scope.

    When nothing matched but the histories do reference other runs, the summary
    carries `runIdMismatch` rather than a clean set of zeros. A zeroed summary
    reads as "nobody tested this run", which is a believable wrong answer; the
    likelier cause is an identifier the results endpoint accepted but the
    history does not compare equal to.
    """
    all_stamps = []
    cases_executed = 0
    never_executed_keys = []
    run_ids_seen = set()

    for row in rows:
        if not isinstance(row, dict):
            continue
        test_case = row.get("testCase")
        if not isinstance(test_case, dict):
            continue

        stamps, run_ids = executions_for_run(test_case, test_run_id)
        run_ids_seen |= run_ids
        if stamps:
            cases_executed += 1
            all_stamps.extend(stamps)
        else:
            never_executed_keys.append(test_case.get("key"))

    listed_keys = sorted(k for k in never_executed_keys if k)
    summary = {
        "casesInRun": cases_executed + len(never_executed_keys),
        "casesExecuted": cases_executed,
        "casesNeverExecuted": len(never_executed_keys),
        "neverExecutedKeys": listed_keys[:_MAX_LISTED_KEYS],
        "totalExecutionEvents": len(all_stamps),
        "firstExecutedAt": None,
        "lastExecutedAt": None,
        "executionSpanMinutes": None,
        "distinctExecutionDays": 0,
    }
    if len(listed_keys) > _MAX_LISTED_KEYS:
        summary["neverExecutedKeysTruncated"] = True

    if not all_stamps:
        other_ids = sorted(
            str(run_id) for run_id in run_ids_seen if run_id and run_id != test_run_id
        )
        if other_ids:
            summary["runIdMismatch"] = {
                "requested": test_run_id,
                "runIdsInHistory": other_ids[:_MAX_LISTED_KEYS],
            }
        return summary, None, None

    first = min(all_stamps)
    last = max(all_stamps)
    days = Counter(stamp.date().isoformat() for stamp in all_stamps)

    summary["firstExecutedAt"] = first.isoformat()
    summary["lastExecutedAt"] = last.isoformat()
    summary["executionSpanMinutes"] = span_minutes(first, last)
    summary["distinctExecutionDays"] = len(days)

    if include_daily_breakdown:
        summary["executionsByDay"] = dict(sorted(days.items()))

    return summary, first, last


def fetch_run(test_run_id, tenant_id, access_token):
    """Fetch the run object itself, or None when it is not retrievable.

    The results endpoint carries no run metadata, so createdAt and lockedAt
    have to come from here. Failure is tolerated rather than raised: the
    execution window is the point of this tool and it does not depend on the
    run object, so a missing one degrades the answer instead of killing it.
    """
    try:
        raw = tuskr_client.send(
            f"test-run/{test_run_id}",
            {},
            tuskr_client.RequestMethod.GET,
            ext_tenant_id=tenant_id,
            ext_access_token=access_token,
        )
        payload = json.loads(raw)
    except (TypeError, ValueError, OSError):
        return None

    run = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(run, dict):
        run = payload if isinstance(payload, dict) and "id" in payload else None
    if not isinstance(run, dict):
        return None

    return {field: run[field] for field in _RUN_FIELDS if field in run}


@mcp.tool
async def get_test_run_timeline(
    ctx: Context,
    test_run: str,
    include_daily_breakdown: bool = True,
):
    """
    Reports when testing in a test run actually started and finished.

    Use this instead of comparing a run's createdAt to its lockedAt. Those two
    bracket the run's administrative life, not its testing: a run is typically
    opened before anyone executes against it and locked well after the last
    result, so the gap between them can be twice the real duration.

    This reads the per-execution timestamps Tuskr keeps on each test case and
    keeps only those recorded against this run, giving the true first and last
    execution, the span between them, and how many distinct days saw activity.

    For a recent run, get_test_run_details is the cheaper way to get the first
    and last result times and the duration: one small call, where this tool
    fetches every results page untrimmed (100 cases per page). Use this tool
    when those timestamps come back null (Tuskr may not have recorded them for
    older results), or when you need the number of distinct days with activity,
    the daily breakdown, or the cases that were never executed.

    Args:
        test_run: ID of the test run. This is the UUID after /test-run/ in the
            Tuskr URL. The underlying endpoint addresses the run in the URL
            path, so a run name or R-key is not accepted; resolve one to its ID
            with list_test_runs first.
        include_daily_breakdown: if True (default), adds executionsByDay, a map
            of date to execution count. Useful for telling a run worked steadily
            over a week from one tested in an afternoon after sitting idle. Its
            size is bounded by the run's span, so it stays small. Days are
            bucketed by UTC date, so an evening session in a UTC+2 or later
            timezone can straddle two buckets and read as two days of activity.

    Returns a JSON object with firstExecutedAt, lastExecutedAt,
    executionSpanMinutes, distinctExecutionDays, totalExecutionEvents, and the
    case counts including casesNeverExecuted with up to 50 of their keys
    (neverExecutedKeysTruncated is set when the list was cut). When the run
    object is retrievable it also carries createdAt, lockedAt,
    createdToLockedMinutes, createdToFirstExecutionMinutes and
    lastExecutionToLockedMinutes, so the administrative and real durations can
    be compared; runMetadataAvailable says whether those are present.

    If no history entry references this run but the cases do carry entries for
    other runs, runIdMismatch is returned instead of a zeroed summary: that
    means the identifier is not the one the history records, not that the run
    went untested.
    """
    tenant_id, access_token = await credentials.resolve(ctx)

    def fetch_page(page_number):
        return tuskr_client.send(
            f"test-run/{test_run}/results",
            {"page": page_number},
            tuskr_client.RequestMethod.GET,
            ext_tenant_id=tenant_id,
            ext_access_token=access_token,
        )

    first_page = fetch_page(1)
    try:
        payload = json.loads(first_page)
    except (TypeError, ValueError):
        return first_page

    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return first_page

    rows = payload["data"]
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    for page_number in range(2, meta.get("pages", 1) + 1):
        try:
            more = json.loads(fetch_page(page_number))
        except (TypeError, ValueError):
            break
        rows.extend(more.get("data", []))

    summary, first, last = summarise_executions(
        rows,
        test_run,
        include_daily_breakdown,
    )

    result = {"testRunId": test_run, **summary}

    run = fetch_run(test_run, tenant_id, access_token)
    if run is None:
        result["runMetadataAvailable"] = False
        return json.dumps(result)

    created = parse_timestamp(run.get("createdAt"))
    locked = parse_timestamp(run.get("lockedAt"))

    result["runMetadataAvailable"] = True
    result["key"] = run.get("key")
    result["name"] = run.get("name")
    result["status"] = run.get("status")
    result["createdAt"] = run.get("createdAt")
    result["lockedAt"] = run.get("lockedAt")
    result["createdToLockedMinutes"] = span_minutes(created, locked)
    result["createdToFirstExecutionMinutes"] = span_minutes(created, first)
    result["lastExecutionToLockedMinutes"] = span_minutes(last, locked)

    return json.dumps(result)
