"""Constructive Solid Geometry on triangle meshes via BSP trees.

The implementation follows the classic BSP CSG algorithm (binary space
partitioning with polygon splitting) written from scratch for this project:

* :class:`Plane`   — a plane defined by a normal and an offset
* :class:`Polygon` — a convex polygon (a split triangle) with optional color
* :class:`Node`    — a BSP tree node
* :func:`union` / :func:`subtract` / :func:`intersect` — boolean operations

Everything is pure standard library and works on any closed manifold mesh.
"""
from __future__ import annotations

import math
import sys
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .mesh import Mesh, RGB
from .vec import Vec3

__all__ = ["Plane", "Polygon", "Node", "union", "subtract", "intersect"]

# vertex classification
COPLANAR = 0
FRONT = 1
BACK = 2
STRADDLING = 3

EPSILON = 1e-9


class Plane:
    """A plane in 3D space: ``normal . x = w``."""

    __slots__ = ("normal", "w")

    def __init__(self, normal: Vec3, w: float) -> None:
        self.normal = normal
        self.w = float(w)

    @classmethod
    def from_points(cls, a: Vec3, b: Vec3, c: Vec3) -> Optional["Plane"]:
        n = (b - a).cross(c - a)
        if n.length_sq() < 1e-18:
            return None
        n = n.normalized()
        return cls(n, n.dot(a))

    @classmethod
    def from_polygon(cls, polygon: "Polygon") -> Optional["Plane"]:
        """Plane of a polygon via Newell's method (robust for thin triangles)."""
        normal = Vec3(0.0, 0.0, 0.0)
        verts = polygon.vertices
        for i in range(len(verts)):
            current = verts[i]
            nxt = verts[(i + 1) % len(verts)]
            normal.x += (current.y - nxt.y) * (current.z + nxt.z)
            normal.y += (current.z - nxt.z) * (current.x + nxt.x)
            normal.z += (current.x - nxt.x) * (current.y + nxt.y)
        if normal.length_sq() < 1e-18:
            return None
        normal = normal.normalized()
        return cls(normal, normal.dot(verts[0]))

    def flip(self) -> None:
        self.normal = -self.normal
        self.w = -self.w

    def clone(self) -> "Plane":
        return Plane(self.normal, self.w)

    def split_polygon(
        self, polygon: "Polygon"
    ) -> Tuple[List["Polygon"], List["Polygon"], List["Polygon"], List["Polygon"]]:
        """Split ``polygon`` by this plane.

        Returns ``(coplanar_front, coplanar_back, front, back)``.
        """
        coplanar_front: List[Polygon] = []
        coplanar_back: List[Polygon] = []
        front: List[Polygon] = []
        back: List[Polygon] = []

        polygon_type = 0
        types: List[int] = []
        for vertex in polygon.vertices:
            t = self.normal.dot(vertex) - self.w
            if t < -EPSILON:
                ptype = BACK
            elif t > EPSILON:
                ptype = FRONT
            else:
                ptype = COPLANAR
            polygon_type |= ptype
            types.append(ptype)

        if polygon_type == COPLANAR:
            if self.normal.dot(polygon.plane.normal) > 0:
                coplanar_front.append(polygon)
            else:
                coplanar_back.append(polygon)
        elif polygon_type == FRONT:
            front.append(polygon)
        elif polygon_type == BACK:
            back.append(polygon)
        else:
            verts = polygon.vertices
            f: List[Vec3] = []
            b: List[Vec3] = []
            color = polygon.color
            n = len(verts)
            for i in range(n):
                j = (i + 1) % n
                ti = types[i]
                tj = types[j]
                vi = verts[i]
                vj = verts[j]
                if ti != BACK:
                    f.append(vi)
                if ti != FRONT:
                    b.append(vi)
                if (ti | tj) == STRADDLING:
                    t = (self.normal.dot(vi) - self.w) / (
                        self.normal.dot(vi) - self.normal.dot(vj)
                    )
                    split = vi.lerp(vj, t)
                    f.append(split)
                    b.append(split)
            if len(f) >= 3:
                front.append(Polygon(f, color))
            if len(b) >= 3:
                back.append(Polygon(b, color))
        return coplanar_front, coplanar_back, front, back


class Polygon:
    """A convex polygon (initially a triangle, possibly split later)."""

    __slots__ = ("vertices", "plane", "color")

    def __init__(
        self,
        vertices: Sequence[Vec3],
        color: Optional[RGB] = None,
        plane: Optional[Plane] = None,
    ) -> None:
        self.vertices: List[Vec3] = [Vec3(v.x, v.y, v.z) for v in vertices]
        self.color = color
        self.plane = plane if plane is not None else Plane.from_polygon(self)
        if self.plane is None:
            # degenerate polygon: fabricate a plane so callers never crash
            self.plane = Plane(Vec3(0.0, 0.0, 1.0), 0.0)

    def flip(self) -> None:
        self.vertices.reverse()
        if self.plane is not None:
            self.plane.flip()

    def clone(self) -> "Polygon":
        return Polygon(self.vertices, self.color, self.plane)


