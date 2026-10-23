"""
Step 6 - Inputs for the Arena version of the step-5 simulation.

Arena does not read our Python objects, so this script turns the same inputs SimPy uses
into the exact numbers and expressions to type into the Arena modules.

Inputs : data/processed/sim_order_sizes.csv, data/processed/sim_hourly_arrivals.csv (step 5)
         outputs/04_next_week_plan.csv, data/raw/staffing_parameters.csv,
         data/raw/simulation_parameters.csv
Outputs: arena/arena_inputs.csv  (name, value - one row per number used in Arena)

Arena clock: minutes, time 0 = 06:00 (same as SimPy).
"""
from pathlib import Path
import math
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "outputs"
(ROOT / "arena").mkdir(exist_ok=True)

sizes = pd.read_csv(PROC / "sim_order_sizes.csv").lines.values
arr = pd.read_csv(PROC / "sim_hourly_arrivals.csv")
P = pd.read_csv(RAW / "staffing_parameters.csv").set_index("parameter")["value"].astype(float)
S = pd.read_csv(RAW / "simulation_parameters.csv").set_index("parameter")["value"].astype(float)
day = pd.read_csv(OUT / "04_next_week_plan.csv").query("date == '2011-12-12'").iloc[0]

# 1. Daily total lines: lognormal through P10 and P90 (same as SimPy)
sigma = (math.log(day.p90) - math.log(day.p10)) / (2 * 1.2816)
mu = (math.log(day.p90) + math.log(day.p10)) / 2

# 2. Hourly arrival shares, Arena array index 1 = 06:00-07:00
share = pd.Series(0.0, index=range(6, 24))
share.loc[arr.hour] = arr.share.values
share = share / share.sum()
max_share = share.max()

# 3. Order size: real orders grouped into 17 bins, each bin's value = its mean size
edges = [1, 2, 3, 5, 9, 13, 17, 22, 28, 34, 41, 51, 61, 81, 121, 201, 401, 10_000]
cum, parts, check = 0.0, [], []
for a, b in zip(edges[:-1], edges[1:]):
    m = (sizes >= a) & (sizes < b)
    v = int(round(sizes[m].mean()))
    cum += m.mean()
    parts.append([cum, v])
    check.append((m.mean(), v))
parts[-1][0] = 1.0
size_expr = "DISC(" + ", ".join(f"{c:.4f}, {v}" for c, v in parts) + ")"
bin_mean = sum(p * v for p, v in check)

min_per_line = 60 / P["pick_rate"]
rows = [
    ("MU", round(mu, 5)), ("SIGMA", round(sigma, 5)),
    ("MeanOrderSize", round(sizes.mean(), 3)), ("MaxShare", round(max_share, 5)),
    ("TaskMaxLines", int(S["task_max_lines"])), ("SetupMin", S["task_setup_min"]),
    ("MinPerLine", min_per_line), ("PickTimeCV", S["pick_time_cv"]),
    ("OvertimeMaxMin", P["max_overtime_hours"] * 60), ("Replications", int(S["replications"])),
    ("RunLengthMin", 18 * 60),
] + [(f"HourShare({i})", round(v, 5)) for i, v in enumerate(share.values, start=1)]
pd.DataFrame(rows, columns=["name", "value"]).to_csv(ROOT / "arena" / "arena_inputs.csv", index=False)

print(f"Day: Mon 12 Dec 2011, P10 {day.p10:,.0f}  P50 {day.p50:,.0f}  P90 {day.p90:,.0f}")
print(f"\nDayLines expression : EXP(NORM({mu:.5f}, {sigma:.5f}))")
print(f"MeanOrderSize       : {sizes.mean():.3f}   MaxShare: {max_share:.5f}")
print(f"\nOrder size expression (mean {bin_mean:.2f} vs real {sizes.mean():.2f}):\n{size_expr}")
print(f"\nPick time expression: {S['task_setup_min']:g} + TaskLines * {min_per_line:g} * LOGN(1, {S['pick_time_cv']:g})")
print("\nHourShare values (index 1 = 06:00):")
print(", ".join(f"{v:.5f}" for v in share.values))
print("\nSaved arena/arena_inputs.csv")