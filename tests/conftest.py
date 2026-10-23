import sys
from pathlib import Path

import pytest

# src/main.py and the tuskr_mcp package import `tuskr_client` as a top-level
# module, so src/ has to be importable in its own right. Doing it here keeps the
# test modules free of import-order workarounds.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def env(monkeypatch):
    """Credentials present in the environment, none in HTTP headers."""
    monkeypatch.delenv("TUSKR_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("TUSKR_TENANT_ID", "tenant-from-env")
    monkeypatch.setenv("TUSKR_ACCESS_TOKEN", "token-from-env")


@pytest.fixture
def send(mocker):
    """Patch the single shared tuskr_client.send every tool module calls."""
    import tuskr_client

    return mocker.patch.object(tuskr_client, "send", return_value="{}")
