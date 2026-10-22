"""
Step 5 - Hour-by-hour picking simulation (SimPy): which shift pattern works?

Step 4 sets pickers per DAY. But orders arrive through the day (peak 12-1 PM, almost none
after 6 PM), so the timing of shifts matters too. This discrete-event simulation replays a
busy forecast day many times and compares shift patterns and crew sizes.

Inputs : data/processed/order_lines.parquet (step 1) -> saved as small CSVs the first time:
           data/processed/sim_order_sizes.csv     lines per order, Sep - Dec 2011 (7,346 orders)
           data/processed/sim_hourly_arrivals.csv share of orders arriving in each hour
         outputs/04_next_week_plan.csv (forecast for Mon 12 Dec 2011)
         data/raw/staffing_parameters.csv, data/raw/simulation_parameters.csv
Outputs: outputs/05_simulation_scenarios.csv, outputs/05_simulation.png
Needs  : pip install simpy

Model (one day = one replication):
  1. Total pick lines for the day ~ forecast, with the same uncertainty as the
     model's 80% range (lognormal through P10 and P90).
  2. Orders arrive as a Poisson process whose rate follows the hourly profile;
     each order's size is drawn from real orders (Sep - Dec 2011).
  3. Orders over 40 lines are split into pick tasks of at most 40 lines (one cart).
  4. Pickers take tasks first-come-first-served during their shift, with breaks.
     If work is left at shift end they stay up to 2 h (overtime); anything left
     after that is picked the next day (late).
"""
from pathlib import Path
import math
import numpy as np
import pandas as pd
import simpy
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RAW, PROC, OUT = ROOT / "data" / "raw", ROOT / "data" / "processed", ROOT / "outputs"

# --- Block 1: inputs ------------------------------------------------------
sizes_csv, arr_csv = PROC / "sim_order_sizes.csv", PROC / "sim_hourly_arrivals.csv"
if not sizes_csv.exists() or not arr_csv.exists():
    d = pd.read_parquet(PROC / "order_lines.parquet")
    o = d.groupby("invoice").agg(t=("invoice_date", "min"), lines=("stock_code", "size"))
    o = o[o.t < "2011-12-09"]
    o[o.t >= "2011-09-01"][["lines"]].to_csv(sizes_csv, index=False)
    h = o.groupby(o.t.dt.hour).size()
    pd.DataFrame({"hour": h.index, "share": (h / h.sum()).round(5)}).to_csv(arr_csv, index=False)

SIZES = pd.read_csv(sizes_csv).lines.values
ARR = pd.read_csv(arr_csv).set_index("hour")["share"]
P = pd.read_csv(RAW / "staffing_parameters.csv").set_index("parameter")["value"].astype(float)
S = pd.read_csv(RAW / "simulation_parameters.csv").set_index("parameter")["value"].astype(float)
plan = pd.read_csv(OUT / "04_next_week_plan.csv", parse_dates=["date"])
day = plan[plan.date == "2011-12-12"].iloc[0]                    # Monday: busiest weekday
P50, P10, P90 = day.p50, day.p10, day.p90
SIGMA = (math.log(P90) - math.log(P10)) / (2 * 1.2816)            # lognormal through P10 and P90
MU = (math.log(P90) + math.log(P10)) / 2

MIN_PER_LINE = 60 / P["pick_rate"]                                  # 0.75 min at 80 lines/h
TASK_MAX = int(S["task_max_lines"])
SETUP = S["task_setup_min"]
CV = S["pick_time_cv"]
BREAKS = [(120, 15), (240, 30), (360, 15)]                        # (minutes after shift start, length)
OT_MAX = P["max_overtime_hours"] * 60
DAY_START = 6 * 60                                                 # clock starts 06:00
print(f"Simulated day: Mon 12 Dec 2011, forecast P50 {P50:,.0f} lines (P10 {P10:,.0f} - P90 {P90:,.0f})")
print(f"Order size: median {np.median(SIZES):.0f}, mean {SIZES.mean():.1f} lines (n = {len(SIZES):,} real orders)")


