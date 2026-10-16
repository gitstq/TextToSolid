"""Tests for texttosolid.vec."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from texttosolid.vec import Vec3


class Vec3Tests(unittest.TestCase):
    def test_arithmetic(self):
        a = Vec3(1, 2, 3)
        b = Vec3(4, 5, 6)
        self.assertEqual((a + b).as_tuple(), (5, 7, 9))
        self.assertEqual((b - a).as_tuple(), (3, 3, 3))
        self.assertEqual((a * 2).as_tuple(), (2, 4, 6))
        self.assertEqual((2 * a).as_tuple(), (2, 4, 6))
        self.assertEqual((b / 2).as_tuple(), (2, 2.5, 3))
        self.assertEqual((-a).as_tuple(), (-1, -2, -3))

    def test_products(self):
        a = Vec3(1, 0, 0)
        b = Vec3(0, 1, 0)
        self.assertEqual(a.dot(b), 0.0)
        self.assertEqual(a.cross(b).as_tuple(), (0, 0, 1))

    def test_metrics(self):
        v = Vec3(3, 4, 0)
        self.assertEqual(v.length_sq(), 25.0)
        self.assertEqual(v.length(), 5.0)
        self.assertEqual(v.normalized().as_tuple(), (0.6, 0.8, 0.0))
        self.assertEqual(Vec3(0, 0, 0).normalized().as_tuple(), (0.0, 0.0, 0.0))
        self.assertAlmostEqual(Vec3(0, 0, 0).distance_to(Vec3(0, 3, 4)), 5.0)

    def test_lerp_and_protocol(self):
        a = Vec3(0, 0, 0)
        b = Vec3(10, 0, 0)
        self.assertEqual(a.lerp(b, 0.5).as_tuple(), (5, 0, 0))
        self.assertEqual(tuple(a), (0.0, 0.0, 0.0))
        self.assertEqual(a[1], 0.0)
        self.assertEqual(len(a), 3)
        self.assertEqual(a, Vec3(0, 0, 0))
        self.assertNotEqual(a, b)
        self.assertEqual(hash(a), hash(Vec3(0, 0, 0)))
        self.assertIn("Vec3", repr(a))


if __name__ == "__main__":
    unittest.main()
