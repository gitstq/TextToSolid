"""Tests for texttosolid.csg boolean operations."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from texttosolid.csg import intersect, subtract, subtract_all, union, union_all
from texttosolid.primitives import box, cylinder


class CSGTests(unittest.TestCase):
    def test_union_disjoint(self):
        a = box(10, 10, 10)
        b = box(10, 10, 10, at=(30, 0, 0))
        result = union(a, b)
        self.assertAlmostEqual(result.volume(), 2000.0, places=6)
        self.assertTrue(result.is_watertight())

    def test_union_overlap(self):
        a = box(10, 10, 10)
        b = box(10, 10, 10, at=(5, 0, 0))  # overlap = 5*10*10 = 500
        result = union(a, b)
        self.assertAlmostEqual(result.volume(), 1500.0, delta=1e-6)

    def test_subtract_cylinder_from_box(self):
        a = box(10, 10, 10)
        b = cylinder(r=2, h=20, segments=64)
        result = subtract(a, b)
        self.assertTrue(result.is_watertight())
        self.assertAlmostEqual(result.volume(), 1000 - math.pi * 4 * 10, delta=10)

    def test_intersect_boxes(self):
        a = box(10, 10, 10)
        b = box(10, 10, 10, at=(5, 0, 0))  # overlap = 5*10*10 = 500
        result = intersect(a, b)
        self.assertTrue(result.is_watertight())
        self.assertAlmostEqual(result.volume(), 500.0, delta=1e-6)

    def test_subtract_to_empty(self):
        a = box(5, 5, 5)
        b = box(20, 20, 20)
        result = subtract(a, b)
        self.assertTrue(result.is_empty())
        self.assertEqual(result.triangle_count, 0)

    def test_union_all(self):
        meshes = [
            box(10, 10, 10),
            box(10, 10, 10, at=(30, 0, 0)),
            box(10, 10, 10, at=(0, 30, 0)),
        ]
        result = union_all(meshes)
        self.assertAlmostEqual(result.volume(), 3000.0, places=6)

    def test_subtract_all_two_holes(self):
        base = box(20, 20, 20)
        # two separate columns along Y, offset in X so they do not overlap
        cutters = [
            cylinder(r=2, h=40, segments=64, at=(-5, 0, 0)),
            cylinder(r=2, h=40, segments=64, at=(5, 0, 0)),
        ]
        result = subtract_all(base, cutters)
        self.assertTrue(result.is_watertight())
        # cylinder axis is Y; each bore removes pi*4*20 through the 20-deep box
        expected = 8000 - 2 * (math.pi * 4 * 20)
        self.assertAlmostEqual(result.volume(), expected, delta=15)

    def test_union_preserves_colors(self):
        a = box(1, 1, 1, color=(1, 0, 0))
        b = box(1, 1, 1, at=(5, 0, 0), color=(0, 0, 1))
        result = union(a, b)
        self.assertIsNotNone(result.colors)
        self.assertEqual(len(result.colors), result.triangle_count)

    def test_results_have_positive_volume(self):
        a = box(10, 10, 10)
        b = box(10, 10, 10, at=(3, 0, 0))
        for op in (union, subtract, intersect):
            self.assertGreater(op(a, b).volume(), 0.0)


if __name__ == "__main__":
    unittest.main()
