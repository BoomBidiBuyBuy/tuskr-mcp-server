import asyncio
import inspect

from fastmcp import Context

from tests.helpers import FakeContext
from tuskr_mcp import credentials


def _resolve(state=None):
    return asyncio.run(credentials.resolve(FakeContext(state)))


def test_real_context_state_access_is_async():
    # The middleware and credentials.resolve await these, and FakeContext
    # mirrors them. If fastmcp ever changes this back, every tool call breaks.
    assert inspect.iscoroutinefunction(Context.get_state)
    assert inspect.iscoroutinefunction(Context.set_state)


def test_header_values_win_over_env(env):
    state = {"ext_tenant_id": "tenant-header", "ext_access_token": "token-header"}

    assert _resolve(state) == ("tenant-header", "token-header")


def test_env_is_the_fallback(env):
    assert _resolve() == ("tenant-from-env", "token-from-env")


def test_legacy_tenant_env_var_is_used_when_the_new_one_is_unset(monkeypatch):
    monkeypatch.delenv("TUSKR_TENANT_ID", raising=False)
    monkeypatch.setenv("TUSKR_ACCOUNT_ID", "tenant-old")
    monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token")

    assert _resolve() == ("tenant-old", "token")


def test_nothing_set_resolves_to_none(monkeypatch):
    for name in ("TUSKR_TENANT_ID", "TUSKR_ACCOUNT_ID", "TUSKR_ACCESS_TOKEN"):
        monkeypatch.delenv(name, raising=False)

    assert _resolve() == (None, None)
