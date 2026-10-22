"""
Warehouse Demand API: pick-line forecast and picker staffing for the next 1-7 days.
Run locally : uvicorn api.main:app --reload      (from the project folder)
Docs        : http://127.0.0.1:8000/docs
Deployed    : as a Vercel Python function (vercel.json); also runs in Docker
"""
import sys
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from features import HORIZON                                        # noqa: E402
from forecast import (load_model, load_params, forecast_next_days,  # noqa: E402
                      pickers_needed, lines_per_picker)

# --- Load once at start-up ------------------------------------------------
MODEL, INFO = load_model()
PARAMS = load_params()
DAILY = pd.read_csv(ROOT / "data" / "processed" / "daily_workload.csv", parse_dates=["date"])
OUT = ROOT / "outputs"

app = FastAPI(title="Warehouse Demand API",
              description="Forecast daily pick lines (LightGBM) and the pickers needed, for the 7 days "
                          "after the data ends (UCI Online Retail II, Dec 2009 - Dec 2011).",
              version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])


# --- Response models ------------------------------------------------------
class DayForecast(BaseModel):
    date: str
    weekday: str
    is_open: bool
    lines_p10: float
    lines_p50: float
    lines_p75: float
    lines_p90: float
    pickers: int


class ForecastResponse(BaseModel):
    rule: str
    pick_rate: float
    lines_per_picker_shift: float
    total_lines_p50: float
    total_picker_shifts: int
    days: list[DayForecast]


class HistoryDay(BaseModel):
    date: str
    is_open: bool
    lines: int


# --- Endpoints ------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok", "model_trained_to": INFO["trained_on"][1]}


@app.get("/model-info")
def model_info():
    """Features, settings and test results of the deployed model."""
    return INFO


@app.get("/forecast", response_model=ForecastResponse)
def forecast(days: int = Query(7, ge=1, le=HORIZON, description="Days ahead (1-7)"),
             rule: Literal["p50", "p75", "p90"] = Query("p75", description="Forecast level used to set pickers"),
             pick_rate: float = Query(PARAMS["pick_rate"], gt=0, le=1000, description="Lines per picker-hour")):
    params = {**PARAMS, "pick_rate": pick_rate}
    fc = forecast_next_days(DAILY, MODEL, INFO, horizon=days)
    out = [DayForecast(date=r.date.strftime("%Y-%m-%d"), weekday=r.date.day_name(), is_open=bool(r.is_open),
                       lines_p10=round(r.p10, 1), lines_p50=round(r.p50, 1), lines_p75=round(r.p75, 1),
                       lines_p90=round(r.p90, 1), pickers=pickers_needed(getattr(r, rule), params))
           for r in fc.itertuples()]
    return ForecastResponse(rule=rule, pick_rate=pick_rate, lines_per_picker_shift=round(lines_per_picker(params), 1),
                            total_lines_p50=round(float(fc.p50.sum()), 1),
                            total_picker_shifts=sum(d.pickers for d in out), days=out)


@app.get("/history", response_model=list[HistoryDay])
def history(days: int = Query(90, ge=7, le=740, description="Calendar days of history to return")):
    """Actual daily pick lines before the forecast starts."""
    h = DAILY.tail(days)
    return [HistoryDay(date=d.strftime("%Y-%m-%d"), is_open=bool(o), lines=int(l))
            for d, o, l in zip(h.date, h.is_open, h.lines)]


@app.get("/backtest")
def backtest():
    """Test months (Jul - Dec 2011): daily forecast vs actual, and the staffing-rule comparison."""
    pred = pd.read_csv(OUT / "03_test_predictions.csv")
    rules = pd.read_csv(OUT / "04_staffing_policies.csv").rename(columns={"Unnamed: 0": "rule"})
    models = pd.read_csv(OUT / "03_model_comparison.csv")
    return {"daily": pred.to_dict(orient="records"), "staffing_rules": rules.to_dict(orient="records"),
            "model_comparison": models.to_dict(orient="records")}
