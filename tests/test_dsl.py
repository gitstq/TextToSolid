"""Tests for the TextToSolid DSL (texttosolid.dsl)."""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from texttosolid.dsl import evaluate, parse
from texttosolid.errors import ParseError


class DSLTests(unittest.TestCase):
    def test_simple_box(self):
        mesh = evaluate("box(2, 3, 4)")
        self.assertAlmostEqual(mesh.volume(), 24.0, places=6)
        self.assertTrue(mesh.is_watertight())

    def test_let_and_expression(self):
        mesh = evaluate("let a = 2\nbox(a * 3, a, a)")
        self.assertAlmostEqual(mesh.volume(), 6 * 2 * 2, places=6)

    def test_constants_and_functions(self):
        mesh = evaluate("box(2 * pi, 2, 2)")
        self.assertAlmostEqual(mesh.volume(), 2 * math.pi * 2 * 2, places=6)

    def test_difference_block(self):
        src = """
        difference {
            box(20, 20, 10)
            translate(0, 0, 0) { cylinder(r=3, h=40) }
        }
        """
        mesh = evaluate(src)
        self.assertTrue(mesh.is_watertight())
        self.assertAlmostEqual(mesh.volume(), 4000 - math.pi * 9 * 10, delta=40)

    def test_union_block(self):
        src = """
        union {
            box(2, 2, 2)
            box(2, 2, 2, at=(3, 0, 0))
        }
        """
        mesh = evaluate(src)
        self.assertAlmostEqual(mesh.volume(), 16.0, places=6)

    def test_repeat_rotates_copies(self):
        src = "repeat(4, rotate=(0, 0, 90)) { translate(5, 0, 0) { box(1, 1, 1) } }"
        mesh = evaluate(src)
        self.assertAlmostEqual(mesh.volume(), 4.0, delta=1e-6)
        self.assertTrue(mesh.is_watertight())

    def test_extrude_statement(self):
        src = "extrude(3) { polygon([(0,0),(2,0),(2,2),(0,2)]) }"
        mesh = evaluate(src)
        self.assertAlmostEqual(mesh.volume(), 12.0, delta=1e-4)
        self.assertTrue(mesh.is_watertight())

    def test_revolve_statement(self):
        src = "revolve(360, 48) { polygon([(3,0),(5,0),(5,10),(3,10)]) }"
        mesh = evaluate(src)
        expected = math.pi * (25 - 9) * 10
        self.assertAlmostEqual(mesh.volume(), expected, delta=expected * 0.02)

    def test_color_statement(self):
        mesh = evaluate('color("red") { box(2, 2, 2) }')
        self.assertIsNotNone(mesh.colors)
        self.assertEqual(mesh.colors[0], (0.90, 0.16, 0.22))

    def test_scale_transform(self):
        mesh = evaluate("scale(2) { box(1, 1, 1) }")
        self.assertAlmostEqual(mesh.volume(), 8.0, places=6)

    def test_mirror_transform(self):
        mesh = evaluate('mirror("x") { box(2, 2, 2, at=(3, 0, 0)) }')
        self.assertAlmostEqual(mesh.volume(), 8.0, places=6)
        self.assertEqual(mesh.center().x, -3.0)

    def test_comments_and_blank_lines(self):
        mesh = evaluate("box(2, 2, 2) # a comment\n")
        self.assertAlmostEqual(mesh.volume(), 8.0, places=6)

    def test_parse_returns_statements(self):
        statements = parse("box(1)\nbox(2)")
        self.assertEqual(len(statements), 2)

    # -- error handling --------------------------------------------------- #
    def test_unknown_statement(self):
        with self.assertRaises(ParseError):
            evaluate("frobnicate(1)")

    def test_undefined_variable(self):
        with self.assertRaises(ParseError):
            evaluate("box(missing, 1, 1)")

    def test_transform_needs_block(self):
        with self.assertRaises(ParseError):
            evaluate("translate(1, 0, 0) box(1)")

    def test_profile_at_root(self):
        with self.assertRaises(ParseError):
            evaluate("polygon([(0, 0)])")

    def test_syntax_error_eof(self):
        with self.assertRaises(ParseError):
            evaluate("box(10")

    def test_division_by_zero(self):
        with self.assertRaises(ParseError):
            evaluate("box(1, 1, 5 / 0)")


if __name__ == "__main__":
    unittest.main()
