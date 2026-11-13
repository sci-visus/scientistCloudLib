"""Saved view prefs, the shared transfer window, transects, and streamline seeds."""
import os
import sys
import unittest

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from scientistCloudLib.SCLib_Dashboards.SCDash_openvisus_load import (  # noqa: E402
    apply_openvisus_view_prefs,
    normalize_view_prefs,
    user_owns_dataset,
    view_prefs_to_openvisus_config,
)
from scientistCloudLib.SCLib_Dashboards.SCDash_volume_explorer import (  # noqa: E402
    apply_opacity_window,
    find_velocity,
    fraction_point,
    initial_window,
    clamp_layer,
    layer_count,
    map_offset,
    mask_to_window,
    opacity_nodes,
    palette_family,
    seeds_for_streamlines,
    transect_image,
)


class ViewPrefsTests(unittest.TestCase):
    def test_user_range_becomes_palette_range(self):
        prefs = normalize_view_prefs({
            "direction": "2",
            "offset": "9",
            "timestep": 4,
            "palette": "Inferno256",
            "colormap": "linear",
            "range_mode": "user",
            "range_min": "39",
            "range_max": "34.5",
            "auto_res": "true",
            "ignored": "nope",
        })
        self.assertEqual(prefs["direction"], 2)
        self.assertEqual(prefs["range_min"], 34.5)
        self.assertEqual(prefs["range_max"], 39.0)
        self.assertNotIn("ignored", prefs)
        config = view_prefs_to_openvisus_config("https://example.test/visus.idx", prefs)
        entry = config["datasets"][0]
        self.assertEqual(entry["palette-range"], [34.5, 39.0])
        self.assertEqual(entry["palette"], "Inferno256")
        self.assertEqual(entry["timestep"], 4)
        self.assertEqual(entry["color-mapper-type"], "linear")
        self.assertTrue(entry["view-dep"])

    def test_dynamic_range_is_not_locked(self):
        prefs = normalize_view_prefs({
            "range_mode": "dynamic",
            "range_min": 1,
            "range_max": 2,
        })
        entry = view_prefs_to_openvisus_config("local.idx", prefs)["datasets"][0]
        self.assertNotIn("palette-range", entry)

    def test_owner_check_rejects_public_sessions(self):
        doc = {"user": "owner@example.com", "user_email": "owner@example.com"}
        self.assertTrue(user_owns_dataset(doc, "Owner@Example.com"))
        self.assertFalse(user_owns_dataset(doc, None))
        self.assertFalse(user_owns_dataset(doc, "auth0_session_user"))
        self.assertFalse(user_owns_dataset(doc, "other@example.com"))

    def test_apply_clamps_offset_and_sets_user_range(self):
        class View:
            def __init__(self):
                self.calls = []

            def setDirection(self, value):
                self.calls.append(("direction", value))

            def getOffsetStartEnd(self):
                return 0, 10, 1

            def setOffset(self, value):
                self.calls.append(("offset", value))

            def setPaletteRange(self, value):
                self.calls.append(("range", tuple(value)))

            def setPaletteRangeMode(self, value):
                self.calls.append(("mode", value))

        view = View()
        apply_openvisus_view_prefs(view, {
            "direction": 1,
            "offset": 40,
            "range_mode": "user",
            "range_min": 2,
            "range_max": 8,
        })
        self.assertIn(("direction", 1), view.calls)
        self.assertIn(("offset", 10.0), view.calls)
        self.assertIn(("range", (2.0, 8.0)), view.calls)
        self.assertIn(("mode", "user"), view.calls)


class VolumeExplorerTests(unittest.TestCase):
    def test_velocity_detection(self):
        self.assertEqual(
            find_velocity([
                {"name": "salinity", "ncomponents": 1},
                {"name": "U", "ncomponents": 1},
                {"name": "V", "ncomponents": 1},
                {"name": "W", "ncomponents": 1},
            ]),
            {"kind": "components", "names": ["U", "V", "W"]},
        )
        self.assertEqual(
            find_velocity([{"name": "velocity", "ncomponents": 3}]),
            {"kind": "vector", "names": ["velocity"]},
        )
        self.assertIsNone(find_velocity([{"name": "salinity", "ncomponents": 1}]))

    def test_transect_reads_depth(self):
        volume = np.zeros((4, 5, 6), dtype=np.float32)
        for depth in range(6):
            volume[:, :, depth] = depth
        image = transect_image(volume, 2, (0, 0), (3, 4), samples=4)
        self.assertEqual(image.shape, (6, 4))
        self.assertTrue(np.allclose(image[:, 0], np.arange(6)))
        self.assertTrue(np.allclose(image[:, -1], np.arange(6)))

    def test_window_hides_outside_values(self):
        image = np.array([[0.0, 5.0], [10.0, 15.0]], dtype=np.float32)
        masked = mask_to_window(image, 4, 11)
        self.assertTrue(np.isnan(masked[0, 0]))
        self.assertTrue(np.isnan(masked[1, 1]))
        self.assertEqual(float(masked[0, 1]), 5.0)
        windowed, nodata = apply_opacity_window(image, 4, 11)
        self.assertLess(nodata, 4)
        self.assertEqual(float(windowed[0, 0]), nodata)
        self.assertEqual(float(windowed[0, 1]), 5.0)
        nodes = opacity_nodes(nodata, 4, 11)
        self.assertEqual(nodes[0]["y"], 0.0)
        self.assertEqual(nodes[1]["x"], 4.0)

    def test_saved_window_and_seeds(self):
        vmin, vmax = initial_window(
            {"range_mode": "user", "range_min": 34.5, "range_max": 39},
            0,
            100,
        )
        self.assertEqual((vmin, vmax), (34.5, 39.0))
        self.assertEqual(palette_family("Inferno256"), "Inferno")
        self.assertEqual(map_offset(10, 21, 11), 5)
        self.assertEqual(layer_count((320, 240, 80), 2), 80)
        self.assertEqual(layer_count((320, 240, 80), 0), 320)
        self.assertEqual(clamp_layer(80, 80), 79)
        self.assertEqual(clamp_layer(12, 80), 12)
        point = fraction_point((0, 10), (1, 11), (1, 21, 5), 0)
        self.assertEqual(point[0], 0.0)
        seeds = seeds_for_streamlines((8, 8, 8), 2, 3, (1, 1), (4, 2), rake=3)
        self.assertEqual(len(seeds), 3)
        self.assertTrue(all(seed[2] == 3 for seed in seeds))
        rake = seeds_for_streamlines((9, 9, 9), 2, 1)
        self.assertGreaterEqual(len(rake), 2)


if __name__ == "__main__":
    unittest.main()
