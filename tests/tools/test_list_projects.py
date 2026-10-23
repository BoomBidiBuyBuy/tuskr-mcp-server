import tuskr_client
from tests.helpers import FakeContext, call_tool
from tuskr_mcp.tools import list_projects as module


def _list_projects(ctx, **kwargs):
    return call_tool(module.list_projects, ctx, **kwargs)


class TestListProjects:
    """Cover the project listing wrapper."""

    def test_default_page_is_sent_and_nothing_else(self, env, send):
        """A minimal call asks for page 1 and sends no filters at all."""
        _list_projects(FakeContext())

        action, params, method = send.call_args[0]
        assert action == "project"
        assert method == tuskr_client.RequestMethod.GET
        # Exact equality is the point: an unset filter must not reach Tuskr as
        # an empty query parameter.
        assert params == {"page": 1}

    def test_page_is_forwarded(self, env, send):
        """Pagination is caller-controlled; the default is not hardcoded."""
        _list_projects(FakeContext(), page=2)

        assert send.call_args[0][1]["page"] == 2

    def test_optional_filters_map_onto_tuskr_keys(self, env, send):
        """Every snake_case parameter becomes its bracketed filter key."""
        _list_projects(FakeContext(), filter_name="Regression", filter_status="active")

        params = send.call_args[0][1]
        assert params["filter[name]"] == "Regression"
        assert params["filter[status]"] == "active"

    def test_blank_filters_are_omitted(self, env, send):
        """An empty string is an absent filter, not a filter on empty."""
        _list_projects(FakeContext(), filter_name="", filter_status="")

        assert set(send.call_args[0][1]) == {"page"}

    def test_falls_back_to_env_vars_in_stdio_mode(self, env, send):
        """Middleware sets state to None in stdio mode, so env vars are used."""
        _list_projects(FakeContext({"ext_tenant_id": None, "ext_access_token": None}))

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-env"
        assert kwargs["ext_access_token"] == "token-from-env"

    def test_header_state_beats_env_vars(self, env, send):
        """Values from HTTP headers take precedence over the environment."""
        _list_projects(
            FakeContext(
                {
                    "ext_tenant_id": "tenant-from-header",
                    "ext_access_token": "token-from-header",
                }
            )
        )

        kwargs = send.call_args[1]
        assert kwargs["ext_tenant_id"] == "tenant-from-header"
        assert kwargs["ext_access_token"] == "token-from-header"

    def test_deprecated_account_id_env_var_still_resolves(self, monkeypatch, send):
        """TUSKR_ACCOUNT_ID remains a working fallback after the tenant rename."""
        monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
        monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-legacy")
        monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")

        _list_projects(FakeContext())

        assert send.call_args[1]["ext_tenant_id"] == "tenant-legacy"
