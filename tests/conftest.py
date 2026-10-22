import sys
from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


@pytest.fixture
def daily():
    return pd.read_csv(ROOT / "data" / "processed" / "daily_workload.csv", parse_dates=["date"])