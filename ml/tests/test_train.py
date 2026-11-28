import os
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from ml.train import ROOT, output_path, sub_index, build_targets


class TrainingTargetTests(unittest.TestCase):
    def test_training_respects_the_same_configured_artifact_path_as_django(self):
        with patch.dict(os.environ, {"ML_ARTIFACT_PATH": "custom/models/atmoiq.joblib"}):
            self.assertEqual(output_path("ML_ARTIFACT_PATH", Path("ml/artifacts/default.joblib")), ROOT / "custom/models/atmoiq.joblib")

    def test_pm25_breakpoint_boundaries(self):
        self.assertEqual(sub_index("pm2_5", 0), 0)
        self.assertEqual(sub_index("pm2_5", 30), 50)
        self.assertEqual(sub_index("pm2_5", 60), 100)

    def test_rolling_targets_require_minimum_history(self):
        hours = 30
        data = {
            "time": pd.date_range("2024-01-01", periods=hours, freq="3h"),
            "city": ["Kolkata"] * hours,
            "pm2_5": [20.0] * hours, "pm10": [40.0] * hours,
            "nitrogen_dioxide": [10.0] * hours, "sulphur_dioxide": [5.0] * hours,
            "carbon_monoxide": [1000.0] * hours, "ozone": [30.0] * hours,
        }
        result = build_targets(pd.DataFrame(data))
        self.assertTrue(np.isnan(result.loc[0, "aqi"]))
        self.assertTrue(np.isnan(result.loc[5, "aqi"]))
        self.assertTrue(np.isfinite(result.loc[7, "aqi"]))
        self.assertAlmostEqual(result.loc[7, "avg_carbon_monoxide"], 1.0)

    def test_negative_measurements_are_not_used_as_valid_targets(self):
        data = {
            "time": pd.date_range("2024-01-01", periods=24, freq="3h"),
            "city": ["Kolkata"] * 24,
            "pm2_5": [-1.0] * 24, "pm10": [-1.0] * 24,
            "nitrogen_dioxide": [10.0] * 24, "sulphur_dioxide": [5.0] * 24,
            "carbon_monoxide": [1000.0] * 24, "ozone": [30.0] * 24,
        }
        result = build_targets(pd.DataFrame(data))
        self.assertTrue(np.isnan(result.loc[23, "aqi"]))


if __name__ == "__main__":
    unittest.main()
