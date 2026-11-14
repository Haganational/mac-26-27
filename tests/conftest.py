import pytest


@pytest.fixture(autouse=True)
def _den_ledger_in_tmp(tmp_path_factory, monkeypatch):
    """Builds under test must never write the Den desk ledger into the repo's data/den/desk/."""
    from mac import den_connect
    monkeypatch.setattr(den_connect, "LEDGER_DIR", tmp_path_factory.mktemp("den-desk"))
