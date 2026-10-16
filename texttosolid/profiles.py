"""2D profiles, polygon triangulation, extrusion and revolution.

These operations turn flat sketches into closed solids:

* :func:`triangulate_polygon` — ear-clipping triangulation of a simple polygon
* :func:`extrude`             — lift a profile along +Z into a prism
* :func:`revolve`             — sweep a profile around the Y axis
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

from .errors import MeshError
from .mesh import Mesh, RGB
from .vec import Vec3

__all__ = [
    "triangulate_polygon",
    "polygon_area",
    "extrude",
    "revolve",
    "circle_profile",
    "rect_profile",
]

Point2 = Tuple[float, float]
WELD_EPS = 1e-9


# ---------------------------------------------------------------------- #
# 2D helpers                                                             #
# ---------------------------------------------------------------------- #
def _clean(points: Sequence[Point2]) -> List[Point2]:
    """Drop consecutive duplicates and the closing point if repeated."""
    cleaned: List[Point2] = []
    for p in points:
        p = (float(p[0]), float(p[1]))
        if cleaned and abs(cleaned[-1][0] - p[0]) < WELD_EPS and abs(cleaned[-1][1] - p[1]) < WELD_EPS:
            continue
        cleaned.append(p)
    if len(cleaned) > 1 and abs(cleaned[0][0] - cleaned[-1][0]) < WELD_EPS \
            and abs(cleaned[0][1] - cleaned[-1][1]) < WELD_EPS:
        cleaned.pop()
    return cleaned


def polygon_area(points: Sequence[Point2]) -> float:
    """Signed area of a 2D polygon (positive when counter-clockwise)."""
    pts = _clean(points)
    if len(pts) < 3:
        return 0.0
    total = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        total += x1 * y2 - x2 * y1
    return total / 2.0


def _cross(o: Point2, a: Point2, b: Point2) -> float:
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _point_in_triangle(p: Point2, a: Point2, b: Point2, c: Point2) -> bool:
    d1 = _cross(a, b, p)
    d2 = _cross(b, c, p)
    d3 = _cross(c, a, p)
    has_neg = (d1 < -1e-12) or (d2 < -1e-12) or (d3 < -1e-12)
    has_pos = (d1 > 1e-12) or (d2 > 1e-12) or (d3 > 1e-12)
    return not (has_neg and has_pos)


def triangulate_polygon(points: Sequence[Point2]) -> List[Tuple[int, int, int]]:
    """Triangulate a simple polygon with ear clipping.

    Returns index triples into the (cleaned) input points.  Works for convex
    and non-convex polygons; raises :class:`MeshError` for degenerate input.
    """
    pts = _clean(points)
    n = len(pts)
    if n < 3:
        raise MeshError("polygon needs at least 3 distinct points")
    if abs(polygon_area(pts)) < 1e-12:
        raise MeshError("polygon has zero area")

    # ensure counter-clockwise orientation
    if polygon_area(pts) < 0:
        pts = list(reversed(pts))

    indices = list(range(n))
    triangles: List[Tuple[int, int, int]] = []
    guard = 0
    while len(indices) > 3:
        guard += 1
        if guard > 4 * n * n + 16:
            raise MeshError("polygon triangulation failed (self-intersecting?)")
        clipped = False
        m = len(indices)
        for k in range(m):
            i_prev = indices[(k - 1) % m]
            i_curr = indices[k]
            i_next = indices[(k + 1) % m]
            a, b, c = pts[i_prev], pts[i_curr], pts[i_next]
            if _cross(a, b, c) <= 1e-12:
                continue  # reflex or collinear vertex — not an ear
            # no other vertex may lie inside the candidate ear
            contains = False
            for idx in indices:
                if idx in (i_prev, i_curr, i_next):
                    continue
                if _point_in_triangle(pts[idx], a, b, c):
                    contains = True
                    break
            if contains:
                continue
            triangles.append((i_prev, i_curr, i_next))
            indices.pop(k)
            clipped = True
            break
        if not clipped:
            # numerical fallback: clip the first convex vertex we can find
            for k in range(m):
                i_prev = indices[(k - 1) % m]
                i_curr = indices[k]
                i_next = indices[(k + 1) % m]
                if _cross(pts[i_prev], pts[i_curr], pts[i_next]) > 1e-12:
                    triangles.append((i_prev, i_curr, i_next))
                    indices.pop(k)
                    clipped = True
                    break
        if not clipped:
            raise MeshError("polygon triangulation failed")
    if len(indices) == 3:
        triangles.append((indices[0], indices[1], indices[2]))
    return triangles


def circle_profile(r: float, segments: int = 32) -> List[Point2]:
    """Circle as a 2D polygon."""
    if r <= 0:
        raise MeshError("circle radius must be positive")
    if segments < 3:
        raise MeshError("circle needs segments >= 3")
    return [
        (r * math.cos(2.0 * math.pi * i / segments), r * math.sin(2.0 * math.pi * i / segments))
        for i in range(segments)
    ]


def rect_profile(w: float, h: float) -> List[Point2]:
    """Rectangle centred on the origin as a 2D polygon."""
    if w <= 0 or h <= 0:
        raise MeshError("rectangle dimensions must be positive")
    hw, hh = w / 2.0, h / 2.0
    return [(-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)]


# ---------------------------------------------------------------------- #
# extrude                                                                #
# ---------------------------------------------------------------------- #
def extrude(
    points: Sequence[Point2],
    height: float = 1.0,
    at: Optional[Tuple[float, float, float]] = None,
    color: Optional[RGB] = None,
    name: str = "extrude",
) -> Mesh:
    """Extrude a 2D profile along +Z from ``z = 0`` to ``z = height``."""
    pts = _clean(points)
    if len(pts) < 3:
        raise MeshError("extrude profile needs at least 3 distinct points")
    if height <= 0:
        raise MeshError("extrude height must be positive")
    tris = triangulate_polygon(pts)
    n = len(pts)
    vertices: List[Vec3] = []
    for x, y in pts:
        vertices.append(Vec3(x, y, 0.0))       # bottom ring: 0 .. n-1
    for x, y in pts:
        vertices.append(Vec3(x, y, height))    # top ring:    n .. 2n-1

    faces: List[Tuple[int, int, int]] = []
    for a, b, c in tris:
        faces.append((a, b, c))            # bottom cap (normal -z after repair)
        faces.append((n + a, n + c, n + b))  # top cap    (normal +z after repair)
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j))
        faces.append((i, n + j, n + i))
    mesh = Mesh(vertices, faces, name=name)
    if color is not None:
        mesh.colors = [tuple(color)] * len(mesh.faces)  # type: ignore[assignment]
    if at is not None:
        offset = Vec3(at[0], at[1], at[2])
        mesh.vertices = [v + offset for v in mesh.vertices]
    return mesh.repair_winding()


# ---------------------------------------------------------------------- #
# revolve                                                                #
# ---------------------------------------------------------------------- #
def revolve(
    profile: Sequence[Point2],
    angle: float = 360.0,
    segments: int = 48,
    at: Optional[Tuple[float, float, float]] = None,
    color: Optional[RGB] = None,
    name: str = "revolve",
) -> Mesh:
    """Revolve a ``(radius, y)`` profile around the Y axis.

    ``angle`` is in degrees (360 = full solid of revolution).  When the sweep
    is partial the open ends are capped automatically whenever the profile
    endpoint is off the axis.
    """
    pts = _clean(profile)
    if len(pts) < 2:
        raise MeshError("revolve profile needs at least 2 points")
    for r, _y in pts:
        if r < -1e-9:
            raise MeshError("revolve profile radius must be >= 0")
    pts = [(max(r, 0.0), y) for r, y in pts]
    if angle <= 0 or angle > 360:
        raise MeshError("revolve angle must be in (0, 360]")
    if segments < 3:
        raise MeshError("revolve needs segments >= 3")
    if angle < 360 and len(pts) < 3:
        raise MeshError("partial revolve needs a profile with at least 3 points")

    sweep = math.radians(angle)
    full = abs(angle - 360.0) < 1e-9
    m = len(pts)

    vertices: List[Vec3] = []
    # profile points that touch the axis collapse to a single shared vertex
    axis_vertex: Dict[int, int] = {}
    for i, (r, y) in enumerate(pts):
        if r <= WELD_EPS:
            axis_vertex[i] = len(vertices)
            vertices.append(Vec3(0.0, y, 0.0))

    off_axis = [i for i, (r, _y) in enumerate(pts) if r > WELD_EPS]
    n_rings = segments if full else segments + 1
    ring_vertex: Dict[Tuple[int, int], int] = {}
    for k in range(n_rings):
        theta = sweep * k / segments
        ct = math.cos(theta)
        st = math.sin(theta)
        for i in off_axis:
            r, y = pts[i]
            ring_vertex[(i, k)] = len(vertices)
            vertices.append(Vec3(r * ct, y, r * st))

    def vid(i: int, k: int) -> int:
        return axis_vertex[i] if i in axis_vertex else ring_vertex[(i, k)]

    faces: List[Tuple[int, int, int]] = []
    for k in range(segments):
        k2 = (k + 1) % segments if full else k + 1
        for i in range(m):
            j = (i + 1) % m
            ri = pts[i][0]
            rj = pts[j][0]
            if ri <= WELD_EPS and rj <= WELD_EPS:
                continue  # segment lies on the axis — no swept surface
            a, b = vid(i, k), vid(j, k)
            c, d = vid(j, k2), vid(i, k2)
            if ri > WELD_EPS and rj > WELD_EPS:
                faces.append((a, b, c))
                faces.append((a, c, d))
            elif ri <= WELD_EPS:
                # i on the axis, j off: triangle (axis_i, j_k, j_k2)
                faces.append((a, b, c))
            else:
                # i off, j on the axis: triangle (i_k, i_k2, axis_j)
                faces.append((a, d, b))

    if not full:
        # cap the two open boundary faces of a partial sweep
        tris = triangulate_polygon(pts)
        for k in (0, n_rings - 1):
            ring = [vid(i, k) for i in range(m)]
            for a, b, c in tris:
                faces.append((ring[a], ring[b], ring[c]))

    mesh = Mesh(vertices, faces, name=name)
    if color is not None:
        mesh.colors = [tuple(color)] * len(mesh.faces)  # type: ignore[assignment]
    if at is not None:
        offset = Vec3(at[0], at[1], at[2])
        mesh.vertices = [v + offset for v in mesh.vertices]
    return mesh.repair_winding()
