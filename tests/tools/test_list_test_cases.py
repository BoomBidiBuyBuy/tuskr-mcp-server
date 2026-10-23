import tuskr_client
from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import list_test_cases as module


def _list_cases(ctx, **kwargs):
    return call_tool(module.list_test_cases, ctx, **kwargs)


class TestListTestCases:
    """Cover the test-case listing wrapper."""

    def test_project_and_default_page_are_always_sent(self, env, send):
        """A minimal call pins the project, asks for page 1, and sends nothing else."""
        _list_cases(FakeContext(), filter_project="7")

        action, params, method = send.call_args[0]
        assert action == "test-case"
        assert method == tuskr_client.RequestMethod.GET
        # Exact equality is the point: an unset filter must not reach Tuskr as
        # an empty query parameter.
        assert params == {"page": 1, "filter[project]": "7"}

    def test_page_is_forwarded(self, env, send):
        """Pagination is caller-controlled; the default is not hardcoded."""
        _list_cases(FakeContext(), filter_project="7", page=3)

        assert send.call_args[0][1]["page"] == 3

    def test_optional_filters_map_onto_tuskr_keys(self, env, send):
        """Every snake_case parameter becomes its camelCase filter key."""
        _list_cases(
            FakeContext(),
            filter_project="7",
            filter_test_suite="TS-1",
            filter_test_suite_section="Checkout",
            filter_key="C-2",
            filter_name="pagination",
        )

        params = send.call_args[0][1]
        assert params["filter[testSuite]"] == "TS-1"
        assert params["filter[testSuiteSection]"] == "Checkout"
        assert params["filter[key]"] == "C-2"
        assert params["filter[name]"] == "pagination"

    def test_test_case_type_maps_onto_tuskr_key(self, env, send):
        """filter_test_case_type becomes filter[testCaseType], value untouched."""
        _list_cases(
            FakeContext(),
            filter_project="7",
            filter_test_case_type="type-id-1",
        )

        params = send.call_args[0][1]
        assert params == {
            "page": 1,
            "filter[project]": "7",
            "filter[testCaseType]": "type-id-1",
        }

    def test_empty_test_case_type_sends_nothing(self, env, send):
        """An empty string carries no more information than an absent filter."""
        _list_cases(FakeContext(), filter_project="7", filter_test_case_type="")

        assert send.call_args[0][1] == {"page": 1, "filter[project]": "7"}

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        """Middleware sets state to None in stdio mode, so env vars are used."""
        _list_cases(
            FakeContext({"ext_tenant_id": None, "ext_access_token": None}),
            filter_project="7",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        """Values from HTTP headers take precedence over the environment."""
        _list_cases(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            ),
            filter_project="7",
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"


class TestListTestCasesCustomFieldFilter:
    """Cover the custom-field filter encoding.

    Tuskr expects one flattened bracket key per field. A previous attempt sent
    the whole mapping JSON-encoded under a single filter[customFields] key and
    Tuskr ignored it silently, returning every case in the project, so these
    tests pin the encoding rather than merely that something was sent.
    """

    def test_single_custom_field_is_flattened(self, env, send):
        _list_cases(
            FakeContext(),
            filter_project="7",
            filter_custom_fields={"can_be_automated": "option-id-yes"},
        )

        params = send.call_args[0][1]
        assert params["filter[customFields][can_be_automated]"] == "option-id-yes"

    def test_each_field_gets_its_own_key(self, env, send):
        """Several fields must not collapse into one parameter."""
        _list_cases(
            FakeContext(),
            filter_project="7",
            filter_custom_fields={
                "can_be_automated": "option-id-no",
                "review_state": "option-id-pending",
            },
        )

        params = send.call_args[0][1]
        assert params["filter[customFields][can_be_automated]"] == "option-id-no"
        assert params["filter[customFields][review_state]"] == "option-id-pending"

    def test_no_json_encoded_blob_is_sent(self, env, send):
        """The shape Tuskr silently ignored must never reappear."""
        _list_cases(
            FakeContext(),
            filter_project="7",
            filter_custom_fields={"can_be_automated": "option-id-yes"},
        )

        assert "filter[customFields]" not in send.call_args[0][1]

    def test_unset_filter_sends_nothing(self, env, send):
        _list_cases(FakeContext(), filter_project="7")

        assert send.call_args[0][1] == {"page": 1, "filter[project]": "7"}

    def test_empty_mapping_sends_nothing(self, env, send):
        """An empty dict carries no more information than an absent one."""
        _list_cases(FakeContext(), filter_project="7", filter_custom_fields={})

        assert send.call_args[0][1] == {"page": 1, "filter[project]": "7"}

    def test_coexists_with_the_other_filters(self, env, send):
        """A custom-field filter narrows alongside the built-in filters."""
        _list_cases(
            FakeContext(),
            filter_project="7",
            filter_test_suite="TS-1",
            filter_name="pagination",
            filter_custom_fields={"can_be_automated": "option-id-yes"},
        )

        params = send.call_args[0][1]
        assert params["filter[testSuite]"] == "TS-1"
        assert params["filter[name]"] == "pagination"
        assert params["filter[customFields][can_be_automated]"] == "option-id-yes"

    def test_non_string_values_keep_their_type(self, env, send):
        """Numeric and multi-select values are not coerced to str.

        A tenant's field set is its own: numeric and multi-select fields have to
        be expressible, not just the dropdown IDs this was first written for.
        Booleans are deliberately not covered here — see
        test_checkbox_fields_use_lowercase_string_not_bool below.
        """
        _list_cases(
            FakeContext(),
            filter_project="7",
            filter_custom_fields={
                "sprint_number": 14,
                "platforms": ["option-id-linux", "option-id-windows"],
            },
        )

        params = send.call_args[0][1]
        assert params["filter[customFields][sprint_number]"] == 14
        assert params["filter[customFields][platforms]"] == [
            "option-id-linux",
            "option-id-windows",
        ]

    def test_checkbox_fields_use_lowercase_string_not_bool(self, env, send):
        """A bool is normalised to the lowercase string Tuskr matches on.

        Live-verified: Tuskr matches the literal text it receives for a checkbox
        field, and requests renders a Python bool via str() as 'True'. Sending
        'True' returned 1369 of 1918 rows, most of them false — a plausible but
        wrong result rather than an error. 'true' returned exactly the 7 true
        rows out of a 38-row sample. Callers pass whichever form is natural and
        the tool sends the one that works.
        """
        _list_cases(
            FakeContext(),
            filter_project="7",
            filter_custom_fields={"is_automated": True, "is_manual": False},
        )

        params = send.call_args[0][1]
        assert params["filter[customFields][is_automated]"] == "true"
        assert params["filter[customFields][is_manual]"] == "false"

    def test_lowercase_string_form_is_passed_through(self, env, send):
        """A caller who already knows the wire format is not second-guessed."""
        _list_cases(
            FakeContext(),
            filter_project="7",
            filter_custom_fields={"is_automated": "true"},
        )

        assert send.call_args[0][1]["filter[customFields][is_automated]"] == "true"

    def test_integer_values_are_not_treated_as_booleans(self, env, send):
        """bool is a subclass of int, so the order of the checks matters.

        A numeric field set to 0 or 1 must stay numeric rather than being
        rewritten to 'false'/'true'.
        """
        _list_cases(
            FakeContext(),
            filter_project="7",
            filter_custom_fields={"retry_count": 1, "defect_count": 0},
        )

        params = send.call_args[0][1]
        assert params["filter[customFields][retry_count]"] == 1
        assert params["filter[customFields][defect_count]"] == 0
