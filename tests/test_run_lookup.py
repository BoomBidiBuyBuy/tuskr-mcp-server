import json

import pytest

import tuskr_client
from tuskr_mcp.run_lookup import resolve_test_run

UUID = "258deaae-1c2d-4e3f-8a9b-0c1d2e3f4a5b"


def _page(rows, pages=1):
    return json.dumps({"rows": rows, "meta": {"pages": pages}})


def _run(run_id, key, name="Some run"):
    return {"id": run_id, "key": key, "name": name}


def _resolve(test_run, project="project-1"):
    return resolve_test_run(test_run, project, "tenant-1", "token-1")


class TestResolveTestRun:
    """Exact matching on top of Tuskr's contains-match filters."""

    def test_uuid_is_returned_without_a_request(self, send):
        assert _resolve(UUID) == UUID
        send.assert_not_called()

    def test_exact_key_wins_over_contains_matches(self, send):
        """R-1 also returns R-10 and R-100; only R-1 itself may be picked."""
        send.return_value = _page(
            [_run("id-10", "R-10"), _run("id-1", "R-1"), _run("id-100", "R-100")]
        )

        assert _resolve("R-1") == "id-1"

    def test_key_match_ignores_case(self, send):
        send.return_value = _page([_run("id-1", "R-1")])

        assert _resolve("r-1") == "id-1"

    def test_lookup_request_is_scoped_to_the_project(self, send):
        send.return_value = _page([_run("id-1", "R-1")])

        _resolve("R-1", project="project-9")

        send.assert_called_once_with(
            "test-run",
            {"page": 1, "filter[project]": "project-9", "filter[key]": "R-1"},
            tuskr_client.RequestMethod.GET,
            ext_tenant_id="tenant-1",
            ext_access_token="token-1",
        )

    def test_match_on_a_later_page_is_found(self, send):
        """The exact row can sit on any page of a contains-match result."""
        send.side_effect = [
            _page([_run("id-10", "R-10")], pages=2),
            _page([_run("id-1", "R-1")], pages=2),
        ]

        assert _resolve("R-1") == "id-1"
        assert [call[0][1]["page"] for call in send.call_args_list] == [1, 2]

    def test_name_is_used_when_no_key_matches(self, send):
        send.side_effect = [
            _page([_run("id-9", "R-9", name="Smoke")]),
            _page([_run("id-9", "R-9", name="Smoke")]),
        ]

        assert _resolve("Smoke") == "id-9"
        assert "filter[name]" in send.call_args_list[1][0][1]

    def test_name_match_is_exact(self, send):
        """A contains-only name match is not a match."""
        send.side_effect = [
            _page([]),
            _page([_run("id-9", "R-9", name="Smoke test nightly")]),
        ]

        with pytest.raises(ValueError, match="No test run"):
            _resolve("Smoke")

    def test_no_match_raises_naming_run_and_project(self, send):
        send.return_value = _page([])

        with pytest.raises(ValueError, match="R-404.*project-1"):
            _resolve("R-404")

    def test_several_matches_raise_and_list_the_ids(self, send):
        send.return_value = _page([_run("id-a", "R-1"), _run("id-b", "r-1")])

        with pytest.raises(ValueError, match="id-a, id-b"):
            _resolve("R-1")

    def test_error_body_is_not_read_as_no_match(self, send):
        send.return_value = "Forbidden"

        with pytest.raises(ValueError, match="unexpected response.*Forbidden"):
            _resolve("R-1")

    def test_json_without_rows_is_not_read_as_no_match(self, send):
        send.return_value = json.dumps({"error": "Unauthorized"})

        with pytest.raises(ValueError, match="unexpected response"):
            _resolve("R-1")
