"""The TextToSolid DSL — a small text language for parametric solids.

Example::

    let wall = 2
    difference {
        box(40, 20, wall)
        translate(0, 0, -1) { cylinder(r=3, h=wall + 2) }
    }

The module is intentionally self-contained: tokenizer, recursive-descent
parser and a safe expression evaluator (no ``eval``, no third-party deps).
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple, Union

from . import csg, profiles as prof
from .errors import MeshError, ParseError
from .mesh import Mesh, RGB
from .primitives import box, cone, cylinder, pyramid, sphere, torus, tube, wedge
from .transforms import mirror, rotate, scale, translate

__all__ = ["evaluate", "parse", "Profile", "NAMED_COLORS"]

Point2 = Tuple[float, float]


class Profile:
    """A 2D sketch produced by ``polygon`` / ``circle`` / ``square`` / ``rect``."""

    __slots__ = ("points",)

    def __init__(self, points: Sequence[Point2]) -> None:
        self.points: List[Point2] = [(float(x), float(y)) for x, y in points]


# ---------------------------------------------------------------------- #
# named colors                                                           #
# ---------------------------------------------------------------------- #
NAMED_COLORS: Dict[str, RGB] = {
    "red": (0.90, 0.16, 0.22),
    "green": (0.18, 0.65, 0.32),
    "blue": (0.20, 0.40, 0.90),
    "yellow": (0.98, 0.80, 0.18),
    "orange": (0.98, 0.55, 0.15),
    "purple": (0.55, 0.30, 0.85),
    "violet": (0.62, 0.35, 0.88),
    "pink": (0.98, 0.55, 0.75),
    "black": (0.08, 0.08, 0.09),
    "white": (0.95, 0.95, 0.96),
    "gray": (0.55, 0.56, 0.58),
    "grey": (0.55, 0.56, 0.58),
    "cyan": (0.20, 0.80, 0.90),
    "magenta": (0.90, 0.25, 0.70),
    "brown": (0.45, 0.30, 0.18),
    "teal": (0.10, 0.65, 0.62),
    "navy": (0.10, 0.20, 0.50),
    "olive": (0.45, 0.48, 0.15),
    "maroon": (0.55, 0.12, 0.22),
    "lime": (0.65, 0.90, 0.20),
    "gold": (0.95, 0.75, 0.25),
    "silver": (0.78, 0.80, 0.82),
    "coral": (0.98, 0.50, 0.40),
    "salmon": (0.95, 0.60, 0.50),
    "crimson": (0.80, 0.10, 0.22),
    "indigo": (0.30, 0.25, 0.75),
    "turquoise": (0.20, 0.82, 0.80),
    "steel": (0.45, 0.52, 0.60),
    "copper": (0.80, 0.48, 0.30),
    "bronze": (0.80, 0.60, 0.30),
}


def _parse_color(value) -> RGB:
    """Accept ``"#rgb"``, ``"#rrggbb"``, a named color or an ``(r, g, b)`` tuple."""
    if isinstance(value, str):
        text = value.strip().lower()
        if text in NAMED_COLORS:
            return NAMED_COLORS[text]
        if text.startswith("#"):
            text = text[1:]
        if len(text) == 3:
            try:
                return tuple(int(c * 2, 16) / 255.0 for c in text)  # type: ignore[return-value]
            except ValueError:
                raise ParseError("invalid hex color: {0!r}".format(value))
        if len(text) == 6:
            try:
                return (
                    int(text[0:2], 16) / 255.0,
                    int(text[2:4], 16) / 255.0,
                    int(text[4:6], 16) / 255.0,
                )
            except ValueError:
                raise ParseError("invalid hex color: {0!r}".format(value))
        raise ParseError("unknown color name: {0!r}".format(value))
    if isinstance(value, (tuple, list)) and len(value) == 3:
        try:
            rgb = tuple(min(1.0, max(0.0, float(c))) for c in value)
        except (TypeError, ValueError):
            raise ParseError("invalid RGB color: {0!r}".format(value))
        return rgb  # type: ignore[return-value]
    raise ParseError("invalid color: {0!r}".format(value))


# ---------------------------------------------------------------------- #
# tokenizer                                                              #
# ---------------------------------------------------------------------- #
class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind: str, value: str, line: int) -> None:
        self.kind = kind  # "num" | "ident" | "string" | "op"
        self.value = value
        self.line = line

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "Token({0}, {1!r}, line={2})".format(self.kind, self.value, self.line)


def tokenize(source: str) -> List[Token]:
    tokens: List[Token] = []
    i = 0
    line = 1
    n = len(source)
    while i < n:
        ch = source[i]
        if ch == "\n":
            line += 1
            i += 1
            continue
        if ch in " \t\r":
            i += 1
            continue
        if ch == "#":  # comment until end of line
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and source[i + 1].isdigit()):
            start = i
            while i < n and (source[i].isdigit() or source[i] in ".eE"):
                # allow exponent sign
                if source[i] in "eE" and i + 1 < n and source[i + 1] in "+-":
                    i += 1
                i += 1
            text = source[start:i]
            try:
                float(text)
            except ValueError:
                raise ParseError("invalid number {0!r} on line {1}".format(text, line))
            tokens.append(Token("num", text, line))
            continue
        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (source[i].isalnum() or source[i] == "_"):
                i += 1
            tokens.append(Token("ident", source[start:i], line))
            continue
        if ch in "\"'":
            quote = ch
            i += 1
            start = i
            while i < n and source[i] != quote:
                if source[i] == "\n":
                    raise ParseError("unterminated string on line {0}".format(line))
                i += 1
            if i >= n:
                raise ParseError("unterminated string on line {0}".format(line))
            tokens.append(Token("string", source[start:i], line))
            i += 1
            continue
        if ch in "(){}[],=;+-*/%^":
            tokens.append(Token("op", ch, line))
            i += 1
            continue
        raise ParseError("unexpected character {0!r} on line {1}".format(ch, line))
    tokens.append(Token("eof", "", line))
    return tokens


# ---------------------------------------------------------------------- #
# expression AST + parser                                                #
# ---------------------------------------------------------------------- #
# expression nodes are plain tuples:
#   ("num", value) | ("var", name) | ("unary", op, node) |
#   ("bin", op, left, right) | ("call", fname, [args])
ExprNode = tuple


class ExprParser:
    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    # -- helpers -------------------------------------------------------- #
    def peek(self) -> Token:
        return self.tokens[self.pos]

    def next(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect_op(self, op: str) -> Token:
        tok = self.peek()
        if tok.kind == "op" and tok.value == op:
            return self.next()
        raise ParseError(
            "expected {0!r} but found {1!r} on line {2}".format(op, tok.value, tok.line)
        )

    def at_op(self, op: str) -> bool:
        tok = self.peek()
        return tok.kind == "op" and tok.value == op

    # -- grammar -------------------------------------------------------- #
    def parse_expression(self) -> ExprNode:
        node = self.parse_term()
        while self.at_op("+") or self.at_op("-"):
            op = self.next().value
            node = ("bin", op, node, self.parse_term())
        return node

    def parse_term(self) -> ExprNode:
        node = self.parse_unary()
        while self.at_op("*") or self.at_op("/") or self.at_op("%"):
            op = self.next().value
            node = ("bin", op, node, self.parse_unary())
        return node

    def parse_unary(self) -> ExprNode:
        if self.at_op("-") or self.at_op("+"):
            op = self.next().value
            return ("unary", op, self.parse_unary())
        return self.parse_power()

    def parse_power(self) -> ExprNode:
        base = self.parse_atom()
        if self.at_op("^"):
            self.next()
            exponent = self.parse_unary()  # right associative
            return ("bin", "^", base, exponent)
        return base

    def parse_atom(self) -> ExprNode:
        tok = self.peek()
        if tok.kind == "num":
            self.next()
            return ("num", float(tok.value))
        if tok.kind == "ident":
            self.next()
            if self.at_op("("):
                self.next()
                args: List[ExprNode] = []
                if not self.at_op(")"):
                    args.append(self.parse_expression())
                    while self.at_op(","):
                        self.next()
                        if self.at_op(")"):
                            break
                        args.append(self.parse_expression())
                self.expect_op(")")
                return ("call", tok.value, args)
            return ("var", tok.value)
        if tok.kind == "op" and tok.value == "(":
            self.next()
            node = self.parse_expression()
            self.expect_op(")")
            return node
        raise ParseError(
            "unexpected token {0!r} on line {1}".format(tok.value, tok.line)
        )


# ---------------------------------------------------------------------- #
# expression evaluation                                                   #
# ---------------------------------------------------------------------- #
_FUNCTIONS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "atan2": math.atan2,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "abs": abs,
    "min": min,
    "max": max,
    "floor": math.floor,
    "ceil": math.ceil,
    "round": round,
    "hypot": math.hypot,
    "sign": lambda x: 0.0 if x == 0 else math.copysign(1.0, x),
}

_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def eval_expr(node: ExprNode, variables: Dict[str, float], line: int = 0) -> float:
    kind = node[0]
    if kind == "num":
        return float(node[1])
    if kind == "var":
        name = node[1]
        if name in variables:
            return float(variables[name])
        if name in _CONSTANTS:
            return _CONSTANTS[name]
        raise ParseError("undefined variable {0!r} (line {1})".format(name, line))
    if kind == "unary":
        value = eval_expr(node[2], variables, line)
        return -value if node[1] == "-" else value
    if kind == "bin":
        left = eval_expr(node[2], variables, line)
        right = eval_expr(node[3], variables, line)
        op = node[1]
        try:
            if op == "+":
                return left + right
            if op == "-":
                return left - right
            if op == "*":
                return left * right
            if op == "/":
                return left / right
            if op == "%":
                return math.fmod(left, right)
            if op == "^":
                return left ** right
        except ZeroDivisionError:
            raise ParseError("division by zero (line {0})".format(line))
        except (OverflowError, ValueError):
            raise ParseError("invalid arithmetic (line {0})".format(line))
    if kind == "call":
        fname = node[1]
        func = _FUNCTIONS.get(fname)
        if func is None:
            raise ParseError("unknown function {0!r} (line {1})".format(fname, line))
        args = [eval_expr(a, variables, line) for a in node[2]]
        try:
            return float(func(*args))
        except (ValueError, TypeError) as exc:
            raise ParseError("bad call to {0}() (line {1}): {2}".format(fname, line, exc))
    raise ParseError("cannot evaluate expression (line {0})".format(line))


# ---------------------------------------------------------------------- #
# statement parser                                                        #
# ---------------------------------------------------------------------- #
PRIMITIVES = {
    "box": (["w", "d", "h"], box),
    "sphere": (["r", "segments", "rings"], sphere),
    "cylinder": (["r", "h", "segments"], cylinder),
    "cone": (["r1", "r2", "h", "segments"], cone),
    "torus": (["R", "r", "segments", "tube_segments"], torus),
    "wedge": (["w", "d", "h"], wedge),
    "tube": (["r", "ri", "h", "segments"], tube),
    "pyramid": (["base", "h"], pyramid),
}

TRANSFORMS = ("translate", "rotate", "scale", "mirror")
CSG_OPS = ("union", "difference", "intersection")
PROFILE_OPS = ("polygon", "circle", "square", "rect")
STATEMENTS = set(PRIMITIVES) | set(TRANSFORMS) | set(CSG_OPS) | {"color", "extrude", "revolve", "repeat"} | set(PROFILE_OPS)


class Statement:
    __slots__ = ("kind", "name", "args", "block", "line")

    def __init__(self, kind: str, name: str, args: List[tuple], block, line: int) -> None:
        self.kind = kind  # "let" | "call"
        self.name = name
        self.args = args
        self.block = block
        self.line = line

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "Statement({0}, {1}, args={2}, block={3})".format(
            self.kind, self.name, len(self.args), "yes" if self.block else "no"
        )


def parse(source: str) -> List[Statement]:
    """Parse TextToSolid source into a list of statements (raises ParseError)."""
    tokens = tokenize(source)
    parser = _StatementParser(tokens)
    return parser.parse_program()


class _StatementParser:
    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[self.pos]

    def next(self) -> Token:
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def at_op(self, op: str) -> bool:
        tok = self.peek()
        return tok.kind == "op" and tok.value == op

    def parse_program(self) -> List[Statement]:
        statements: List[Statement] = []
        while True:
            while self.at_op(";"):
                self.next()
            if self.peek().kind == "eof":
                break
            statements.append(self.parse_statement())
        return statements

    def parse_statement(self) -> Statement:
        tok = self.peek()
        if tok.kind == "ident" and tok.value == "let":
            self.next()
            name_tok = self.next()
            if name_tok.kind != "ident":
                raise ParseError("expected variable name after 'let' on line {0}".format(tok.line))
            self._expect_op("=", tok.line)
            expr = self._parse_expr_from()
            return Statement("let", name_tok.value, [("expr", expr)], None, tok.line)
        if tok.kind != "ident":
            raise ParseError(
                "expected a statement but found {0!r} on line {1}".format(tok.value, tok.line)
            )
        name = tok.value
        line = tok.line
        self.next()
        args: List[tuple] = []
        if self.at_op("("):
            args = self._parse_args()
        block = None
        if self.at_op("{"):
            block = self._parse_block()
        if name not in STATEMENTS:
            raise ParseError("unknown statement {0!r} on line {1}".format(name, line))
        return Statement("call", name, args, block, line)

    # -- argument lists -------------------------------------------------- #
    def _parse_args(self) -> List[tuple]:
        self._expect_op("(", self.peek().line)
        args: List[tuple] = []
        if not self.at_op(")"):
            args.append(self._parse_arg())
            while self.at_op(","):
                self.next()
                if self.at_op(")"):
                    break
                args.append(self._parse_arg())
        self._expect_op(")", self.peek().line)
        return args

    def _parse_arg(self) -> tuple:
        # named argument:  ident = value
        if self.peek().kind == "ident" and self._lookahead_is_assign():
            name_tok = self.next()
            self.next()  # '='
            return ("kw", name_tok.value, self._parse_value())
        return ("expr", self._parse_value())

    def _lookahead_is_assign(self) -> bool:
        # peek: ident followed by '='
        if self.pos + 1 < len(self.tokens):
            nxt = self.tokens[self.pos + 1]
            return nxt.kind == "op" and nxt.value == "="
        return False

    def _parse_value(self):
        """Parse an argument value: expression, point list or string."""
        tok = self.peek()
        if tok.kind == "string":
            self.next()
            return ("string", tok.value)
        if self.at_op("["):
            return ("points", self._parse_point_list())
        if self.at_op("("):
            return ("vec3", self._parse_vec3())
        return ("expr", self._parse_expr_from())

    def _parse_point_list(self) -> List[Tuple[ExprNode, ExprNode]]:
        self._expect_op("[", self.peek().line)
        points: List[Tuple[ExprNode, ExprNode]] = []
        if not self.at_op("]"):
            points.append(self._parse_point())
            while self.at_op(","):
                self.next()
                if self.at_op("]"):
                    break
                points.append(self._parse_point())
        self._expect_op("]", self.peek().line)
        return points

    def _parse_point(self) -> Tuple[ExprNode, ExprNode]:
        self._expect_op("(", self.peek().line)
        x = self._parse_expr_from()
        self._expect_op(",", self.peek().line)
        y = self._parse_expr_from()
        self._expect_op(")", self.peek().line)
        return (x, y)

    def _parse_vec3(self) -> Tuple[ExprNode, ExprNode, ExprNode]:
        self._expect_op("(", self.peek().line)
        x = self._parse_expr_from()
        self._expect_op(",", self.peek().line)
        y = self._parse_expr_from()
        self._expect_op(",", self.peek().line)
        z = self._parse_expr_from()
        self._expect_op(")", self.peek().line)
        return (x, y, z)

    def _parse_expr_from(self) -> ExprNode:
        """Parse an expression using the shared token stream."""
        sub = ExprParser(self.tokens[self.pos:])
        node = sub.parse_expression()
        self.pos += sub.pos
        return node

    def _parse_block(self) -> List[Statement]:
        self._expect_op("{", self.peek().line)
        statements: List[Statement] = []
        while True:
            while self.at_op(";"):
                self.next()
            if self.at_op("}"):
                self.next()
                break
            if self.peek().kind == "eof":
                raise ParseError("unexpected end of file: missing '}}'")
            statements.append(self.parse_statement())
        return statements

    def _expect_op(self, op: str, line: int) -> None:
        tok = self.peek()
        if tok.kind == "op" and tok.value == op:
            self.next()
            return
        raise ParseError(
            "expected {0!r} but found {1!r} on line {2}".format(op, tok.value, tok.line or line)
        )


# ---------------------------------------------------------------------- #
# evaluator                                                               #
# ---------------------------------------------------------------------- #
def _eval_points(node, variables: Dict[str, float], line: int) -> List[Point2]:
    if node[0] != "points":
        raise ParseError("expected a point list like [(x, y), ...] on line {0}".format(line))
    return [
        (eval_expr(x, variables, line), eval_expr(y, variables, line))
        for x, y in node[1]
    ]


def _eval_vec3(node, variables: Dict[str, float], line: int) -> Tuple[float, float, float]:
    if node[0] == "vec3":
        return tuple(eval_expr(c, variables, line) for c in node[1])  # type: ignore[return-value]
    raise ParseError("expected a 3D point like (x, y, z) on line {0}".format(line))


def _eval_value(node, variables: Dict[str, float], line: int):
    kind = node[0]
    if kind == "expr":
        return eval_expr(node[1], variables, line)
    if kind == "string":
        return node[1]
    if kind == "points":
        return _eval_points(node, variables, line)
    if kind == "vec3":
        return _eval_vec3(node, variables, line)
    raise ParseError("invalid argument on line {0}".format(line))


def _collect_args(
    statement: Statement, positional_names: List[str], allowed_kwargs: Sequence[str]
) -> Tuple[Dict[str, object], Dict[str, object]]:
    """Split statement arguments into positional values and keyword values."""
    values: Dict[str, object] = {}
    kwargs: Dict[str, object] = {}
    pos_index = 0
    for arg in statement.args:
        if arg[0] == "kw":
            _, key, value_node = arg
            if key not in allowed_kwargs:
                raise ParseError(
                    "unknown argument {0!r} for {1}() on line {2}".format(
                        key, statement.name, statement.line
                    )
                )
            kwargs[key] = value_node
        else:
            if pos_index >= len(positional_names):
                raise ParseError(
                    "too many positional arguments for {0}() on line {1}".format(
                        statement.name, statement.line
                    )
                )
            values[positional_names[pos_index]] = arg[1]
            pos_index += 1
    return values, kwargs


def _resolved(values: Dict[str, object], kwargs: Dict[str, object],
              variables: Dict[str, float], line: int) -> Dict[str, object]:
    resolved: Dict[str, object] = {}
    for key, node in values.items():
        resolved[key] = _eval_value(node, variables, line)
    for key, node in kwargs.items():
        resolved[key] = _eval_value(node, variables, line)
    return resolved


def _build_primitive(statement: Statement, variables: Dict[str, float]) -> Mesh:
    names, factory = PRIMITIVES[statement.name]
    allowed = set(names) | {"at", "color"}
    values, kwargs = _collect_args(statement, names, sorted(allowed))
    resolved = _resolved(values, kwargs, variables, statement.line)
    params = {k: v for k, v in resolved.items() if k not in ("at", "color")}
    for key, value in params.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ParseError(
                "argument {0!r} of {1}() must be a number (line {2})".format(
                    key, statement.name, statement.line
                )
            )
        if key in ("segments", "rings", "tube_segments"):
            params[key] = int(round(value))
    at = resolved.get("at")
    color = resolved.get("color")
    try:
        if at is not None:
            if not isinstance(at, tuple) or len(at) != 3:
                raise ParseError(
                    "at= expects (x, y, z) on line {0}".format(statement.line)
                )
        if color is not None:
            color = _parse_color(color)
        mesh = factory(**params)  # type: ignore[arg-type]
    except MeshError as exc:
        raise ParseError("{0}() failed on line {1}: {2}".format(statement.name, statement.line, exc))
    if at is not None or color is not None:
        mesh = mesh.copy()
        if at is not None:
            from .vec import Vec3 as _V
            offset = _V(float(at[0]), float(at[1]), float(at[2]))
            mesh.vertices = [v + offset for v in mesh.vertices]
        if color is not None:
            mesh.colors = [color] * len(mesh.faces)
    return mesh


def _build_transform(statement: Statement, block_meshes: List[Mesh],
                     variables: Dict[str, float]) -> Mesh:
    name = statement.name
    names, allowed_kwargs = {
        "translate": (["dx", "dy", "dz"], []),
        "rotate": (["rx", "ry", "rz"], []),
        "scale": (["s", "sy", "sz"], []),
        "mirror": (["axis"], []),
    }[name]
    allowed = set(names) | set(allowed_kwargs)
    values, kw = _collect_args(statement, names, sorted(allowed))
    resolved = _resolved(values, kw, variables, statement.line)
    base = csg.union_all(block_meshes) if block_meshes else Mesh.empty()
    line = statement.line
    try:
        if name == "translate":
            return translate(base, float(resolved["dx"]), float(resolved["dy"]), float(resolved["dz"]))
        if name == "rotate":
            return rotate(base, float(resolved["rx"]), float(resolved["ry"]), float(resolved["rz"]))
        if name == "scale":
            if "sy" in resolved and "sz" not in resolved:
                raise ParseError(
                    "scale() takes either 1 (uniform) or 3 (sx, sy, sz) arguments (line {0})".format(line)
                )
            if "sz" in resolved and "sy" not in resolved:
                raise ParseError(
                    "scale() takes either 1 (uniform) or 3 (sx, sy, sz) arguments (line {0})".format(line)
                )
            if "sy" in resolved and "sz" in resolved:
                return scale(base, (float(resolved["s"]), float(resolved["sy"]), float(resolved["sz"])))
            return scale(base, float(resolved["s"]))
        if name == "mirror":
            axis = resolved["axis"]
            return mirror(base, axis)
    except (TypeError, ValueError) as exc:
        raise ParseError("{0}() failed on line {1}: {2}".format(name, line, exc))
    raise ParseError("unhandled transform {0}".format(name))  # pragma: no cover


def _build_profile(statement: Statement, variables: Dict[str, float]) -> Profile:
    name = statement.name
    line = statement.line
    if name == "polygon":
        allowed = {"points"}
        values, kwargs = _collect_args(statement, ["points"], sorted(allowed))
        if "points" not in kwargs and "points" not in values:
            raise ParseError("polygon() needs a points=[[x, y], ...] argument (line {0})".format(line))
        node = kwargs.get("points") or values.get("points")
        points = _eval_points(node, variables, line)
        if len(points) < 3:
            raise ParseError("polygon() needs at least 3 points (line {0})".format(line))
        return Profile(points)
    if name == "circle":
        names, allowed = ["r"], ["r", "segments"]
        values, kwargs = _collect_args(statement, names, sorted(set(names) | set(allowed)))
        resolved = _resolved(values, kwargs, variables, line)
        return Profile(prof.circle_profile(float(resolved["r"]), int(resolved.get("segments", 32))))
    if name == "square":
        names, allowed = ["size"], ["size"]
        values, kwargs = _collect_args(statement, names, sorted(set(names) | set(allowed)))
        resolved = _resolved(values, kwargs, variables, line)
        s = float(resolved["size"])
        return Profile(prof.rect_profile(s, s))
    if name == "rect":
        names, allowed = ["w", "h"], ["w", "h"]
        values, kwargs = _collect_args(statement, names, sorted(set(names) | set(allowed)))
        resolved = _resolved(values, kwargs, variables, line)
        return Profile(prof.rect_profile(float(resolved["w"]), float(resolved["h"])))
    raise ParseError("unknown profile {0!r} (line {1})".format(name, line))  # pragma: no cover


def _eval_block(statements: List[Statement], variables: Dict[str, float],
                allow_profiles: bool) -> List[Union[Mesh, Profile]]:
    items: List[Union[Mesh, Profile]] = []
    for st in statements:
        items.extend(_eval_statement(st, variables, allow_profiles))
    return items


def _eval_statement(statement: Statement, variables: Dict[str, float],
                    allow_profiles: bool) -> List[Union[Mesh, Profile]]:
    line = statement.line
    if statement.kind == "let":
        variables[statement.name] = eval_expr(statement.args[0][1], variables, line)
        return []

    name = statement.name
    if name in PRIMITIVES:
        return [_build_primitive(statement, variables)]

    if name in PROFILE_OPS:
        if not allow_profiles:
            raise ParseError(
                "{0}() is only allowed inside extrude/revolve blocks (line {1})".format(name, line)
            )
        return [_build_profile(statement, variables)]

    if name in TRANSFORMS:
        if statement.block is None:
            raise ParseError("{0}() needs a {{ ... }} block (line {1})".format(name, line))
        items = _eval_block(statement.block, variables, allow_profiles=False)
        meshes = [i for i in items if isinstance(i, Mesh)]
        if any(isinstance(i, Profile) for i in items):
            raise ParseError("profiles are not allowed inside {0}() (line {1})".format(name, line))
        return [_build_transform(statement, meshes, variables)]

    if name in CSG_OPS:
        if statement.block is None:
            raise ParseError("{0}() needs a {{ ... }} block (line {1})".format(name, line))
        items = _eval_block(statement.block, variables, allow_profiles=False)
        meshes = [i for i in items if isinstance(i, Mesh)]
        if not meshes:
            raise ParseError("{0}() block is empty (line {1})".format(name, line))
        if name == "union":
            return [csg.union_all(meshes)]
        if name == "difference":
            return [csg.subtract_all(meshes[0], meshes[1:])]
        return [csg.intersect(meshes[0], csg.union_all(meshes[1:]))]

    if name == "color":
        if statement.block is None:
            raise ParseError("color() needs a { ... } block (line {0})".format(line))
        items = _eval_block(statement.block, variables, allow_profiles=False)
        meshes = [i for i in items if isinstance(i, Mesh)]
        if not meshes:
            raise ParseError("color() block is empty (line {0})".format(line))
        names = ["value"]
        values, kwargs = _collect_args(statement, names, ["value"])
        resolved = _resolved(values, kwargs, variables, line)
        rgb = _parse_color(resolved.get("value", "#cccccc"))
        mesh = csg.union_all(meshes)
        mesh = mesh.copy()
        mesh.colors = [rgb] * len(mesh.faces)
        return [mesh]

    if name == "repeat":
        if statement.block is None:
            raise ParseError("repeat() needs a { ... } block (line {0})".format(line))
        items = _eval_block(statement.block, variables, allow_profiles=False)
        meshes = [i for i in items if isinstance(i, Mesh)]
        if not meshes:
            raise ParseError("repeat() block is empty (line {0})".format(line))
        names = ["count"]
        allowed = {"count", "rotate", "translate"}
        values, kwargs = _collect_args(statement, names, sorted(allowed))
        resolved = _resolved(values, kwargs, variables, line)
        count = int(resolved.get("count", 1))
        if count < 1:
            raise ParseError("repeat() count must be >= 1 (line {0})".format(line))
        rot = resolved.get("rotate", (0.0, 0.0, 0.0))
        trans = resolved.get("translate", (0.0, 0.0, 0.0))
        base = csg.union_all(meshes)
        copies = [base]
        for k in range(1, count):
            copy = rotate(base, float(rot[0]) * k, float(rot[1]) * k, float(rot[2]) * k)
            copy = translate(copy, float(trans[0]) * k, float(trans[1]) * k, float(trans[2]) * k)
            copies.append(copy)
        return [csg.union_all(copies)]

    if name in ("extrude", "revolve"):
        if statement.block is None:
            raise ParseError("{0}() needs a {{ profile }} block (line {1})".format(name, line))
        items = _eval_block(statement.block, variables, allow_profiles=True)
        profile_items = [i for i in items if isinstance(i, Profile)]
        mesh_items = [i for i in items if isinstance(i, Mesh)]
        if mesh_items:
            raise ParseError("{0}() blocks may only contain profiles (line {1})".format(name, line))
        if len(profile_items) != 1:
            raise ParseError(
                "{0}() needs exactly one profile statement (line {1})".format(name, line)
            )
        profile: Profile = profile_items[0]  # type: ignore[assignment]
        if name == "extrude":
            names, allowed = ["height"], ["height", "at", "color"]
        else:
            names, allowed = ["angle", "segments"], ["angle", "segments", "at", "color"]
        values, kwargs = _collect_args(statement, names, sorted(set(names) | set(allowed)))
        resolved = _resolved(values, kwargs, variables, line)
        at = resolved.get("at")
        color = resolved.get("color")
        if color is not None:
            color = _parse_color(color)
        if at is not None and (not isinstance(at, tuple) or len(at) != 3):
            raise ParseError("at= expects (x, y, z) (line {0})".format(line))
        try:
            if name == "extrude":
                mesh = prof.extrude(
                    profile.points,
                    float(resolved.get("height", 1.0)),
                    at=at,
                    color=color,
                )
            else:
                mesh = prof.revolve(
                    profile.points,
                    float(resolved.get("angle", 360.0)),
                    int(resolved.get("segments", 48)),
                    at=at,
                    color=color,
                )
        except MeshError as exc:
            raise ParseError("{0}() failed on line {1}: {2}".format(name, line, exc))
        return [mesh]

    raise ParseError("unhandled statement {0!r} on line {1}".format(name, line))  # pragma: no cover


def evaluate(source: str, name: str = "model", units: str = "mm") -> Mesh:
    """Evaluate TextToSolid DSL source and return the resulting solid mesh.

    All root-level shapes are combined with an implicit union.
    """
    statements = parse(source)
    variables: Dict[str, float] = {}
    meshes: List[Mesh] = []
    for st in statements:
        for item in _eval_statement(st, variables, allow_profiles=False):
            if isinstance(item, Profile):
                raise ParseError(
                    "profiles are only allowed inside extrude/revolve (line {0})".format(st.line)
                )
            meshes.append(item)
    result = csg.union_all(meshes) if meshes else Mesh.empty(name=name, units=units)
    result.name = name
    result.units = units
    return result
