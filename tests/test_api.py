"""API endpoints."""
import math
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_forecast_default_7_days():
    body = client.get("/forecast").json()
    assert len(body["days"]) == 7
    assert body["rule"] == "p75"
    for d in body["days"]:
        if d["is_open"]:
            assert 0 < d["lines_p10"] <= d["lines_p50"] <= d["lines_p75"] <= d["lines_p90"]
            assert d["pickers"] == math.ceil(d["lines_p75"] / body["lines_per_picker_shift"])
        else:
            assert d["lines_p50"] == 0 and d["pickers"] == 0


def test_saturday_is_closed():
    days = client.get("/forecast").json()["days"]
    sat = [d for d in days if d["weekday"] == "Saturday"]
    assert sat and all(not d["is_open"] and d["pickers"] == 0 for d in sat)


def test_higher_rule_never_needs_fewer_pickers():
    p50 = client.get("/forecast", params={"rule": "p50"}).json()["total_picker_shifts"]
    p90 = client.get("/forecast", params={"rule": "p90"}).json()["total_picker_shifts"]
    assert p90 >= p50


def test_faster_picking_needs_fewer_pickers():
    slow = client.get("/forecast", params={"pick_rate": 60}).json()["total_picker_shifts"]
    fast = client.get("/forecast", params={"pick_rate": 120}).json()["total_picker_shifts"]
    assert fast <= slow


@pytest.mark.parametrize("params", [{"days": 0}, {"days": 8}, {"rule": "p99"}, {"pick_rate": -5}])
def test_bad_input_rejected(params):
    assert client.get("/forecast", params=params).status_code == 422


def test_history_and_backtest():
    h = client.get("/history", params={"days": 30}).json()
    assert len(h) == 30 and all(d["lines"] >= 0 for d in h)
    b = client.get("/backtest").json()
    assert len(b["daily"]) > 100 and len(b["staffing_rules"]) == 5


def test_simulation_endpoint():
    s = client.get("/simulation").json()
    assert len(s["scenarios"]) == 9
    assert all(0 <= r["late_lines_pct"] <= 100 for r in s["scenarios"])
