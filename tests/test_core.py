"""Assert-based checks. No framework. Run: python3 tests/test_core.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import date
import numpy as np, pandas as pd
import common, features as F
from common import parse_dmy, parse_num, PANEL


def test_parsers():
    assert parse_dmy("13/07/2024") == date(2024, 7, 13)
    assert parse_dmy("") is None and parse_dmy(None) is None
    assert parse_dmy("garbage") is None
    assert parse_num("1,234.5") == 1234.5
    assert parse_num("") is None, "empty must be None, NEVER 0.0"
    assert parse_num(None) is None, "missing cost is not free"
    print("  parsers OK")


def test_panel():
    d = pd.read_parquet(PANEL)
    assert len(d) == 18601, len(d)
    assert d.pid.nunique() == 2243
    assert d.month.nunique() == 13
    assert (d.month == "2026-04").sum() == 1981, "must match the PS's own figure"
    print("  panel counts OK")


def test_linter_catches_future():
    assert F.assert_no_leakage()

    @F.feature(reads="t+1..t+3")
    def _cheat(w): return 1.0
    try:
        F.assert_no_leakage()
        raise AssertionError("linter did NOT catch a future-reading feature")
    except F.LeakageError:
        pass
    finally:
        F.REGISTRY.pop("_cheat")
    assert F.assert_no_leakage()
    print("  leakage linter OK (both directions)")


def test_window_cannot_see_future():
    arr = {"t": np.array([date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]),
           "x": np.array([1.0, 2.0, 3.0])}
    w = F.Window(arr, 1)
    assert w.at("x") == 2.0
    assert w.lag("x", 1) == 1.0
    assert np.isnan(w.lag("x", 5)), "out-of-range lag must be NaN, not a wrap-around"
    assert list(w.history("x")) == [1.0, 2.0], "history must stop at t"
    assert 3.0 not in list(w.history("x")), "WINDOW LEAKED THE FUTURE"
    print("  Window truncation OK")


def test_no_silent_zero_labels():
    d = pd.read_parquet(PANEL).head(400)
    for c in ["t", "sanction_date", "original_end_date", "revised_date"]:
        d[c] = pd.to_datetime(d[c]).dt.date
    lab = F.label_windows(d)
    singles = d.groupby("pid").filter(lambda g: len(g) == 1)
    for _, r in singles.iterrows():
        assert lab[(r.pid, r.month)] == (None, None), "single-obs project must have NO label"
    print("  unlabelable rows dropped, not zero-filled")


def test_time_split_integrity():
    d = pd.read_parquet(PANEL)
    tr = set(d[d.month < "2026-04"].month)
    te = set(d[d.month >= "2026-04"].month)
    assert not tr & te, "train and test months overlap"
    assert max(tr) < min(te), "split is not forward in time"
    print("  time split OK")


if __name__ == "__main__":
    for fn in [test_parsers, test_panel, test_linter_catches_future,
               test_window_cannot_see_future, test_no_silent_zero_labels,
               test_time_split_integrity]:
        fn()
    print("\nall tests PASS")
