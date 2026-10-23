"""Unit tests for UserTokenHandler's header extraction.

The end-to-end path, with fastmcp's real Context and HTTP stack, is covered in
test_server_integration.py.
"""

import asyncio
import logging
from types import SimpleNamespace

import pytest

from tuskr_mcp.middleware import UserTokenHandler


class _FakeFastMCPContext:
    """Records state writes; set_state is async, as on the real Context."""

    def __init__(self, headers=None):
        if headers is None:
            # Stdio mode: there is no HTTP request to read headers from.
            self.request_context = SimpleNamespace(request=None)
        else:
            self.request_context = SimpleNamespace(
                request=SimpleNamespace(headers=headers)
            )
        self.state = {}

    async def set_state(self, key, value):
        self.state[key] = value


def _apply(headers=None):
    fastmcp_context = _FakeFastMCPContext(headers)
    context = SimpleNamespace(fastmcp_context=fastmcp_context)
    asyncio.run(UserTokenHandler().retrieve_and_apply_token(context))
    return fastmcp_context.state


def test_stdio_mode_sets_both_values_to_none():
    assert _apply() == {"ext_access_token": None, "ext_tenant_id": None}


def test_bearer_token_and_tenant_header_are_stored():
    state = _apply({"Authorization": "Bearer abc", "Tenant-ID": " tenant-1 "})

    assert state == {"ext_access_token": "abc", "ext_tenant_id": "tenant-1"}


def test_missing_headers_store_none():
    assert _apply({}) == {"ext_access_token": None, "ext_tenant_id": None}


def test_non_bearer_authorization_is_ignored():
    assert _apply({"Authorization": "Basic abc"})["ext_access_token"] is None


def test_empty_bearer_token_raises():
    with pytest.raises(ValueError, match="Empty Bearer token"):
        _apply({"Authorization": "Bearer   "})


def test_legacy_account_id_header_is_used_with_a_warning():
    with pytest.warns(DeprecationWarning, match="Account-ID"):
        state = _apply({"Account-ID": "tenant-old"})

    assert state["ext_tenant_id"] == "tenant-old"


def test_tenant_id_header_wins_over_account_id(recwarn):
    state = _apply({"Tenant-ID": "tenant-new", "Account-ID": "tenant-old"})

    assert state["ext_tenant_id"] == "tenant-new"
    assert not any(issubclass(w.category, DeprecationWarning) for w in recwarn.list)


def test_bearer_token_is_never_logged(caplog):
    with caplog.at_level(logging.DEBUG):
        state = _apply({"Authorization": "Bearer secret-token"})

    assert state["ext_access_token"] == "secret-token"
    assert "secret-token" not in caplog.text
