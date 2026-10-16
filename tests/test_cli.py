"""Tests for the TextToSolid command line interface (texttosolid.cli)."""
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from texttosolid.cli import main

SIMPLE_T2S = "box(10, 10, 10)\n"
GEAR_T2S = None  # filled from built-in example below


class CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.src = os.path.join(self.tmp, "model.t2s")
        with open(self.src, "w", encoding="utf-8") as handle:
            handle.write(SIMPLE_T2S)
        self.spec = os.path.join(self.tmp, "model.json")
        with open(self.spec, "w", encoding="utf-8") as handle:
            json.dump({"shapes": [{"op": "box", "w": 5, "d": 5, "h": 5}]}, handle)

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

    def test_build(self):
        out = os.path.join(self.tmp, "out.stl")
        code = main(["build", self.src, "-o", out])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(out))
        self.assertGreater(os.path.getsize(out), 84)

    def test_validate(self):
        self.assertEqual(main(["validate", self.src]), 0)

    def test_info_json(self):
        buf = io.StringIO()
        with __import__("contextlib").redirect_stdout(buf):
            code = main(["info", self.src, "--json"])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["triangles"], 12)

    def test_check(self):
        self.assertEqual(main(["check", self.src]), 0)

    def test_preview(self):
        out = os.path.join(self.tmp, "preview.svg")
        code = main(["preview", self.src, "-o", out])
        self.assertEqual(code, 0)
        with open(out, "r", encoding="utf-8") as handle:
            self.assertIn("<svg", handle.read())

    def test_example_build(self):
        out = os.path.join(self.tmp, "gear.stl")
        code = main(["example", "gear", "-o", out])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(out))

    def test_examples_list(self):
        self.assertEqual(main(["examples"]), 0)

    def test_missing_file(self):
        self.assertEqual(main(["build", os.path.join(self.tmp, "nope.t2s")]), 2)

    def test_no_command(self):
        self.assertEqual(main([]), 0)

    def test_spec_build(self):
        out = os.path.join(self.tmp, "fromspec.obj")
        code = main(["spec", self.spec, "-o", out])
        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
