"""Tests for the agent JSON protocol (texttosolid.agent)."""
import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from texttosolid.agent import build_from_spec, describe, model_info
from texttosolid.errors import ParseError
from texttosolid.primitives import box


class AgentTests(unittest.TestCase):
    def test_simple_box(self):
        mesh = build_from_spec({"shapes": [{"op": "box", "w": 10, "d": 10, "h": 10}]})
        self.assertAlmostEqual(mesh.volume(), 1000.0, places=6)

    def test_nested_difference(self):
        spec = {
            "shapes": [
                {
                    "op": "difference",
                    "shapes": [
                        {"op": "box", "w": 20, "d": 20, "h": 10},
                        {"op": "cylinder", "r": 3, "h": 40},
                    ],
                }
            ]
        }
        mesh = build_from_spec(spec)
        self.assertTrue(mesh.is_watertight())
        # cylinder axis is Y; the box is 20 deep in Y, so the bore removes pi*9*20
        self.assertAlmostEqual(mesh.volume(), 4000 - math.pi * 9 * 20, delta=40)

    def test_extrude_op(self):
        spec = {
            "shapes": [
                {"op": "extrude", "height": 3, "profile": [[0, 0], [2, 0], [2, 2], [0, 2]]}
            ]
        }
        mesh = build_from_spec(spec)
        self.assertAlmostEqual(mesh.volume(), 12.0, delta=1e-4)

    def test_revolve_op(self):
        spec = {
            "shapes": [
                {
                    "op": "revolve",
                    "angle": 360,
                    "segments": 48,
                    "profile": [[3, 0], [5, 0], [5, 10], [3, 10]],
                }
            ]
        }
        mesh = build_from_spec(spec)
        self.assertAlmostEqual(mesh.volume(), 160 * 3.141592653589793, delta=160 * 0.02)

    def test_model_info(self):
        info = model_info(box(2, 2, 2))
        self.assertEqual(info["triangles"], 12)
        self.assertTrue(info["watertight"])
        self.assertTrue(info["printable"])
        self.assertIn("volume", info)
        # must be JSON serializable
        self.assertIsInstance(json.dumps(info), str)

    def test_describe_mentions_watertight(self):
        text = describe(box(2, 2, 2))
        self.assertIn("watertight", text)

    def test_missing_shapes(self):
        with self.assertRaises(ParseError):
            build_from_spec({"name": "x"})

    def test_unknown_op(self):
        with self.assertRaises(ParseError):
            build_from_spec({"shapes": [{"op": "not_a_thing"}]})


if __name__ == "__main__":
    unittest.main()
