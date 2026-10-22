"""The API scores the model from JSON with numpy; it must match LightGBM exactly."""
import numpy as np
import pytest
from features import build_features, FEATURES
from tree_model import TreeModel

lgb = pytest.importorskip("lightgbm")


def test_json_model_matches_lightgbm(daily):
    from conftest import ROOT
    booster = lgb.Booster(model_file=str(ROOT / "models" / "lgbm_pick_lines.txt"))
    tree = TreeModel(ROOT / "models" / "lgbm_pick_lines.json")
    X = build_features(daily)[FEATURES]                      # includes rows with missing lags
    assert np.isnan(X.values).any()
    np.testing.assert_allclose(tree.predict(X.values), booster.predict(X), rtol=0, atol=1e-9)
