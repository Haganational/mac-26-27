import pytest


@pytest.fixture(autouse=True)
def _den_ledger_in_tmp(tmp_path_factory, monkeypatch):
    """Builds under test must never write the Den desk ledger into the repo's data/den/desk/."""
    from mac import den_connect
    monkeypatch.setattr(den_connect, "LEDGER_DIR", tmp_path_factory.mktemp("den-desk"))


@pytest.fixture(autouse=True)
def _tops_ledger_in_tmp(tmp_path_factory, monkeypatch):
    """Builds under test must never lock or grade a Tops and Bottoms card in the repo's data/tops/."""
    from mac import tops
    monkeypatch.setattr(tops, "TOPS_DIR", tmp_path_factory.mktemp("tops"))
    monkeypatch.setattr(tops, "data_dirs", lambda: [])  # and never read the real schedules (tests pass their own)
