from datetime import date

from mac import backtest as B
from mac import model as M


def _row(d, model_margin, home_spread, margin):
    return {"date": d, "proj": {"margin": model_margin, "total": 140.0},
            "line": {"home_spread": home_spread, "total": 140.0},
            "pts_h": 70 + margin, "pts_a": 70}


def test_blend_weight_near_zero_when_model_adds_nothing():
    # Results equal the market every time, whatever the model says.
    rows = [_row(date(2026, 1, 1 + i % 28), (i % 7) - 3.0, -2.0, 2) for i in range(800)]
    out = B.blend_study(rows, "spread")
    assert out["games"] == 800
    assert out["w_final"] == 0.0
    assert out["publish_edges"] is False


def test_blend_weight_positive_when_model_is_right():
    # Results follow the model exactly, so its disagreements carry the signal.
    rows = [_row(date(2026, 1, 1 + i % 28), float((i % 9) - 4), 0.0, (i % 9) - 4) for i in range(800)]
    out = B.blend_study(rows, "spread")
    assert out["w_final"] > 0.7
    assert out["blend_mae"] < out["market_mae"]


def test_edges_unproven_without_backtest(monkeypatch, tmp_path):
    monkeypatch.setattr(M, "MODEL_DIR", tmp_path)
    assert M.edges_proven("spread") is False
    assert M.total_side(150.0, 140.0)["flag"] is False
