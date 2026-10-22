"""
Step 3 - Forecast daily pick lines: baselines vs LightGBM, tracked in MLflow, explained with SHAP.
Input  : data/processed/daily_workload.csv (step 2)
Outputs: models/lgbm_pick_lines.txt     final model (trained on all data, used by the API)
         models/model_info.json          features, settings, interval multipliers, test metrics
         outputs/03_model_comparison.csv
         outputs/03_test_predictions.csv  daily test forecasts (used by step 4)
         outputs/03_test_forecast.png    test period: actual vs forecast with 80% band
         outputs/03_shap_importance.png, outputs/03_shap_beeswarm.png
         mlflow.db                       all runs (view: mlflow ui --backend-store-uri sqlite:///mlflow.db)
Needs  : pip install lightgbm mlflow shap

How it is tested (rolling origin, like real use):
  at the start of each month the model is retrained on all earlier days, then forecasts
  that month (each day from data at least 7 days old = a 7-day-ahead forecast).
  Tuning months : Jan - Jun 2011 (settings are chosen here only)
  Test months   : Jul - Dec 2011 (includes the autumn peak; scored once at the end)
"""
from pathlib import Path
import json, os, itertools, warnings
import numpy as np
import pandas as pd
import lightgbm as lgb
import mlflow
import shap
import matplotlib.pyplot as plt
from features import build_features, FEATURES, HORIZON

os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
warnings.filterwarnings("ignore")

# --- Block 1: settings + data --------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
PROC, OUT, MOD = ROOT / "data" / "processed", ROOT / "outputs", ROOT / "models"
MOD.mkdir(exist_ok=True)
TUNE_MONTHS = pd.date_range("2011-01-01", "2011-06-01", freq="MS")
TEST_MONTHS = pd.date_range("2011-07-01", "2011-12-01", freq="MS")
GRID = {"target": ["raw", "ratio", "expected"], "objective": ["median", "mean"],
        "num_leaves": [7, 15], "min_child_samples": [10, 20], "n_estimators": [200, 500]}
FIXED = dict(learning_rate=0.03, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
             reg_lambda=1.0, verbose=-1, random_state=42)
# Target options: "raw" = lines; "ratio" = lines / recent 28-day level;
# "expected" = lines / (last year's level x year-on-year growth). Ratio targets let the
# model learn the shape (weekday, season) while the level carries growth.
BASE = {"ratio": "open_mean_28", "expected": "expected_level"}

daily = pd.read_csv(PROC / "daily_workload.csv", parse_dates=["date"])
f = build_features(daily)
# open days with enough history (the first ~5 weeks have no lag features)
f = f[(f.is_open == 1) & f.same_dow_mean_4.notna() & f.open_mean_28.notna()].reset_index(drop=True)
test = f[f.date >= TEST_MONTHS[0]]
print(f"Model rows: {len(f)} open days ({f.date.min():%d %b %Y} - {f.date.max():%d %b %Y}); "
      f"test {len(test)} days ({test.date.min():%d %b %Y} - {test.date.max():%d %b %Y})\n")


def wape(y, p):
    return 100 * np.abs(y - p).sum() / y.sum()


def scores(y, p):
    return {"wape": wape(y, p), "mae": np.abs(y - p).mean(), "bias_pct": 100 * (p.sum() - y.sum()) / y.sum()}


# --- Block 2: LightGBM helpers --------------------------------------------
def fit(df, p):
    y = df.lines / df[BASE[p["target"]]] if p["target"] in BASE else df.lines
    obj = dict(objective="quantile", alpha=0.5) if p["objective"] == "median" else dict(objective="regression")
    params = {k: v for k, v in p.items() if k not in ("target", "objective")}
    return lgb.LGBMRegressor(**obj, **params, **FIXED).fit(df[FEATURES], y)


def predict(m, df, p):
    pred = m.predict(df[FEATURES])
    return pred * df[BASE[p["target"]]].values if p["target"] in BASE else pred


