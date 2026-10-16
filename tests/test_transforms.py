"""Tests for texttosolid.transforms."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from texttosolid.primitives import box
from texttosolid.transforms import mirror, rotate, scale, translate


class TransformTests(unittest.TestCase):
    def test_translate_moves_center(self):
        mesh = translate(box(2, 2, 2), 5, 0, 0)
        self.assertEqual(mesh.center().as_tuple(), (5, 0, 0))
        self.assertAlmostEqual(mesh.volume(), 8.0, places=9)
        self.assertTrue(mesh.is_watertight())

    def test_translate_zero_is_copy(self):
        base = box(2, 2, 2)
        moved = translate(base, 0, 0, 0)
        self.assertAlmostEqual(moved.volume(), base.volume())
        self.assertIsNot(moved, base)

    def test_rotate_swaps_axes(self):
        # box(4, 2, 2) is long in X; a 90deg rotation about Z makes it long in Y
        mesh = rotate(box(4, 2, 2), 0, 0, 90)
        size = mesh.size()
        self.assertAlmostEqual(size.x, 2.0, places=6)
        self.assertAlmostEqual(size.y, 4.0, places=6)
        self.assertAlmostEqual(size.z, 2.0, places=6)
        self.assertAlmostEqual(mesh.volume(), 16.0, places=6)

    def test_rotate_about_x(self):
        mesh = rotate(box(2, 4, 2), 90, 0, 0)
        size = mesh.size()
        self.assertAlmostEqual(size.x, 2.0, places=6)
        self.assertAlmostEqual(size.y, 2.0, places=6)
        self.assertAlmostEqual(size.z, 4.0, places=6)

    def test_scale_uniform(self):
        mesh = scale(box(1, 1, 1), 2)
        self.assertAlmostEqual(mesh.volume(), 8.0, places=9)
        size = mesh.size()
        self.assertEqual((size.x, size.y, size.z), (2.0, 2.0, 2.0))

    def test_scale_per_axis(self):
        mesh = scale(box(2, 2, 2), (2, 1, 1))
        self.assertAlmostEqual(mesh.volume(), 16.0, places=9)
        size = mesh.size()
        self.assertEqual((size.x, size.y, size.z), (4.0, 2.0, 2.0))

    def test_scale_zero_rejected(self):
        with self.assertRaises(ValueError):
            scale(box(1, 1, 1), 0)

    def test_mirror_reflects(self):
        mesh = mirror(box(2, 2, 2, at=(3, 0, 0)), "x")
        self.assertEqual(mesh.center().as_tuple(), (-3, 0, 0))
        self.assertAlmostEqual(mesh.volume(), 8.0, places=9)
        self.assertTrue(mesh.is_watertight())

    def test_mirror_centered_preserves(self):
        mesh = mirror(box(2, 2, 2), "z")
        self.assertAlmostEqual(mesh.volume(), 8.0, places=9)
        self.assertTrue(mesh.is_watertight())

    def test_mirror_bad_axis(self):
        with self.assertRaises(ValueError):
            mirror(box(1, 1, 1), "q")


if __name__ == "__main__":
    unittest.main()
