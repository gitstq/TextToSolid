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

import sys
from typing import Iterable, List, Optional, Sequence, Tuple

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


def _polygons_to_mesh(
    polygons: Iterable[Polygon], name: str = "model", units: str = "mm"
) -> Mesh:
    """Rebuild a welded mesh from BSP polygons.

    Vertices are snapped (welded) so that coincident split points share an
    index again; duplicate and degenerate faces are dropped.  This keeps the
    result manifold-checkable.
    """
    vertices: List[Vec3] = []
    index_of = {}
    faces: List[Tuple[int, int, int]] = []
    colors: List[RGB] = []
    has_color = False
    seen = set()

    for poly in polygons:
        if len(poly.vertices) < 3:
            continue
        # fan-triangulate (polygons stay convex after BSP splitting)
        idxs: List[int] = []
        for v in poly.vertices:
            key = (round(v.x, 7), round(v.y, 7), round(v.z, 7))
            idx = index_of.get(key)
            if idx is None:
                idx = len(vertices)
                index_of[key] = idx
                vertices.append(v)
            idxs.append(idx)
        for t in range(1, len(idxs) - 1):
            tri = (idxs[0], idxs[t], idxs[t + 1])
            if tri[0] == tri[1] or tri[1] == tri[2] or tri[0] == tri[2]:
                continue
            key = tuple(sorted(tri))
            if key in seen:
                continue
            seen.add(key)
            faces.append(tri)
            if poly.color is not None:
                colors.append(poly.color)
                has_color = True
            else:
                colors.append((0.75, 0.75, 0.75))

    mesh = Mesh(vertices, faces, colors if has_color else None, name, units)
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
