import json
from datetime import datetime, timezone

from mac import oddsboard, projlog, tops


def test_append_writes_daily_file_and_reads_archive_first(tmp_path):
    m = tmp_path / "model"; m.mkdir()
    (m / "projections.jsonl").write_text(json.dumps({"game_id": "1", "generated_at": "2026-11-20T10:00:00+00:00", "v": "old"}) + "\n")
    now = datetime(2026, 11, 24, 3, 30, tzinfo=timezone.utc)
    p = projlog.append(m, [{"game_id": "1", "generated_at": now.isoformat(timespec="seconds"), "v": "new"}], now)
    assert p == m / "projections" / "2026-11-24.jsonl"
    assert [f.name for f in projlog.files(m)] == ["projections.jsonl", "2026-11-24.jsonl"]
    assert oddsboard.load_projections(m)["1"]["v"] == "new"
    # the archive is never written again
    assert "new" not in (m / "projections.jsonl").read_text()


def test_append_uses_utc_day(tmp_path):
    from zoneinfo import ZoneInfo
    now = datetime(2026, 11, 23, 22, 30, tzinfo=ZoneInfo("America/New_York"))  # 03:30 UTC next day
    assert projlog.append(tmp_path, [{"a": 1}], now).name == "2026-11-24.jsonl"


def test_tops_reads_daily_files(tmp_path):
    d = tmp_path / "lg"; (d / "model").mkdir(parents=True)
    now = datetime(2026, 11, 24, 12, 0, tzinfo=timezone.utc)
    row = {"game_id": "9", "tip": "2026-11-24T23:00Z", "generated_at": "2026-11-24T11:00:00+00:00"}
    projlog.append(d / "model", [row], now)
    assert tops.load_projections([d], "2026-11-24", now)["9"]["game_id"] == "9"