# --- Block 2: one simulated day -------------------------------------------
def simulate(shifts, day_seed):
    """shifts: list of (start_hour, n_pickers), each shift 8 h. Returns KPIs for one day.
    day_seed fixes the day's demand (total lines, arrival times, order sizes) on one random
    stream and pick times on another, so every scenario is tested on exactly the same days."""
    rng = np.random.default_rng([day_seed, 0])        # demand
    rng_pick = np.random.default_rng([day_seed, 1])   # pick-time variation
    env = simpy.Environment(initial_time=DAY_START)
    tasks = simpy.Store(env)
    total_lines = math.exp(rng.normal(MU, SIGMA))
    n_orders = rng.poisson(total_lines / SIZES.mean())
    orders, done_lines, open_trace = {}, [0], []

    # arrivals: draw each order's hour from the hourly profile, uniform inside the hour
    hours = rng.choice(ARR.index.values, size=n_orders, p=ARR.values / ARR.values.sum())
    times = np.sort(hours * 60 + rng.uniform(0, 60, n_orders))
    order_sizes = rng.choice(SIZES, size=n_orders)

    def arrivals():
        for i, t in enumerate(times):
            yield env.timeout(max(0, t - env.now))
            lines = int(order_sizes[i])
            parts = [TASK_MAX] * (lines // TASK_MAX) + ([lines % TASK_MAX] if lines % TASK_MAX else [])
            orders[i] = {"arrive": env.now, "left": len(parts), "lines": lines, "done": None}
            for p in parts:
                tasks.put((i, p))

    picker_stats = []

    def picker(start, end):
        busy = 0.0
        yield env.timeout(start - env.now)
        next_break = 0
        while True:
            # breaks, taken between tasks
            if next_break < len(BREAKS) and env.now >= start + BREAKS[next_break][0] and env.now < end:
                yield env.timeout(BREAKS[next_break][1])
                next_break += 1
                continue
            if env.now >= end + OT_MAX or (env.now >= end and not tasks.items):
                break
            if not tasks.items and env.now < end:                     # idle: wait a minute
                yield env.timeout(1)
                continue
            order_id, lines = yield tasks.get()
            t = SETUP + lines * MIN_PER_LINE * rng_pick.lognormal(-0.5 * math.log(1 + CV**2), math.sqrt(math.log(1 + CV**2)))
            yield env.timeout(t)
            busy += t
            done_lines[0] += lines
            o = orders[order_id]
            o["left"] -= 1
            if o["left"] == 0:
                o["done"] = env.now
        picker_stats.append({"paid": end - start, "overtime": max(0.0, env.now - end), "busy": busy})

    def tracer():                                                     # open lines every 15 min
        while env.now < 22 * 60:
            arrived = sum(o["lines"] for o in orders.values())
            open_trace.append((env.now, arrived - done_lines[0]))
            yield env.timeout(15)

    env.process(arrivals())
    for start_h, n in shifts:
        for _ in range(n):
            env.process(picker(start_h * 60, start_h * 60 + 8 * 60))
    env.process(tracer())
    env.run(until=24 * 60)

    o = pd.DataFrame(orders.values(), columns=["arrive", "left", "lines", "done"])
    late_lines = int(o.lines.sum()) - done_lines[0]        # lines not picked today (partial orders count only the unpicked part)
    cycle = (o.done - o.arrive).dropna()
    ps = pd.DataFrame(picker_stats, columns=["paid", "overtime", "busy"])
    paid_h, ot_h = ps.paid.sum() / 60, ps.overtime.sum() / 60
    return {"lines": o.lines.sum(), "picked_lines": done_lines[0], "late_lines": late_lines,
            "late_lines_pct": 100 * late_lines / o.lines.sum(),
            "orders_same_day_pct": 100 * o.done.notna().mean() if len(o) else 100.0,
            "within_4h_pct": 100 * (cycle <= 240).sum() / max(len(o), 1),
            "mean_cycle_h": cycle.mean() / 60, "overtime_h": ot_h,
            "utilisation_pct": 100 * ps.busy.sum() / max(ps.paid.sum() + ps.overtime.sum(), 1e-9),
            "cost_index": paid_h + P["overtime_premium"] * ot_h}, open_trace


def main():
    # --- Block 3: scenarios ---------------------------------------------------
    N_REP = int(S["replications"])
    SCENARIOS = {
        "6 pickers, all 08-16": [(8, 6)],
        "6 pickers, all 09-17": [(9, 6)],
        "6 pickers, all 10-18": [(10, 6)],
        "6 pickers, split 3 x 08-16 + 3 x 10-18": [(8, 3), (10, 3)],
        "6 pickers, staggered 2 x 08/09/10": [(8, 2), (9, 2), (10, 2)],
        "6 pickers, split 3 x 09-17 + 3 x 11-19": [(9, 3), (11, 3)],
        "5 pickers, staggered 2/2/1": [(8, 2), (9, 2), (10, 1)],
        "5 pickers, all 10-18": [(10, 5)],
        "7 pickers, staggered 2/3/2": [(8, 2), (9, 3), (10, 2)],
    }
    rows, traces = [], {}
    for name, shifts in SCENARIOS.items():
        res = []
        for r in range(N_REP):
            k, tr = simulate(shifts, int(S["seed"]) * 10_000 + r)   # day r is the same in every scenario
            res.append(k)
            if r < 50:
                traces.setdefault(name, []).append(tr)
        res = pd.DataFrame(res)
        row = {"scenario": name, "pickers": sum(n for _, n in shifts)}
        for col in ["late_lines_pct", "orders_same_day_pct", "within_4h_pct", "mean_cycle_h", "overtime_h",
                    "utilisation_pct", "cost_index"]:
            m, half = res[col].mean(), 1.96 * res[col].std() / math.sqrt(N_REP)   # 95% CI of the mean
            row[col] = round(m, 2)
            row[col + "_ci95"] = round(half, 2)
        rows.append(row)
    out = pd.DataFrame(rows)
    base = out.loc[out.scenario == "6 pickers, all 08-16", "cost_index"].iloc[0]
    out["cost_vs_all_early_pct"] = (100 * (out.cost_index / base - 1)).round(1)
    out.to_csv(OUT / "05_simulation_scenarios.csv", index=False)

    show = out[["scenario", "late_lines_pct", "within_4h_pct", "mean_cycle_h", "overtime_h", "utilisation_pct",
                "cost_vs_all_early_pct"]]
    print(f"\n{N_REP} simulated days per scenario (same random days for each); means, 95% CI in the CSV:")
    print(show.to_string(index=False))

    # --- Block 4: chart -------------------------------------------------------
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4.2))
    cols = {"6 pickers, all 08-16": "#8C2F39", "6 pickers, all 10-18": "#B8892B",
            "6 pickers, staggered 2 x 08/09/10": "#1F3A5F"}
    for name, c in cols.items():
        tr = np.array([[v for _, v in t] for t in traces[name]])
        x = [t / 60 for t, _ in traces[name][0]]
        a1.plot(x, tr.mean(axis=0), color=c, lw=2, label=name.replace("6 pickers, ", ""))
    a1.set_xlabel("Hour of day"); a1.set_ylabel("Pick lines waiting (avg of 50 days)")
    a1.set_title("Work waiting through the day, 6 pickers", loc="left", fontsize=11)
    a1.legend(fontsize=8); a1.set_xlim(6, 21)
    lab = out.scenario.str.replace(" pickers", "p").str.replace("staggered", "stag.")
    a2.barh(lab, out.late_lines_pct, xerr=out.late_lines_pct_ci95, color="#8C2F39", alpha=.85)
    a2.set_xlabel("Lines picked a day late (%), mean ± 95% CI")
    a2.set_title("Late lines by shift pattern and crew", loc="left", fontsize=11)
    a2.invert_yaxis()
    for a in (a1, a2):
        a.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(OUT / "05_simulation.png", dpi=150)
    print("\nSaved outputs/05_simulation_scenarios.csv and outputs/05_simulation.png")


if __name__ == "__main__":
    main()
