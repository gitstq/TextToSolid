"""Tests for texttosolid.primitives."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from texttosolid.errors import MeshError
from texttosolid.primitives import box, cone, cylinder, pyramid, sphere, torus, tube, wedge


class PrimitiveTests(unittest.TestCase):
    def assertClosedVolume(self, mesh, expected, rel=0.02):
        self.assertTrue(mesh.is_watertight(), "{0} is not watertight".format(mesh.name))
        self.assertEqual(mesh.degenerate_faces(), [])
        self.assertAlmostEqual(mesh.volume(), expected, delta=abs(expected) * rel)

    def test_box(self):
        self.assertClosedVolume(box(2, 3, 4), 24.0, rel=1e-9)

    def test_sphere(self):
        self.assertClosedVolume(sphere(r=5, segments=64, rings=32), 4 / 3 * math.pi * 125)

    def test_cylinder(self):
        self.assertClosedVolume(cylinder(r=2, h=5, segments=64), math.pi * 4 * 5)

    def test_cone_sharp(self):
        self.assertClosedVolume(cone(r1=3, r2=0, h=4, segments=64), 1 / 3 * math.pi * 9 * 4)

    def test_cone_frustum(self):
        # frustum volume = pi*h/3 * (r1^2 + r1*r2 + r2^2)
        self.assertClosedVolume(
            cone(r1=3, r2=1, h=4, segments=64), math.pi * 4 / 3 * 13
        )

    def test_torus(self):
        self.assertClosedVolume(
            torus(R=5, r=1, segments=64, tube_segments=24), 2 * math.pi ** 2 * 5 * 1
        )

    def test_wedge(self):
        self.assertClosedVolume(wedge(4, 6, 8), 0.5 * 4 * 8 * 6, rel=1e-9)

    def test_tube(self):
        self.assertClosedVolume(
            tube(r=5, ri=3, h=4, segments=64), math.pi * (25 - 9) * 4
        )

    def test_pyramid(self):
        self.assertClosedVolume(pyramid(base=6, h=9), 6 * 6 * 9 / 3, rel=1e-9)

    def test_at_offset(self):
        mesh = box(1, 1, 1, at=(5, -2, 3))
        self.assertEqual(mesh.center().as_tuple(), (5, -2, 3))
        self.assertAlmostEqual(mesh.volume(), 1.0, places=9)

    def test_color(self):
        mesh = box(1, 1, 1, color=(1.0, 0.0, 0.0))
        self.assertIsNotNone(mesh.colors)
        self.assertEqual(len(mesh.colors), mesh.triangle_count)
        self.assertEqual(mesh.colors[0], (1.0, 0.0, 0.0))

    def test_outward_orientation(self):
        for mesh in (sphere(r=2), cylinder(r=2, h=3), cone(r1=2, r2=1, h=3),
                     torus(R=3, r=1), tube(r=3, ri=1.5, h=2), wedge(2, 2, 2),
                     pyramid(base=3, h=3), box(2, 2, 2)):
            self.assertGreater(mesh.volume(), 0.0, mesh.name)

    def test_invalid_parameters(self):
        with self.assertRaises(MeshError):
            box(0, 1, 1)
        with self.assertRaises(MeshError):
            box(-1, 1, 1)
        with self.assertRaises(MeshError):
            sphere(r=0)
        with self.assertRaises(MeshError):
            sphere(r=1, segments=2)
        with self.assertRaises(MeshError):
            cylinder(r=1, h=0)
        with self.assertRaises(MeshError):
            cylinder(r=1, h=1, segments=2)
        with self.assertRaises(MeshError):
            cone(r1=0, r2=0, h=1)
        with self.assertRaises(MeshError):
            torus(R=0, r=1)
        with self.assertRaises(MeshError):
            tube(r=2, ri=3, h=1)
        with self.assertRaises(MeshError):
            wedge(0, 1, 1)
        with self.assertRaises(MeshError):
            pyramid(base=0, h=1)


if __name__ == "__main__":
    unittest.main()
