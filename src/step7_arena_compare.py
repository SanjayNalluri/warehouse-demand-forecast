"""
Step 7 - Cross-check: Arena model vs SimPy model, same scenarios.

Inputs : arena/results/*.xlsm   Arena report workbooks, one per scenario (file name = scenario key below)
         outputs/05_simulation_scenarios.csv   SimPy results (step 5)
Outputs: outputs/07_arena_vs_simpy.csv

The Arena Student edition allows at most 150 entities in the model. On the busiest days the
pick queue gets close to that, so the Arena model ends a day early once more than 120 tasks are
waiting (Run Setup > Terminating Condition: NQ(Pick Task.Queue) > 120). Those days are counted
and reported, and the late-line average is shown with and without them.
"""
from pathlib import Path
import numpy as np
import pandas as pd
import openpyxl

ROOT = Path(__file__).resolve().parents[1]
RES, OUT = ROOT / "arena" / "results", ROOT / "outputs"

SCENARIOS = {                                           # file name -> SimPy scenario name
    "s1_6_all_08_16": "6 pickers, all 08-16",
    "s2_6_all_10_18": "6 pickers, all 10-18",
    "s3_6_split_09_11": "6 pickers, split 3 x 09-17 + 3 x 11-19",
    "s4_5_all_10_18": "5 pickers, all 10-18",
    "s5_7_staggered": "7 pickers, staggered 2/3/2",
}


def sheet(wb, name):
    rows = list(wb[name].iter_rows(values_only=True))
    return pd.DataFrame(rows[1:], columns=rows[0])


def ci(x):
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x))


simpy = pd.read_csv(OUT / "05_simulation_scenarios.csv").set_index("scenario")
rows = []
for key, name in SCENARIOS.items():
    f = RES / f"{key}.xlsm"
    if not f.exists():
        print(f"missing {f.name} - skipped")
        continue
    wb = openpyxl.load_workbook(f, data_only=True, read_only=True)
    reps = int(sheet(wb, "ProjectInformation").NumberOfReplications.iloc[0])
    o = sheet(wb, "OutputStatsByRep").pivot_table(index="Replication", columns="Name", values="RecordedValue")
    c = sheet(wb, "ContinuousTimeStatsByRep")
    o["queue_max"] = c[c.Name == "Pick Task.Queue"].set_index("Replication")["Maximum"]
    cut = o.queue_max > 120
    full = o[~cut]
    s = simpy.loc[name]
    rows.append({
        "scenario": name, "replications": reps, "days_cut_short": int(cut.sum()),
        "arena_late_pct": round(o.LateLinesPct.mean(), 2), "arena_late_ci95": round(ci(o.LateLinesPct), 2),
        "arena_late_pct_full_days": round(full.LateLinesPct.mean(), 2),
        "simpy_late_pct": s.late_lines_pct, "simpy_late_ci95": s.late_lines_pct_ci95,
        "arena_overtime_h": round(o.OvertimeHours.mean(), 2), "simpy_overtime_h": s.overtime_h,
        "arena_mean_lines": round(o.LinesInDay.mean(), 0),
    })

res = pd.DataFrame(rows)
res["late_diff_pts"] = (res.arena_late_pct - res.simpy_late_pct).round(2)
res["cis_overlap"] = (res.late_diff_pts.abs() <= res.arena_late_ci95 + res.simpy_late_ci95)
res.to_csv(OUT / "07_arena_vs_simpy.csv", index=False)
print(res[["scenario", "days_cut_short", "arena_late_pct", "arena_late_ci95", "simpy_late_pct", "simpy_late_ci95",
           "late_diff_pts", "cis_overlap", "arena_overtime_h", "simpy_overtime_h"]].to_string(index=False))
if len(res) > 1:
    r = np.corrcoef(res.arena_late_pct, res.simpy_late_pct)[0, 1]
    print(f"\nScenario ranking agreement (correlation of late %): {r:.3f}")
print("\nSaved outputs/07_arena_vs_simpy.csv")
