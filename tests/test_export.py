"""Tests for texttosolid.export (STL / OBJ / SVG)."""
import os
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from texttosolid.errors import ExportError
from texttosolid.export import (
    mesh_to_obj,
    mesh_to_stl_ascii,
    mesh_to_stl_binary,
    mesh_to_svg,
    save,
)
from texttosolid.primitives import box


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.mesh = box(2, 2, 2)
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        for name in os.listdir(self.tmp):
            try:
                os.remove(os.path.join(self.tmp, name))
            except OSError:
                pass
        try:
            os.rmdir(self.tmp)
        except OSError:
            pass

    def test_stl_binary_layout(self):
        data = mesh_to_stl_binary(self.mesh)
        self.assertEqual(len(data), 84 + 50 * self.mesh.triangle_count)
        self.assertEqual(data[:11], b"TextToSolid")
        count = struct.unpack("<I", data[80:84])[0]
        self.assertEqual(count, self.mesh.triangle_count)

    def test_stl_ascii(self):
        text = mesh_to_stl_ascii(self.mesh)
        self.assertTrue(text.startswith("solid "))
        self.assertIn("endsolid", text)
        self.assertIn("facet normal", text)
        self.assertEqual(text.count("outer loop"), self.mesh.triangle_count)

    def test_obj(self):
        text = mesh_to_obj(self.mesh)
        self.assertEqual(text.count("\nv "), self.mesh.vertex_count)
        self.assertEqual(text.count("\nf "), self.mesh.triangle_count)

    def test_svg_contains_polygons(self):
        text = mesh_to_svg(self.mesh)
        self.assertIn("<svg", text)
        self.assertIn("</svg>", text)
        self.assertGreaterEqual(text.count("<polygon"), 10)

    def test_save_dispatch(self):
        for ext in ("stl", "obj", "svg"):
            path = os.path.join(self.tmp, "model." + ext)
            save(self.mesh, path)
            self.assertTrue(os.path.exists(path))
            self.assertGreater(os.path.getsize(path), 0)
        # ASCII STL
        path = os.path.join(self.tmp, "model_ascii.stl")
        save(self.mesh, path, ascii=True)
        with open(path, "r", encoding="utf-8") as handle:
            self.assertTrue(handle.read().startswith("solid "))

    def test_save_unsupported_extension(self):
        path = os.path.join(self.tmp, "model.xyz")
        with self.assertRaises(ExportError):
            save(self.mesh, path)


if __name__ == "__main__":
    unittest.main()
