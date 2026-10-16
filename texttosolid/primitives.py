"""Parametric solid primitives.

Every primitive returns a closed, watertight :class:`Mesh` centred on the
origin (optionally moved with ``at=``).  Winding is repaired automatically, so
each solid has outward-facing normals regardless of construction order.
"""
from __future__ import annotations

import math
from typing import List, Optional, Sequence, Tuple

from .errors import MeshError
from .mesh import Mesh, RGB
from .vec import Vec3

__all__ = [
    "box",
    "sphere",
    "cylinder",
    "cone",
    "torus",
    "wedge",
    "tube",
    "pyramid",
]

Point3 = Tuple[float, float, float]


def _at_offset(at: Optional[Point3]) -> Vec3:
    if at is None:
        return Vec3(0.0, 0.0, 0.0)
    if len(at) != 3:
        raise MeshError("at= expects a 3D point like (x, y, z)")
    return Vec3(at[0], at[1], at[2])


def _finish(mesh: Mesh, at: Optional[Point3], color: Optional[RGB], name: str) -> Mesh:
    mesh.name = name
    offset = _at_offset(at)
    if offset.x or offset.y or offset.z:
        mesh.vertices = [v + offset for v in mesh.vertices]
    if color is not None:
        mesh.colors = [tuple(color)] * len(mesh.faces)  # type: ignore[assignment]
    return mesh.repair_winding()


def _quad(a: int, b: int, c: int, d: int) -> List[Tuple[int, int, int]]:
    """Split quad (a, b, c, d) into two consistently wound triangles."""
    return [(a, b, c), (a, c, d)]


def _ring(radius: float, y: float, segments: int) -> List[Vec3]:
    """A circle of vertices around the Y axis at height ``y``."""
    if radius <= 0.0:
        return [Vec3(0.0, y, 0.0)]
    return [
        Vec3(radius * math.cos(2.0 * math.pi * i / segments), y,
             radius * math.sin(2.0 * math.pi * i / segments))
        for i in range(segments)
    ]


def _connect_rings(bottom: Sequence[Vec3], top: Sequence[Vec3]) -> List[Tuple[int, int, int]]:
    """Quads between two rings (handles single-vertex rings at cone tips)."""
    faces: List[Tuple[int, int, int]] = []
    n = max(len(bottom), len(top))
    if len(bottom) == 1:
        b0 = 0
        for i in range(n):
            j = (i + 1) % n
            faces.append((b0, 1 + i, 1 + j))
        return faces
    if len(top) == 1:
        t0 = n
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, t0, j))
        return faces
    if len(bottom) != len(top):
        raise MeshError("cannot connect rings of different sizes")
    for i in range(n):
        j = (i + 1) % n
        faces.extend(_quad(i, n + i, n + j, j))
    return faces


def _cap(center: Vec3, ring: Sequence[Vec3], normal_y: float) -> List[Tuple[int, int, int]]:
    """Triangle fan closing a ring around ``center`` (normal along ±Y)."""
    if len(ring) <= 1:
        return []
    c_idx = len(ring)
    faces: List[Tuple[int, int, int]] = []
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        if normal_y >= 0:
            faces.append((c_idx, i, j))
        else:
            faces.append((c_idx, j, i))
    return faces


# ---------------------------------------------------------------------- #
# primitives                                                              #
# ---------------------------------------------------------------------- #
def box(
    w: float = 1.0,
    d: float = 1.0,
    h: float = 1.0,
    at: Optional[Point3] = None,
    color: Optional[RGB] = None,
) -> Mesh:
    """Axis-aligned box of size ``w x d x h`` centred on the origin."""
    if w <= 0 or d <= 0 or h <= 0:
        raise MeshError("box dimensions must be positive")
    hx, hy, hz = w / 2.0, d / 2.0, h / 2.0
    v = [
        Vec3(-hx, -hy, -hz), Vec3(hx, -hy, -hz), Vec3(hx, hy, -hz), Vec3(-hx, hy, -hz),
        Vec3(-hx, -hy, hz), Vec3(hx, -hy, hz), Vec3(hx, hy, hz), Vec3(-hx, hy, hz),
    ]
    quads = [
        (0, 3, 2, 1),  # bottom  (-z)
        (4, 5, 6, 7),  # top     (+z)
        (0, 1, 5, 4),  # front   (-y)
        (2, 3, 7, 6),  # back    (+y)
        (1, 2, 6, 5),  # right   (+x)
        (0, 4, 7, 3),  # left    (-x)
    ]
    faces: List[Tuple[int, int, int]] = []
    for q in quads:
        faces.extend(_quad(*q))
    return _finish(Mesh(v, faces), at, color, "box")


