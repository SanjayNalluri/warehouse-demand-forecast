"""Feature code: no look-ahead, and the closure rule."""
import numpy as np
import pandas as pd
from features import build_features, extend_calendar, is_closed, FEATURES, HORIZON


def test_no_lookahead(daily):
    """Changing the last 7 days' lines must not change the features of those days."""
    base = build_features(daily)
    changed = daily.copy()
    last7 = changed.date > changed.date.max() - pd.Timedelta(days=HORIZON)
    changed.loc[last7, "lines"] = changed.loc[last7, "lines"] * 10 + 999
    after = build_features(changed)
    rows = base.date > base.date.max() - pd.Timedelta(days=HORIZON)
    pd.testing.assert_frame_equal(base.loc[rows, FEATURES], after.loc[rows, FEATURES])


def test_closure_rule_matches_history(daily):
    """Rule says closed on every day the warehouse had no orders (one odd Saturday excepted)."""
    closed = is_closed(pd.DatetimeIndex(daily.date))
    wrong = daily[closed == (daily.is_open == 1)]
    assert list(wrong.date.dt.strftime("%Y-%m-%d")) == ["2009-12-05"]


def test_known_closed_days():
    days = pd.DatetimeIndex(["2011-12-10", "2011-12-25", "2012-01-02", "2011-04-29", "2011-12-12"])
    assert list(is_closed(days)) == [True, True, True, True, False]   # Sat, Xmas, shutdown, royal wedding, Mon


def test_extend_calendar_adds_horizon_days(daily):
    cal = extend_calendar(daily)
    assert len(cal) == len(daily) + HORIZON
    assert cal.lines.tail(HORIZON).isna().all()
    assert np.isfinite(build_features(cal).tail(HORIZON).loc[lambda d: d.is_open == 1, "open_mean_28"]).all()