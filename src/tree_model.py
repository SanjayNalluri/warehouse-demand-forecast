"""
Score a LightGBM model from its JSON dump with plain numpy.

Why: the API runs as a small serverless function, where the LightGBM library
(and its OpenMP runtime) is too heavy. The trained model is exported once with
booster.dump_model(); this file walks the same trees. tests/test_tree_model.py
checks the predictions match LightGBM.

Supports numerical splits ("<="), the only kind this model uses.
"""
import json
from pathlib import Path
import numpy as np


class TreeModel:
    def __init__(self, path):
        d = json.loads(Path(path).read_text())
        if d["num_tree_per_iteration"] != 1 or d.get("average_output"):
            raise ValueError("only single-output boosted regression models are supported")
        self.feature_names = d["feature_names"]
        self.trees = [self._flatten(t["tree_structure"]) for t in d["tree_info"]]

    @staticmethod
    def _flatten(root):
        """Turn the nested tree into arrays; leaves get feature = -1."""
        feat, thr, left, right, default_left, nan_mode, value = [], [], [], [], [], [], []

        def add(node):
            i = len(feat)
            for lst in (feat, thr, left, right, default_left, nan_mode, value):
                lst.append(0)
            if "leaf_value" in node or "split_index" not in node:
                feat[i], value[i] = -1, node.get("leaf_value", 0.0)
                return i
            if node["decision_type"] != "<=":
                raise ValueError(f"unsupported split {node['decision_type']}")
            feat[i], thr[i] = node["split_feature"], node["threshold"]
            default_left[i] = node["default_left"]
            nan_mode[i] = {"None": 0, "NaN": 1, "Zero": 2}[node["missing_type"]]
            left[i] = add(node["left_child"])
            right[i] = add(node["right_child"])
            return i

        add(root)
        return tuple(np.array(a) for a in (feat, thr, left, right, default_left, nan_mode, value))

    def predict(self, X):
        X = np.asarray(X, dtype=float)
        out = np.zeros(len(X))
        rows = np.arange(len(X))
        for feat, thr, left, right, dleft, nan_mode, value in self.trees:
            node = np.zeros(len(X), dtype=int)
            while True:
                f = feat[node]
                inner = f >= 0
                if not inner.any():
                    break
                r, n = rows[inner], node[inner]
                x = X[r, f[inner]]
                mode = nan_mode[n]
                x = np.where((mode == 0) & np.isnan(x), 0.0, x)          # missing type None: NaN -> 0
                missing = ((mode == 1) & np.isnan(x)) | ((mode == 2) & ((x == 0) | np.isnan(x)))
                go_left = np.where(missing, dleft[n].astype(bool), x <= thr[n])
                node[inner] = np.where(go_left, left[n], right[n])
            out += value[node]
        return out
