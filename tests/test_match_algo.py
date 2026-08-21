import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from pages.helper import match_algo


class MatchAlgoTests(unittest.TestCase):
    def test_public_cases_data_defaults_to_all_rows(self):
        def fake_fetch_public_cases(train_data, status=None):
            if status == "NF":
                return []
            return [("case-1", "[0.1, 0.2]")]

        with patch("pages.helper.match_algo.db_queries.fetch_public_cases", side_effect=fake_fetch_public_cases):
            df = match_algo.get_public_cases_data()

        self.assertIsNotNone(df)
        self.assertEqual(df.iloc[0, 0], "case-1")

    def test_identity_distance_rejects_different_face(self):
        close = np.array([1.0, 0.0] + [0.0] * 126)
        different = np.array([-1.0, 0.0] + [0.0] * 126)
        self.assertLess(match_algo._distance(close, close), 0.363)
        self.assertGreater(match_algo._distance(close, different), 0.363)

    def test_match_uses_only_matches_below_identity_threshold(self):
        close = np.array([1.0, 0.0] + [0.0] * 126)
        different = np.array([-1.0, 0.0] + [0.0] * 126)
        public = pd.DataFrame([("sighting", close)], columns=["label", "feature"])
        registered = pd.DataFrame([("case", different)], columns=["label", "feature"])

        with patch.object(match_algo, "get_public_cases_data", return_value=public), patch.object(
            match_algo, "get_registered_cases_data", return_value=registered
        ):
            result = match_algo.match()

        self.assertTrue(result["status"])
        self.assertEqual(result["result"], {})

    def test_match_confirms_same_identity_embedding(self):
        same_face = np.array([1.0, 0.0] + [0.0] * 126)
        public = pd.DataFrame([("sighting", same_face)], columns=["label", "feature"])
        registered = pd.DataFrame([("case", same_face)], columns=["label", "feature"])

        with patch.object(match_algo, "get_public_cases_data", return_value=public), patch.object(
            match_algo, "get_registered_cases_data", return_value=registered
        ):
            result = match_algo.match()

        self.assertEqual(result["result"], {"case": [("sighting", 0.0)]})

    def test_decode_feature_rejects_invalid_data(self):
        self.assertIsNone(match_algo._decode_feature("not-json"))
        self.assertIsNone(match_algo._decode_feature([]))


if __name__ == "__main__":
    unittest.main()
