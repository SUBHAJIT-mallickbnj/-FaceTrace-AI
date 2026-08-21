import math
import unittest
from unittest.mock import MagicMock, patch

from pages.helper.map_utils import (
    geocode_last_seen_location,
    resolve_case_map_coordinate,
    separate_overlapping_coordinate,
)


class MapUtilsTests(unittest.TestCase):
    def test_repeated_city_coordinates_are_separated(self):
        seen = {}
        first = separate_overlapping_coordinate((22.5726, 88.3639), seen)
        second = separate_overlapping_coordinate((22.5726, 88.3639), seen)

        self.assertEqual(first, (22.5726, 88.3639))
        self.assertNotEqual(second, first)
        self.assertGreater(abs(second[0] - first[0]) + abs(second[1] - first[1]), 0.1)
        self.assertEqual(len(seen), 1)

    def test_map_uses_last_seen_only(self):
        with patch(
            "pages.helper.map_utils.geocode_last_seen_location",
            return_value=(22.5726, 88.3639),
        ) as geocode:
            coords = resolve_case_map_coordinate(
                "Kolkata",
                "New Town, Kolkata",
                "Baguihati",
                12.9716,
                77.5946,
            )

        self.assertEqual(coords, (22.5726, 88.3639))
        geocode.assert_called_once_with("New Town, Kolkata")

    def test_last_seen_geocoder_does_not_use_other_case_fields(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = "[]"
        with patch("pages.helper.map_utils.urlopen", return_value=response) as urlopen:
            geocode_last_seen_location("Ranchi")

        request = urlopen.call_args.args[0]
        self.assertIn("Ranchi%2C+India", request.full_url)
        self.assertNotIn("Baguihati", request.full_url)


if __name__ == "__main__":
    unittest.main()