"""Tests for texttosolid.profiles (triangulation, extrude, revolve)."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from texttosolid.errors import MeshError
from texttosolid.profiles import (
    circle_profile,
    extrude,
    polygon_area,
    rect_profile,
    revolve,
    triangulate_polygon,
)


class ProfileTests(unittest.TestCase):
    def test_triangulate_square(self):
        tris = triangulate_polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        self.assertEqual(len(tris), 2)

    def test_triangulate_concave(self):
        # L-shaped polygon, area 5, 6 vertices -> 4 triangles
        lshape = [(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)]
        tris = triangulate_polygon(lshape)
        self.assertEqual(len(tris), 4)

    def test_polygon_area_ccw_positive(self):
        self.assertAlmostEqual(polygon_area([(0, 0), (1, 0), (1, 1), (0, 1)]), 1.0)
        self.assertAlmostEqual(polygon_area([(0, 0), (0, 1), (1, 1), (1, 0)]), -1.0)

    def test_triangulate_collinear_raises(self):
        with self.assertRaises(MeshError):
            triangulate_polygon([(0, 0), (1, 1), (2, 2)])

    def test_extrude_square(self):
        mesh = extrude([(-1, -1), (1, -1), (1, 1), (-1, 1)], height=3)
        self.assertAlmostEqual(mesh.volume(), 12.0, places=6)  # area 4 * 3
        self.assertTrue(mesh.is_watertight())
        self.assertEqual(mesh.bounds()[0].z, 0.0)
        self.assertEqual(mesh.bounds()[1].z, 3.0)

    def test_extrude_lshape(self):
        lshape = [(0, 0), (3, 0), (3, 1), (1, 1), (1, 3), (0, 3)]
        mesh = extrude(lshape, height=2)
        self.assertAlmostEqual(mesh.volume(), 5.0 * 2.0, places=6)

    def test_extrude_offset(self):
        mesh = extrude([(-1, -1), (1, -1), (1, 1), (-1, 1)], height=3, at=(0, 0, 5))
        self.assertEqual(mesh.bounds()[0].z, 5.0)
        self.assertEqual(mesh.bounds()[1].z, 8.0)

    def test_extrude_too_few_points(self):
        with self.assertRaises(MeshError):
            extrude([(0, 0), (1, 0)], height=2)

    def test_revolve_tube(self):
        profile = [(3, 0), (5, 0), (5, 10), (3, 10)]
        mesh = revolve(profile, angle=360, segments=48)
        expected = math.pi * (25 - 9) * 10  # pi*(R^2 - r^2)*h
        self.assertAlmostEqual(mesh.volume(), expected, delta=expected * 0.02)
        self.assertTrue(mesh.is_watertight())

    def test_revolve_cone(self):
        # closed triangular profile in (radius, y) space -> a solid cone
        profile = [(0, 0), (5, 0), (0, 10)]
        mesh = revolve(profile, angle=360, segments=48)
        expected = (1.0 / 3.0) * math.pi * 25 * 10
        self.assertTrue(mesh.is_watertight())
        self.assertAlmostEqual(mesh.volume(), expected, delta=expected * 0.02)

    def test_revolve_partial(self):
        profile = [(3, 0), (5, 0), (5, 10), (3, 10)]
        full = revolve(profile, angle=360, segments=48)
        half = revolve(profile, angle=180, segments=48)
        self.assertTrue(half.is_watertight())
        self.assertAlmostEqual(half.volume(), full.volume() / 2.0, delta=full.volume() * 0.05)

    def test_revolve_negative_radius_raises(self):
        with self.assertRaises(MeshError):
            revolve([(-1, 0), (5, 10)], angle=360)

    def test_revolve_bad_angle_raises(self):
        with self.assertRaises(MeshError):
            revolve([(3, 0), (5, 0), (5, 10), (3, 10)], angle=400)

    def test_helpers(self):
        self.assertEqual(len(circle_profile(5, 16)), 16)
        self.assertEqual(len(rect_profile(2, 4)), 4)


if __name__ == "__main__":
    unittest.main()