class Node:
    """A node of a BSP tree holding coplanar polygons and two children."""

    __slots__ = ("plane", "front", "back", "polygons")

    def __init__(self, polygons: Optional[Sequence[Polygon]] = None) -> None:
        self.plane: Optional[Plane] = None
        self.front: Optional[Node] = None
        self.back: Optional[Node] = None
        self.polygons: List[Polygon] = []
        if polygons:
            self.build(list(polygons))

    # ------------------------------------------------------------------ #
    def invert(self) -> None:
        """Recursively flip the whole subtree (inside-out)."""
        for poly in self.polygons:
            poly.flip()
        if self.plane is not None:
            self.plane.flip()
        self.front, self.back = self.back, self.front
        if self.front is not None:
            self.front.invert()
        if self.back is not None:
            self.back.invert()

    # ------------------------------------------------------------------ #
    def clip_polygons(self, polygons: Sequence[Polygon]) -> List[Polygon]:
        """Clip polygons against this tree, dropping everything behind it."""
        if self.plane is None:
            return list(polygons)
        front: List[Polygon] = []
        back: List[Polygon] = []
        for poly in polygons:
            cf, cb, f, b = self.plane.split_polygon(poly)
            front.extend(cf)
            front.extend(f)
            back.extend(cb)
            back.extend(b)
        if self.front is not None:
            front = self.front.clip_polygons(front)
        if self.back is not None:
            back = self.back.clip_polygons(back)
        else:
            back = []
        return front + back

    def clip_to(self, bsp: "Node") -> None:
        """Remove the parts of this tree that lie outside ``bsp``."""
        self.polygons = bsp.clip_polygons(self.polygons)
        if self.front is not None:
            self.front.clip_to(bsp)
        if self.back is not None:
            self.back.clip_to(bsp)

    # ------------------------------------------------------------------ #
    def all_polygons(self) -> List[Polygon]:
        result: List[Polygon] = []
        if self.front is not None:
            result.extend(self.front.all_polygons())
        result.extend(self.polygons)
        if self.back is not None:
            result.extend(self.back.all_polygons())
        return result

    # ------------------------------------------------------------------ #
    def build(self, polygons: Sequence[Polygon]) -> None:
        """Insert polygons into the tree, splitting them at each node plane."""
        if not polygons:
            return
        if self.plane is None:
            self.plane = polygons[0].plane.clone()
        front: List[Polygon] = []
        back: List[Polygon] = []
        for poly in polygons:
            cf, cb, f, b = self.plane.split_polygon(poly)
            self.polygons.extend(cf)
            self.polygons.extend(cb)
            front.extend(f)
            back.extend(b)
        if front:
            if self.front is None:
                self.front = Node()
            self.front.build(front)
        if back:
            if self.back is None:
                self.back = Node()
            self.back.build(back)


# ---------------------------------------------------------------------- #
# mesh <-> polygon conversion                                             #
# ---------------------------------------------------------------------- #
def _mesh_to_polygons(mesh: Mesh) -> List[Polygon]:
    colors = mesh.colors if mesh.colors is not None else [None] * len(mesh.faces)
    polygons: List[Polygon] = []
    for (i, j, k), color in zip(mesh.faces, colors):
        polygons.append(
            Polygon([mesh.vertices[i], mesh.vertices[j], mesh.vertices[k]], color)
        )
    return polygons


def _weld_vertices(
    vertices: List[Vec3], faces: List[Tuple[int, int, int]], tol: float
) -> Tuple[List[Vec3], List[Tuple[int, int, int]], List[int]]:
    """Merge vertices closer than ``tol`` and drop degenerate/duplicate faces.

    Returns the merged vertices, the remapped faces and, for every kept face,
    the index of the original face it came from (so per-face colors stay
    aligned).  A uniform grid keeps the pass near-linear.
    """
    cell = tol if tol > 0 else 1.0
    grid: Dict[Tuple[int, int, int], List[int]] = {}
    remap: List[int] = [0] * len(vertices)
    kept: List[Vec3] = []
    for i, v in enumerate(vertices):
        gx, gy, gz = math.floor(v.x / cell), math.floor(v.y / cell), math.floor(v.z / cell)
        target = None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in grid.get((gx + dx, gy + dy, gz + dz), ()):
                        if (kept[remap[j]] - v).length_sq() <= tol * tol:
                            target = remap[j]
                            break
                    if target is not None:
                        break
                if target is not None:
                    break
            if target is not None:
                break
        if target is None:
            target = len(kept)
            kept.append(v)
            grid.setdefault((gx, gy, gz), []).append(i)
        remap[i] = target

    seen = set()
    new_faces: List[Tuple[int, int, int]] = []
    origin: List[int] = []
    for fi, (i, j, k) in enumerate(faces):
        tri = (remap[i], remap[j], remap[k])
        if tri[0] == tri[1] or tri[1] == tri[2] or tri[0] == tri[2]:
            continue
        key = tuple(sorted(tri))
        if key in seen:
            continue
        seen.add(key)
        new_faces.append(tri)
        origin.append(fi)
    return kept, new_faces, origin


