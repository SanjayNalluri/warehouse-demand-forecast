"""
Shared feature code: used by training (step 3) and by the API, so both build
features the same way.

Rule: every feature for day t uses only data from day t-7 or earlier, so one
model can forecast any of the next 7 days from the last known day.
"""
from pathlib import Path
import numpy as np
import pandas as pd

HORIZON = 7          # days ahead the model can forecast
FEATURES = [
    "dow", "month", "week_of_year", "days_to_xmas", "after_closure",
    "lag_7", "same_dow_mean_4", "open_mean_28", "open_mean_7_to_14", "trend_28_vs_91",
    "lag_364", "last_year_mean_28", "yoy_growth", "expected_level",
]

ROOT = Path(__file__).resolve().parents[1]
HOLIDAYS = pd.read_csv(ROOT / "data" / "raw" / "uk_bank_holidays.csv", parse_dates=["date"])


def is_closed(dates: pd.DatetimeIndex) -> np.ndarray:
    """Closure rule from step 2: Saturday, bank holiday, Easter Sunday, 24 Dec - 3 Jan."""
    easter_sun = HOLIDAYS[HOLIDAYS.holiday == "Good Friday"].date + pd.Timedelta(days=2)
    xmas = ((dates.month == 12) & (dates.day >= 24)) | ((dates.month == 1) & (dates.day <= 3))
    return np.asarray((dates.dayofweek == 5) | dates.isin(HOLIDAYS.date) | dates.isin(easter_sun) | xmas)


def extend_calendar(daily: pd.DataFrame, horizon: int = HORIZON) -> pd.DataFrame:
    """Add the next `horizon` calendar days (lines unknown) using the closure rule."""
    last = daily.date.max()
    future = pd.DataFrame({"date": pd.date_range(last + pd.Timedelta(days=1), periods=horizon)})
    future["is_open"] = (~is_closed(pd.DatetimeIndex(future.date))).astype(int)
    future["lines"] = np.nan
    return pd.concat([daily[["date", "is_open", "lines"]], future], ignore_index=True)


def build_features(daily: pd.DataFrame) -> pd.DataFrame:
    """daily: one row per calendar day with date, is_open, lines (NaN for future days)."""
    d = daily.sort_values("date").set_index("date").copy()
    y = d.lines.where(d.is_open == 1)                       # closed days -> NaN, not 0
    idx = d.index

    # calendar
    d["dow"] = idx.dayofweek
    d["month"] = idx.month
    d["week_of_year"] = idx.isocalendar().week.astype(int).values
    xmas = pd.to_datetime([f"{y_}-12-24" for y_ in idx.year])
    d["days_to_xmas"] = np.where(idx <= xmas, (xmas - idx).days, 400)   # 400 = after Christmas
    # first open day after 1+ closed days (excluding the normal Saturday) gets catch-up orders
    closed_before = pd.Series(d.is_open.values, idx).shift(1).eq(0) & (idx.dayofweek != 6)
    d["after_closure"] = closed_before.astype(int).values

    # history, all shifted by 7+ days
    s7 = y.shift(7)
    d["lag_7"] = s7                                          # same weekday last week
    d["same_dow_mean_4"] = pd.concat([y.shift(k) for k in (7, 14, 21, 28)], axis=1).mean(axis=1)
    d["open_mean_28"] = s7.rolling(28, min_periods=10).mean()        # open days in t-34..t-7
    d["open_mean_7_to_14"] = s7.rolling(7, min_periods=3).mean()
    d["trend_28_vs_91"] = d.open_mean_28 / s7.rolling(91, min_periods=40).mean()
    d["lag_364"] = y.shift(364)                              # same weekday last year
    d["last_year_mean_28"] = y.shift(350).rolling(28, min_periods=10).mean()   # t-377..t-350, around last year
    # year-on-year: recent level vs the same weeks last year, applied to last year's
    # level around day t -> captures the seasonal ramp-up before it shows in recent data
    d["yoy_growth"] = d.open_mean_28 / y.shift(371).rolling(28, min_periods=10).mean()
    d["expected_level"] = (d.last_year_mean_28 * d.yoy_growth).fillna(d.open_mean_28)
    return d.reset_index()