def sphere(
    r: float = 1.0,
    segments: int = 24,
    rings: int = 12,
    at: Optional[Point3] = None,
    color: Optional[RGB] = None,
) -> Mesh:
    """UV sphere of radius ``r`` (latitude ``rings``, longitude ``segments``)."""
    if r <= 0:
        raise MeshError("sphere radius must be positive")
    if rings < 2 or segments < 3:
        raise MeshError("sphere needs rings >= 2 and segments >= 3")
    vertices: List[Vec3] = [Vec3(0.0, r, 0.0)]  # north pole
    ring_ranges: List[Tuple[int, int]] = []
    for j in range(1, rings):
        phi = math.pi * j / rings
        start = len(vertices)
        y = r * math.cos(phi)
        rr = r * math.sin(phi)
        for i in range(segments):
            theta = 2.0 * math.pi * i / segments
            vertices.append(Vec3(rr * math.cos(theta), y, rr * math.sin(theta)))
        ring_ranges.append((start, start + segments))
    south_pole = len(vertices)
    vertices.append(Vec3(0.0, -r, 0.0))

    faces: List[Tuple[int, int, int]] = []
    # north cap: fan over the first ring
    first_start, first_end = ring_ranges[0]
    for i in range(segments):
        j = first_start + (i + 1) % segments
        faces.append((0, first_start + i, j))
    # middle rings
    for (s0, e0), (s1, e1) in zip(ring_ranges, ring_ranges[1:]):
        for i in range(segments):
            j = (i + 1) % segments
            faces.extend(_quad(s0 + i, s0 + j, s1 + j, s1 + i))
    # south cap
    last_start, _ = ring_ranges[-1]
    for i in range(segments):
        j = last_start + (i + 1) % segments
        faces.append((south_pole, j, last_start + i))
    return _finish(Mesh(vertices, faces), at, color, "sphere")


def cylinder(
    r: float = 1.0,
    h: float = 1.0,
    segments: int = 32,
    at: Optional[Point3] = None,
    color: Optional[RGB] = None,
) -> Mesh:
    """Cylinder of radius ``r`` and height ``h`` around the Y axis."""
    if r <= 0 or h <= 0:
        raise MeshError("cylinder radius and height must be positive")
    if segments < 3:
        raise MeshError("cylinder needs segments >= 3")
    hy = h / 2.0
    bottom = _ring(r, -hy, segments)
    top = _ring(r, hy, segments)
    vertices = list(bottom) + list(top)
    faces = _connect_rings(bottom, top)
    faces.extend(_cap(Vec3(0.0, -hy, 0.0), bottom, -1.0))
    faces.extend(_cap(Vec3(0.0, hy, 0.0), top, +1.0))
    return _finish(Mesh(vertices, faces), at, color, "cylinder")


def cone(
    r1: float = 1.0,
    r2: float = 0.0,
    h: float = 1.0,
    segments: int = 32,
    at: Optional[Point3] = None,
    color: Optional[RGB] = None,
) -> Mesh:
    """Truncated cone: bottom radius ``r1``, top radius ``r2`` (0 = sharp tip)."""
    if r1 < 0 or r2 < 0 or h <= 0:
        raise MeshError("cone radii must be >= 0 and height positive")
    if r1 == 0 and r2 == 0:
        raise MeshError("cone needs at least one non-zero radius")
    if segments < 3:
        raise MeshError("cone needs segments >= 3")
    hy = h / 2.0
    bottom = _ring(r1, -hy, segments)
    top = _ring(r2, hy, segments)
    vertices = list(bottom) + list(top)
    faces = _connect_rings(bottom, top)
    if r1 > 0:
        faces.extend(_cap(Vec3(0.0, -hy, 0.0), bottom, -1.0))
    if r2 > 0:
        faces.extend(_cap(Vec3(0.0, hy, 0.0), top, +1.0))
    return _finish(Mesh(vertices, faces), at, color, "cone")


def torus(
    R: float = 1.0,
    r: float = 0.3,
    segments: int = 32,
    tube_segments: int = 12,
    at: Optional[Point3] = None,
    color: Optional[RGB] = None,
) -> Mesh:
    """Torus with major radius ``R`` and tube radius ``r`` around the Y axis."""
    if R <= 0 or r <= 0:
        raise MeshError("torus radii must be positive")
    if segments < 3 or tube_segments < 3:
        raise MeshError("torus needs segments >= 3 and tube_segments >= 3")
    vertices: List[Vec3] = []
    faces: List[Tuple[int, int, int]] = []
    for k in range(segments):
        theta = 2.0 * math.pi * k / segments
        radial = Vec3(math.cos(theta), 0.0, math.sin(theta))
        center = radial * R
        start = len(vertices)
        for m in range(tube_segments):
            phi = 2.0 * math.pi * m / tube_segments
            p = center + radial * (r * math.cos(phi)) + Vec3(0.0, r * math.sin(phi), 0.0)
            vertices.append(p)
        nxt = (k + 1) % segments
        base_next = nxt * tube_segments
        for m in range(tube_segments):
            j = (m + 1) % tube_segments
            faces.extend(_quad(start + m, base_next + m, base_next + j, start + j))
    return _finish(Mesh(vertices, faces), at, color, "torus")