def _polygons_to_mesh(
    polygons: Iterable[Polygon], name: str = "model", units: str = "mm"
) -> Mesh:
    """Rebuild a welded, manifold mesh from BSP polygons.

    Duplicate coplanar faces contributed by both operands are dropped at the
    polygon level (same plane and vertex set — they only differ in fan diagonal
    or winding).  Vertices are then welded with a small tolerance so that split
    points created along curved seams coincide again, and degenerate/duplicate
    triangles are removed.
    """
    raw_vertices: List[Vec3] = []
    raw_faces: List[Tuple[int, int, int]] = []
    raw_colors: List[Optional[RGB]] = []
    poly_seen = set()

    for poly in polygons:
        if len(poly.vertices) < 3:
            continue
        vkey = frozenset(
            (round(v.x, 5), round(v.y, 5), round(v.z, 5)) for v in poly.vertices
        )
        nrm = poly.plane.normal
        pkey = (
            round(nrm.x, 4), round(nrm.y, 4), round(nrm.z, 4),
            round(poly.plane.w, 4), vkey,
        )
        if pkey in poly_seen:
            continue
        poly_seen.add(pkey)
        base = len(raw_vertices)
        raw_vertices.extend(poly.vertices)
        idxs = list(range(base, base + len(poly.vertices)))
        for t in range(1, len(idxs) - 1):
            tri = (idxs[0], idxs[t], idxs[t + 1])
            if tri[0] == tri[1] or tri[1] == tri[2] or tri[0] == tri[2]:
                continue
            raw_faces.append(tri)
            raw_colors.append(poly.color)

    vertices, faces, origin = _weld_vertices(raw_vertices, raw_faces, tol=1e-4)
    has_color = any(c is not None for c in raw_colors)
    colors: Optional[List[RGB]] = None
    if has_color:
        colors = [
            raw_colors[fi] if raw_colors[fi] is not None else (0.75, 0.75, 0.75)
            for fi in origin
        ]
    mesh = Mesh(vertices, faces, colors, name, units)
    return mesh.fix_orientation()


# ---------------------------------------------------------------------- #
# boolean operations                                                      #
# ---------------------------------------------------------------------- #
def _prepare(mesh: Mesh) -> Node:
    return Node(_mesh_to_polygons(mesh))


def union(a: Mesh, b: Mesh) -> Mesh:
    """Boolean union of two closed meshes (``a OR b``)."""
    if a.is_empty():
        return b.copy()
    if b.is_empty():
        return a.copy()
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))
    node_a = _prepare(a)
    node_b = _prepare(b)
    node_a.clip_to(node_b)
    node_b.clip_to(node_a)
    node_b.invert()
    node_b.clip_to(node_a)
    node_b.invert()
    node_a.build(node_b.all_polygons())
    return _polygons_to_mesh(node_a.all_polygons(), name=a.name, units=a.units)


def subtract(a: Mesh, b: Mesh) -> Mesh:
    """Boolean difference of two closed meshes (``a AND NOT b``)."""
    if a.is_empty():
        return a.copy()
    if b.is_empty():
        return a.copy()
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))
    node_a = _prepare(a)
    node_b = _prepare(b)
    node_a.invert()
    node_a.clip_to(node_b)
    node_b.clip_to(node_a)
    node_b.invert()
    node_b.clip_to(node_a)
    node_b.invert()
    node_a.build(node_b.all_polygons())
    node_a.invert()
    return _polygons_to_mesh(node_a.all_polygons(), name=a.name, units=a.units)


def intersect(a: Mesh, b: Mesh) -> Mesh:
    """Boolean intersection of two closed meshes (``a AND b``)."""
    if a.is_empty() or b.is_empty():
        return Mesh.empty(name=a.name, units=a.units)
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20000))
    node_a = _prepare(a)
    node_b = _prepare(b)
    node_a.invert()
    node_b.clip_to(node_a)
    node_b.invert()
    node_a.clip_to(node_b)
    node_b.clip_to(node_a)
    node_a.build(node_b.all_polygons())
    node_a.invert()
    return _polygons_to_mesh(node_a.all_polygons(), name=a.name, units=a.units)


def union_all(meshes: Sequence[Mesh]) -> Mesh:
    """Union of any number of meshes (empty input yields an empty mesh)."""
    if not meshes:
        return Mesh.empty()
    result = meshes[0].copy()
    for m in meshes[1:]:
        result = union(result, m)
    return result


def subtract_all(base: Mesh, cutters: Sequence[Mesh]) -> Mesh:
    """``base`` minus every mesh in ``cutters``."""
    result = base.copy()
    for cutter in cutters:
        result = subtract(result, cutter)
    return result
