import math
import unittest
from unittest.mock import patch

from pages.helper.map_utils import (
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

    def test_invalid_stored_coordinates_use_geocoding(self):
        with patch(
            "pages.helper.map_utils.geocode_location",
            return_value=(22.5726, 88.3639),
        ) as geocode:
            coords = resolve_case_map_coordinate(
                "Kolkata", "New Town, Kolkata", "Baguihati", math.nan, None
            )

        self.assertEqual(coords, (22.5726, 88.3639))
        geocode.assert_called_once_with("Kolkata", "New Town, Kolkata", "Baguihati")


if __name__ == "__main__":
    unittest.main()