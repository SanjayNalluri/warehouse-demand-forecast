"""
Step 4 - From forecast to pickers per day, and which staffing rule works best.
Inputs : outputs/03_test_predictions.csv (step 3), data/processed/daily_workload.csv,
         data/raw/staffing_parameters.csv, models/ (step 3)
Outputs: outputs/04_staffing_policies.csv   each rule scored on Jul - Dec 2011
         outputs/04_pick_rate_sensitivity.csv
         outputs/04_staffing_test.png
         outputs/04_next_week_plan.csv       forecast + pickers for 9 - 15 Dec 2011

A day is simulated like this: the rule sets pickers in advance; actual lines arrive;
up to `max_overtime_hours` per picker is used if needed; anything beyond becomes backlog
(lines picked a day late). Cost index = paid normal hours + premium x overtime hours.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from forecast import load_model, load_params, lines_per_picker, pickers_needed, forecast_next_days

ROOT = Path(__file__).resolve().parents[1]
PROC, OUT = ROOT / "data" / "processed", ROOT / "outputs"
P = load_params()
test = pd.read_csv(OUT / "03_test_predictions.csv", parse_dates=["date"])
daily = pd.read_csv(PROC / "daily_workload.csv", parse_dates=["date"])
print(f"One picker does {lines_per_picker(P):.0f} lines per shift "
      f"({P['pick_rate']:.0f} lines/h x {P['shift_hours']:.0f} h x {P['productive_share']:.0%} productive)\n")


# --- Block 1: staffing rules (pickers set the week before) -----------------
def rules(params):
    prior = daily[(daily.date >= "2011-01-01") & (daily.date < "2011-07-01") & (daily.is_open == 1)]
    flat = pickers_needed(prior.lines.quantile(0.9), params)   # enough for a busy day in Jan - Jun
    return {
        f"Flat crew ({flat} pickers, sized on Jan-Jun busy days)": np.full(len(test), flat),
        "Naive: last week's same weekday": test.naive.apply(pickers_needed, args=(params,)).values,
        "Forecast P50 (middle)": test.p50.apply(pickers_needed, args=(params,)).values,
        "Forecast P75": test.p75.apply(pickers_needed, args=(params,)).values,
        "Forecast P90 (upper end)": test.p90.apply(pickers_needed, args=(params,)).values,
    }


# --- Block 2: simulate a day-by-day outcome for each rule ------------------
def simulate(pickers, params):
    rate, shift, prod = params["pick_rate"], params["shift_hours"], params["productive_share"]
    need_h = test.actual.values / rate                      # picking hours needed
    cap_h = pickers * shift * prod                          # productive hours available
    ot_h = np.minimum(np.maximum(need_h - cap_h, 0), pickers * params["max_overtime_hours"])
    backlog_lines = np.maximum(need_h - cap_h - ot_h, 0) * rate
    idle_h = np.maximum(cap_h - need_h, 0)
    paid_h = pickers * shift
    return {"avg_pickers": pickers.mean(), "paid_hours": paid_h.sum(), "overtime_hours": ot_h.sum(),
            "idle_hours": idle_h.sum(), "days_with_overtime": int((ot_h > 0).sum()),
            "days_with_backlog": int((backlog_lines > 0).sum()),
            "late_lines_pct": 100 * backlog_lines.sum() / test.actual.sum(),
            "cost_index": paid_h.sum() + params["overtime_premium"] * ot_h.sum()}


res = pd.DataFrame({name: simulate(p, P) for name, p in rules(P).items()}).T
res["cost_vs_flat_pct"] = 100 * (res.cost_index / res.cost_index.iloc[0] - 1)
res = res.round(1)
res.to_csv(OUT / "04_staffing_policies.csv")
print(f"Staffing rules on the test months ({len(test)} open days, Jul - Dec 2011):")
print(res.to_string(), "\n")

# --- Block 3: does the answer change with the pick rate? ------------------
sens = []
for rate in [60, 80, 100, 120]:
    p = {**P, "pick_rate": rate}
    for name, pk in rules(p).items():
        s = simulate(pk, p)
        sens.append({"pick_rate": rate, "rule": name.split(" (")[0] if name.startswith("Flat") else name,
                     "cost_index": round(s["cost_index"]), "late_lines_pct": round(s["late_lines_pct"], 2),
                     "days_with_backlog": s["days_with_backlog"]})
sens = pd.DataFrame(sens)
sens.to_csv(OUT / "04_pick_rate_sensitivity.csv", index=False)
print("Pick-rate sensitivity (cost index, % lines late):")
print(sens.pivot(index="rule", columns="pick_rate", values=["cost_index", "late_lines_pct"]).to_string(), "\n")

# --- Block 4: chart -------------------------------------------------------
r = rules(P)
needed = np.ceil(test.actual / lines_per_picker(P))
fig, ax = plt.subplots(figsize=(11, 4))
ax.plot(test.date, needed, "o", color="#14213D", ms=3, label="Pickers actually needed (normal hours)")
flat_name = [k for k in r if k.startswith("Flat")][0]
ax.step(test.date, r[flat_name], where="mid", color="#8C2F39", lw=1.2, label="Flat crew")
ax.step(test.date, r["Forecast P50 (middle)"], where="mid", color="#118DFF", lw=1, alpha=0.7, label="Forecast P50")
ax.step(test.date, r["Forecast P75"], where="mid", color="#0F5C4C", lw=1.6, label="Forecast P75")
ax.set_ylabel("Pickers"); ax.legend(loc="upper left", fontsize=8)
ax.set_title("Pickers scheduled vs needed, Jul - Dec 2011 (test months)", loc="left")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "04_staffing_test.png", dpi=150)

# --- Block 5: plan for the next 7 days after the data ends ----------------
model, info = load_model()
plan = forecast_next_days(daily, model, info)
plan["pickers_p50"] = plan.p50.apply(pickers_needed, args=(P,))
plan["pickers_p75"] = plan.p75.apply(pickers_needed, args=(P,))
plan["day"] = plan.date.dt.day_name()
plan = plan[["date", "day", "is_open", "p10", "p50", "p75", "p90", "pickers_p50", "pickers_p75"]]
plan[["p10", "p50", "p75", "p90"]] = plan[["p10", "p50", "p75", "p90"]].round(0)
plan.to_csv(OUT / "04_next_week_plan.csv", index=False, date_format="%Y-%m-%d")
print("Next 7 days after the data ends (pick lines, and pickers for the P50 and P75 rules):")
print(plan.to_string(index=False))
print("\nSaved outputs/04_staffing_policies.csv, 04_pick_rate_sensitivity.csv, 04_staffing_test.png, 04_next_week_plan.csv")
