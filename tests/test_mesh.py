"""Tests for texttosolid.mesh."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from texttosolid.mesh import Mesh
from texttosolid.primitives import box
from texttosolid.vec import Vec3


class MeshTests(unittest.TestCase):
    def setUp(self):
        self.cube = box(20, 20, 10)

    def test_counts(self):
        self.assertEqual(self.cube.triangle_count, 12)
        self.assertEqual(self.cube.vertex_count, 8)

    def test_volume_and_area(self):
        self.assertAlmostEqual(self.cube.volume(), 4000.0, places=6)
        # 2 * (20*20 + 20*10 + 20*10)
        self.assertAlmostEqual(self.cube.surface_area(), 1600.0, places=6)

    def test_bounds_size_center(self):
        low, high = self.cube.bounds()
        self.assertEqual(low.as_tuple(), (-10, -10, -5))
        self.assertEqual(high.as_tuple(), (10, 10, 5))
        size = self.cube.size()
        self.assertEqual(size.as_tuple(), (20, 20, 10))
        self.assertEqual(self.cube.center().as_tuple(), (0, 0, 0))

    def test_watertight_and_degenerate(self):
        self.assertTrue(self.cube.is_watertight())
        self.assertEqual(self.cube.non_manifold_edges(), [])
        self.assertEqual(self.cube.degenerate_faces(), [])

    def test_empty_mesh(self):
        empty = Mesh.empty()
        self.assertTrue(empty.is_empty())
        self.assertFalse(empty.is_watertight())
        self.assertEqual(empty.volume(), 0.0)
        self.assertIsNone(empty.bounds())
        self.assertIsNone(empty.center())

    def test_fix_orientation_flips_inside_out(self):
        flipped = self.cube.copy()
        flipped.faces = [(k, j, i) for (i, j, k) in flipped.faces]
        self.assertLess(flipped.volume(), 0.0)
        flipped.fix_orientation()
        self.assertGreater(flipped.volume(), 0.0)
        self.assertTrue(flipped.is_watertight())

    def test_merge(self):
        merged = box(10, 10, 10).merge(box(10, 10, 10, at=(50, 0, 0)))
        self.assertEqual(merged.triangle_count, 24)
        self.assertEqual(merged.vertex_count, 16)
        self.assertAlmostEqual(merged.volume(), 2000.0, places=6)
        self.assertTrue(merged.is_watertight())

    def test_merge_with_colors(self):
        red = box(1, 1, 1, color=(1, 0, 0))
        green = box(1, 1, 1, at=(5, 0, 0), color=(0, 1, 0))
        merged = red.merge(green)
        self.assertIsNotNone(merged.colors)
        self.assertEqual(len(merged.colors), 24)
        self.assertEqual(merged.colors[0], (1, 0, 0))
        self.assertEqual(merged.colors[-1], (0, 1, 0))

    def test_weld_merges_duplicates(self):
        # a quad stored with every vertex duplicated
        mesh = Mesh(
            vertices=[
                Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(1, 1, 0), Vec3(0, 1, 0),
                Vec3(0, 0, 0), Vec3(1, 0, 0), Vec3(1, 1, 0), Vec3(0, 1, 0),
            ],
            faces=[(0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7)],
        )
        mesh.weld()
        self.assertEqual(mesh.vertex_count, 4)
        self.assertEqual(mesh.triangle_count, 2)

    def test_face_normal(self):
        for face in self.cube.faces:
            n = self.cube.face_normal(face)
            self.assertAlmostEqual(n.length(), 1.0, places=6)
            self.assertNotEqual(n.length_sq(), 0.0)


if __name__ == "__main__":
    unittest.main()