def wedge(
    w: float = 1.0,
    d: float = 1.0,
    h: float = 1.0,
    at: Optional[Point3] = None,
    color: Optional[RGB] = None,
) -> Mesh:
    """Right triangular prism (a box sliced along a diagonal)."""
    if w <= 0 or d <= 0 or h <= 0:
        raise MeshError("wedge dimensions must be positive")
    hx, hy, hz = w / 2.0, d / 2.0, h / 2.0
    v = [
        Vec3(-hx, -hy, -hz),  # 0 bottom front-left
        Vec3(hx, -hy, -hz),   # 1 bottom front-right
        Vec3(hx, hy, -hz),    # 2 bottom back-right
        Vec3(-hx, hy, -hz),   # 3 bottom back-left
        Vec3(hx, -hy, hz),    # 4 top front-right
        Vec3(hx, hy, hz),     # 5 top back-right
    ]
    faces: List[Tuple[int, int, int]] = []
    faces.extend(_quad(0, 1, 2, 3))          # bottom
    faces.extend(_quad(0, 4, 5, 3))          # sloped face
    faces.extend(_quad(1, 2, 5, 4))          # right face (+x)
    faces.append((0, 1, 4))                  # front triangle (-y)
    faces.append((2, 3, 5))                  # back triangle (+y)
    return _finish(Mesh(v, faces), at, color, "wedge")


def tube(
    r: float = 1.0,
    ri: float = 0.6,
    h: float = 1.0,
    segments: int = 32,
    at: Optional[Point3] = None,
    color: Optional[RGB] = None,
) -> Mesh:
    """Hollow cylinder (pipe) with outer radius ``r`` and inner radius ``ri``."""
    if r <= 0 or ri <= 0 or h <= 0:
        raise MeshError("tube radii and height must be positive")
    if ri >= r:
        raise MeshError("tube inner radius must be smaller than outer radius")
    if segments < 3:
        raise MeshError("tube needs segments >= 3")
    hy = h / 2.0
    outer_b = _ring(r, -hy, segments)
    outer_t = _ring(r, hy, segments)
    inner_b = _ring(ri, -hy, segments)
    inner_t = _ring(ri, hy, segments)
    n = len(outer_b)
    vertices = list(outer_b) + list(outer_t) + list(inner_b) + list(inner_t)
    ib = 2 * n  # index offset of the inner rings inside ``vertices``

    faces = _connect_rings(outer_b, outer_t)
    # inner wall, wound the opposite way (it faces into the bore)
    faces.extend(
        (a + ib, b + ib, c + ib)
        for a, b, c in _connect_rings(inner_t, inner_b)
    )
    # annulus caps connecting outer and inner rings
    for i in range(n):
        j = (i + 1) % n
        faces.extend(_quad(i, j, ib + j, ib + i))            # bottom
        faces.extend(_quad(n + i, ib + i, ib + j, n + j))    # top
    return _finish(Mesh(vertices, faces), at, color, "tube")


def pyramid(
    base: float = 1.0,
    h: float = 1.0,
    at: Optional[Point3] = None,
    color: Optional[RGB] = None,
) -> Mesh:
    """Square pyramid with base side ``base`` and height ``h``."""
    if base <= 0 or h <= 0:
        raise MeshError("pyramid base and height must be positive")
    hb = base / 2.0
    hy = h / 2.0
    v = [
        Vec3(-hb, -hy, -hb),  # 0
        Vec3(hb, -hy, -hb),   # 1
        Vec3(hb, -hy, hb),    # 2
        Vec3(-hb, -hy, hb),   # 3
        Vec3(0.0, hy, 0.0),   # 4 apex
    ]
    faces: List[Tuple[int, int, int]] = []
    faces.extend(_quad(0, 3, 2, 1))  # base
    faces.append((0, 1, 4))
    faces.append((1, 2, 4))
    faces.append((2, 3, 4))
    faces.append((3, 0, 4))
    return _finish(Mesh(v, faces), at, color, "pyramid")