def backtest(p, months):
    """Retrain at each month start on all earlier days, forecast that month."""
    out = []
    for m in months:
        tr = f[f.date < m]
        te = f[(f.date >= m) & (f.date < m + pd.offsets.MonthBegin(1))]
        out.append(te.assign(pred=predict(fit(tr, p), te, p)))
    return pd.concat(out)


mlflow.set_tracking_uri(f"sqlite:///{(ROOT / 'mlflow.db').as_posix()}")
mlflow.set_experiment("warehouse-pick-lines")

# --- Block 3: tune on Jan - Jun 2011 --------------------------------------
tune = []
for vals in itertools.product(*GRID.values()):
    p = dict(zip(GRID.keys(), vals))
    r = backtest(p, TUNE_MONTHS)
    tune.append({**p, "tune_wape": wape(r.lines, r.pred)})
    with mlflow.start_run(run_name="tune | " + " ".join(f"{k}={v}" for k, v in p.items())):
        mlflow.log_params(p)
        mlflow.log_metric("tune_wape", tune[-1]["tune_wape"])
tune = pd.DataFrame(tune).sort_values("tune_wape")
best = {k: (v if k in ("target", "objective") else int(v)) for k, v in tune.iloc[0].drop("tune_wape").items()}
print(f"Tried {len(tune)} settings. Top 5 by WAPE on the tuning months (Jan - Jun 2011):")
print(tune.head(5).round(2).to_string(index=False), "\n")

# 80% interval: P10/P90 of (actual / forecast) on the tuning months, so it is
# calibrated without looking at the test months.
r_tune = backtest(best, TUNE_MONTHS)
LO, Q75, HI = (float((r_tune.lines / r_tune.pred).quantile(q)) for q in (0.10, 0.75, 0.90))

# --- Block 4: score the test months once ----------------------------------
r = backtest(best, TEST_MONTHS)
p50, p10, p90 = r.pred.values, r.pred.values * LO, r.pred.values * HI
s = scores(r.lines, p50)
coverage = 100 * ((r.lines >= p10) & (r.lines <= p90)).mean()
wk = pd.DataFrame({"w": r.date.dt.to_period("W-SAT"), "y": r.lines, "p": p50}).groupby("w").sum()
weekly = wape(wk.y, wk.p)

baselines = {
    "Naive: same weekday last week": test.lag_7.fillna(test.same_dow_mean_4),
    "Mean of last 4 same weekdays": test.same_dow_mean_4,
    "Same weekday last year": test.lag_364.fillna(test.same_dow_mean_4),
    "Last year's level x growth": test.expected_level,
}
rows = []
for name, pb in baselines.items():
    sb = scores(test.lines, pb)
    rows.append({"model": name, **sb})
    with mlflow.start_run(run_name=f"baseline | {name}"):
        mlflow.log_param("model", name)
        mlflow.log_metrics({f"test_{k}": v for k, v in sb.items()})
rows.append({"model": "LightGBM (tuned, retrained monthly)", **s})
comp = pd.DataFrame(rows).round(2)
pd.DataFrame({"date": r.date.dt.strftime("%Y-%m-%d"), "dow": r.dow, "actual": r.lines,
              "p10": p10.round(1), "p50": p50.round(1), "p75": (p50 * Q75).round(1), "p90": p90.round(1),
              "naive": r.lag_7.fillna(r.same_dow_mean_4).values}).to_csv(OUT / "03_test_predictions.csv", index=False)
comp.to_csv(OUT / "03_model_comparison.csv", index=False)
naive = comp.loc[0, "wape"]
best_base = comp.iloc[:-1].sort_values("wape").iloc[0]

print("Test months, Jul - Dec 2011 (WAPE = total abs error / total lines; bias = forecast vs actual total):")
print(comp.to_string(index=False))
print(f"\nLightGBM: WAPE {s['wape']:.1f}% vs naive {naive:.1f}% ({100 * (naive - s['wape']) / naive:.0f}% lower error), "
      f"vs best baseline '{best_base.model}' {best_base.wape:.1f}%")
