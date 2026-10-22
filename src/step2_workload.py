"""
Step 2 - Daily and hourly warehouse workload.
Inputs : data/processed/order_lines.parquet (step 1), data/raw/uk_bank_holidays.csv
Outputs: data/processed/daily_workload.csv   one row per calendar day (open or closed)
         outputs/02_hourly_profile.csv       avg orders and lines per hour, by weekday (for Arena)
         outputs/02_daily_workload.png       daily pick lines over time
         outputs/02_profiles.png             weekday and hour-of-day pattern
Workload = pick lines (one product line on an order = one pick). Also orders, units, SKUs.
"""
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt

# --- Block 1: paths + data -----------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "outputs"
d = pd.read_parquet(PROC / "order_lines.parquet")
hol = pd.read_csv(RAW / "uk_bank_holidays.csv", parse_dates=["date"])

# The last day (9 Dec 2011) stops at 12:50, so it is a partial day: drop it
last = d.invoice_date.dt.normalize().max()
d = d[d.invoice_date < last]
d["date"] = d.invoice_date.dt.normalize()

# --- Block 2: one row per calendar day -----------------------------------
day = d.groupby("date").agg(orders=("invoice", "nunique"), lines=("invoice", "size"),
                            units=("quantity", "sum"), skus=("stock_code", "nunique"),
                            value=("line_value", "sum"))
cal = pd.DataFrame(index=pd.date_range(day.index.min(), day.index.max(), name="date"))
day = cal.join(day).fillna(0)
day[["orders", "lines", "units", "skus"]] = day[["orders", "lines", "units", "skus"]].astype(int)
day["is_open"] = (day.lines > 0).astype(int)

# --- Block 3: closure rule (so future days can be marked open/closed) ----
# Observed: closed Saturdays, UK bank holidays, Easter Sunday, and 24 Dec - 3 Jan.
idx = day.index
easter_sun = hol[hol.holiday == "Good Friday"].date + pd.Timedelta(days=2)
day["is_bank_holiday"] = idx.isin(hol.date).astype(int)
day["xmas_shutdown"] = (((idx.month == 12) & (idx.day >= 24)) | ((idx.month == 1) & (idx.day <= 3))).astype(int)
day["rule_closed"] = ((idx.dayofweek == 5) | day.is_bank_holiday.astype(bool)
                      | idx.isin(easter_sun) | day.xmas_shutdown.astype(bool)).astype(int)
agree = (day.rule_closed == 1 - day.is_open)
print(f"Closure rule matches the data on {agree.sum()} of {len(day)} days")
print("Days where the rule is wrong:")
print(day.loc[~agree, ["lines", "is_open", "rule_closed"]].to_string(), "\n")

day["dow"] = idx.dayofweek          # 0 = Monday
day.reset_index().to_csv(PROC / "daily_workload.csv", index=False, date_format="%Y-%m-%d")

op = day[day.is_open == 1]
print(f"Open days: {len(op)} | closed: {len(day) - len(op)}")
print(op[["orders", "lines", "units", "skus"]].describe().round(0).loc[["mean", "min", "50%", "max"]].to_string())
print(f"\nLines per order: {op.lines.sum() / op.orders.sum():.1f}")
print("\nAvg pick lines by weekday (open days):")
print(op.groupby(op.index.day_name()).lines.agg(["mean", "count"]).round(0)
      .reindex(["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]).dropna().to_string())
print("\nAvg pick lines by month:")
print(op.groupby(op.index.to_period("M")).lines.mean().round(0).to_string())

# --- Block 4: hourly arrival profile (input for the Arena model) ----------
d["dow"], d["hour"] = d.invoice_date.dt.dayofweek, d.invoice_date.dt.hour
open_days = op.groupby("dow").size()                              # open days per weekday
hp = d.groupby(["dow", "hour"]).agg(orders=("invoice", "nunique"), lines=("invoice", "size")).reset_index()
hp = hp[hp.dow != 5]                                              # one odd Saturday
hp["avg_orders"] = hp.orders / hp.dow.map(open_days)
hp["avg_lines"] = hp.lines / hp.dow.map(open_days)
hp[["dow", "hour", "avg_orders", "avg_lines"]].round(2).to_csv(OUT / "02_hourly_profile.csv", index=False)
hp_all = hp.groupby("hour")[["orders", "lines"]].sum()
print("\nShare of daily lines by hour:")
print((100 * hp_all.lines / hp_all.lines.sum()).round(1).to_string())

# --- Block 5: charts -----------------------------------------------------
NAVY, BLUE, GOLD = "#14213D", "#118DFF", "#E9A23B"
fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(op.index, op.lines, color=BLUE, lw=0.8, label="Pick lines per open day")
ax.plot(op.lines.rolling(28, min_periods=10).mean(), color=NAVY, lw=2, label="28-open-day average")
ax.set_ylabel("Pick lines"); ax.legend(loc="upper left")
ax.set_title("Daily warehouse workload, Dec 2009 - Dec 2011: autumn peak every year", loc="left")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "02_daily_workload.png", dpi=150)

fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 3.8))
wk = op.groupby("dow").lines.mean().reindex([6, 0, 1, 2, 3, 4])
a1.bar(["Sun", "Mon", "Tue", "Wed", "Thu", "Fri"], wk.values, color=BLUE)
a1.set_title("Avg pick lines by weekday (closed Saturdays)", loc="left", fontsize=10)
a2.bar(hp_all.index, 100 * hp_all.lines / hp_all.lines.sum(), color=GOLD)
a2.set_title("Share of daily pick lines by hour of order", loc="left", fontsize=10)
a2.set_xlabel("Hour"); a2.set_ylabel("%")
for a in (a1, a2):
    a.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "02_profiles.png", dpi=150)
print("\nSaved data/processed/daily_workload.csv, outputs/02_hourly_profile.csv, "
      "outputs/02_daily_workload.png, outputs/02_profiles.png")