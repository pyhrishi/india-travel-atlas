import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = importlib.util.spec_from_file_location(
    "build_global_maps", os.path.join(ROOT, "tools", "build_global_maps.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GlobalMapValidationTests(unittest.TestCase):
    def feature(self, name="Province A", geometry=None):
        return {
            "type": "Feature",
            "properties": {"shapeName": name, "shapeID": "ABC-1"},
            "geometry": geometry or {
                "type": "Polygon",
                "coordinates": [[[10, 20], [11, 20], [11, 21], [10, 20]]]
            }
        }

    def test_valid_polygon_is_normalized_for_existing_map_renderer(self):
        result = MODULE.normalize_feature(self.feature(), "XYZ")
        self.assertEqual(result["properties"]["st_nm"], "Province A")
        self.assertEqual(result["properties"]["country_iso3"], "XYZ")
        self.assertEqual(result["geometry"]["type"], "Polygon")

    def test_valid_multipolygon_is_accepted(self):
        geometry = {
            "type": "MultiPolygon",
            "coordinates": [
                [[[10, 20], [11, 20], [11, 21], [10, 20]]],
                [[[12, 20], [13, 20], [13, 21], [12, 20]]]
            ]
        }
        result = MODULE.normalize_feature(self.feature(geometry=geometry), "XYZ")
        self.assertEqual(result["geometry"]["type"], "MultiPolygon")

    def test_missing_name_is_rejected(self):
        feature = self.feature()
        feature["properties"] = {}
        with self.assertRaisesRegex(ValueError, "missing its administrative-unit name"):
            MODULE.normalize_feature(feature, "XYZ")

    def test_non_polygon_geometry_is_rejected(self):
        feature = self.feature()
        feature["geometry"] = {"type": "Point", "coordinates": [10, 20]}
        with self.assertRaisesRegex(ValueError, "unsupported polygon geometry"):
            MODULE.normalize_feature(feature, "XYZ")

    def test_out_of_range_coordinate_is_rejected(self):
        feature = self.feature(geometry={
            "type": "Polygon",
            "coordinates": [[[190, 20], [11, 20], [11, 21], [190, 20]]]
        })
        with self.assertRaisesRegex(ValueError, "invalid or empty coordinates"):
            MODULE.normalize_feature(feature, "XYZ")


if __name__ == "__main__":
    unittest.main()
