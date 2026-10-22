"""
Shared forecasting + staffing code: used by step 4 and by the API.
"""
from pathlib import Path
import json
import math
import numpy as np
import pandas as pd
import lightgbm as lgb
from features import build_features, extend_calendar, FEATURES, HORIZON

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "models"


def load_model():
    booster = lgb.Booster(model_file=str(MOD / "lgbm_pick_lines.txt"))
    info = json.loads((MOD / "model_info.json").read_text())
    return booster, info


def load_params(path=ROOT / "data" / "raw" / "staffing_parameters.csv"):
    return pd.read_csv(path).set_index("parameter")["value"].astype(float).to_dict()


def lines_per_picker(params):
    """Pick lines one picker can do in a normal shift."""
    return params["pick_rate"] * params["shift_hours"] * params["productive_share"]


def pickers_needed(lines, params):
    return 0 if lines <= 0 else math.ceil(lines / lines_per_picker(params))


def forecast_next_days(daily, booster, info, horizon=HORIZON):
    """daily: history with date, is_open, lines. Returns the next `horizon` calendar days."""
    if not 1 <= horizon <= HORIZON:
        raise ValueError(f"horizon must be 1-{HORIZON} days")
    cal = extend_calendar(daily, horizon)
    f = build_features(cal)
    fut = f[f.date > daily.date.max()].copy()
    pred = booster.predict(fut[FEATURES])
    if info["base_column"]:
        pred = pred * fut[info["base_column"]].values
    m = info["interval_multipliers"]
    is_open = fut.is_open.values == 1
    fut["p50"] = np.where(is_open, pred, 0.0)
    fut["p10"] = fut.p50 * m["p10"]
    fut["p75"] = fut.p50 * m["p75"]
    fut["p90"] = fut.p50 * m["p90"]
    return fut[["date", "is_open", "p10", "p50", "p75", "p90"]].reset_index(drop=True)