print(f"Weekly totals (Sun-Fri): WAPE {weekly:.1f}%")
print(f"80% interval (forecast x {LO:.2f} to x {HI:.2f}) covers {coverage:.0f}% of test days (target 80%)")

# chart
fig, ax = plt.subplots(figsize=(11, 4))
ax.fill_between(r.date, p10, p90, color="#118DFF", alpha=0.2, label="80% interval")
ax.plot(r.date, r.lines, "o-", color="#14213D", ms=2.5, lw=0.8, label="Actual")
ax.plot(r.date, p50, color="#118DFF", lw=1.8, label=f"LightGBM 7-day-ahead forecast (WAPE {s['wape']:.1f}%)")
ax.plot(test.date, baselines["Naive: same weekday last week"], color="#E9A23B", lw=1, ls="--",
        label=f"Naive: same weekday last week (WAPE {naive:.1f}%)")
ax.set_ylabel("Pick lines per day"); ax.legend(loc="upper left", fontsize=8)
ax.set_title("Test months (never used for tuning): forecast vs actual, Jul - Dec 2011", loc="left")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "03_test_forecast.png", dpi=150)

# --- Block 5: final model on ALL data (for the API) + SHAP ---------------
final = fit(f, best)
final.booster_.save_model(str(MOD / "lgbm_pick_lines.txt"))
X = f[f.date >= TEST_MONTHS[0]][FEATURES]
sv = shap.TreeExplainer(final).shap_values(X)
imp = pd.Series(np.abs(sv).mean(axis=0), FEATURES).sort_values()
fig, ax = plt.subplots(figsize=(7, 4.5))
ax.barh(imp.index, imp.values, color="#118DFF")
ax.set_xlabel("Mean |SHAP value|" + (" (effect on lines / base level)" if best["target"] in BASE else " (pick lines)"))
ax.set_title("What drives the forecast", loc="left"); ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout(); fig.savefig(OUT / "03_shap_importance.png", dpi=150)
plt.figure(); shap.summary_plot(sv, X, show=False)
plt.tight_layout(); plt.savefig(OUT / "03_shap_beeswarm.png", dpi=150); plt.close("all")
print("Top features (SHAP):", ", ".join(imp.sort_values(ascending=False).index[:5]))

info = {"features": FEATURES, "horizon_days": HORIZON, "settings": best, "base_column": BASE.get(best["target"]),
        "trained_on": [str(f.date.min().date()), str(f.date.max().date())],
        "interval_multipliers": {"p10": round(LO, 4), "p75": round(Q75, 4), "p90": round(HI, 4)},
        "test_months": [str(TEST_MONTHS[0].date()), str(r.date.max().date())],
        "test_wape": round(s["wape"], 2), "test_bias_pct": round(s["bias_pct"], 2),
        "test_weekly_wape": round(weekly, 2), "naive_wape": round(naive, 2),
        "best_baseline": best_base.model, "best_baseline_wape": round(best_base.wape, 2),
        "interval_coverage_pct": round(coverage, 1)}
(MOD / "model_info.json").write_text(json.dumps(info, indent=2))
with mlflow.start_run(run_name="final | lgbm tuned"):
    mlflow.log_params(best)
    mlflow.log_metrics({"test_wape": s["wape"], "test_mae": s["mae"], "test_bias_pct": s["bias_pct"],
                        "test_weekly_wape": weekly, "interval_coverage_pct": coverage, "naive_test_wape": naive})
    for p in ["03_test_forecast.png", "03_shap_importance.png", "03_shap_beeswarm.png", "03_model_comparison.csv"]:
        mlflow.log_artifact(str(OUT / p))
    for p in MOD.iterdir():
        mlflow.log_artifact(str(p), artifact_path="model")
print("\nSaved models/lgbm_pick_lines.txt, models/model_info.json, outputs/03_*, MLflow runs in mlflow.db")
