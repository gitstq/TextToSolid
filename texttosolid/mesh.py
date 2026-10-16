"""Indexed triangle mesh — the core data structure of TextToSolid.

A mesh stores vertices, triangle faces (index triples, counter-clockwise when
seen from outside the solid) and optional per-face RGB colors.  All helpers in
this module are pure standard library.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from .vec import Vec3

__all__ = ["Mesh"]

RGB = Tuple[float, float, float]
WELD_DECIMALS = 7  # vertex welding precision (coordinates are snapped)


class Mesh:
    """An indexed triangle mesh.

    Parameters
    ----------
    vertices:
        Sequence of :class:`Vec3` points.
    faces:
        Sequence of ``(i, j, k)`` index triples.
    colors:
        Optional per-face ``(r, g, b)`` tuples with components in ``[0, 1]``.
    name:
        Model name (used by exporters).
    units:
        Unit string such as ``"mm"`` or ``"in"``.
    """

    __slots__ = ("vertices", "faces", "colors", "name", "units")

    def __init__(
        self,
        vertices: Optional[Sequence[Vec3]] = None,
        faces: Optional[Sequence[Sequence[int]]] = None,
        colors: Optional[Sequence[RGB]] = None,
        name: str = "model",
        units: str = "mm",
    ) -> None:
        self.vertices: List[Vec3] = [Vec3(v.x, v.y, v.z) for v in vertices] if vertices else []
        self.faces: List[Tuple[int, int, int]] = [
            (int(f[0]), int(f[1]), int(f[2])) for f in faces
        ] if faces else []
        self.colors: Optional[List[RGB]] = (
            [(float(c[0]), float(c[1]), float(c[2])) for c in colors]
            if colors is not None
            else None
        )
        self.name = name
        self.units = units

    # ------------------------------------------------------------------ #
    # basic info                                                          #
    # ------------------------------------------------------------------ #
    @classmethod
    def empty(cls, name: str = "empty", units: str = "mm") -> "Mesh":
        return cls(name=name, units=units)

    @property
    def triangle_count(self) -> int:
        return len(self.faces)

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    def is_empty(self) -> bool:
        return not self.faces or not self.vertices

    def copy(self) -> "Mesh":
        return Mesh(self.vertices, self.faces, self.colors, self.name, self.units)

    def save(self, path: str, ascii: bool = False, **kwargs) -> str:
        """Export this mesh, dispatching on the file extension (.stl/.obj/.svg)."""
        from .export import save as _save  # lazy import avoids an import cycle
        return _save(self, path, ascii=ascii, **kwargs)

    def __repr__(self) -> str:
        return "Mesh(name={0!r}, triangles={1}, vertices={2})".format(
            self.name, self.triangle_count, self.vertex_count
        )

    # ------------------------------------------------------------------ #
    # extents                                                             #
    # ------------------------------------------------------------------ #
    def bounds(self) -> Optional[Tuple[Vec3, Vec3]]:
        """Return ``(min_corner, max_corner)`` of the axis-aligned bbox."""
        if not self.vertices:
            return None
        xs = [v.x for v in self.vertices]
        ys = [v.y for v in self.vertices]
        zs = [v.z for v in self.vertices]
        return (Vec3(min(xs), min(ys), min(zs)), Vec3(max(xs), max(ys), max(zs)))

    def size(self) -> Optional[Vec3]:
        """Overall dimensions ``(dx, dy, dz)`` of the bounding box."""
        b = self.bounds()
        if b is None:
            return None
        return b[1] - b[0]

    def center(self) -> Optional[Vec3]:
        b = self.bounds()
        if b is None:
            return None
        return (b[0] + b[1]) * 0.5

    # ------------------------------------------------------------------ #
    # per-face geometry                                                   #
    # ------------------------------------------------------------------ #
    def face_normal(self, face: Sequence[int]) -> Vec3:
        a, b, c = (self.vertices[i] for i in face)
        n = (b - a).cross(c - a)
        if n.length_sq() == 0.0:
            return Vec3(0.0, 0.0, 0.0)
        return n.normalized()

    # ------------------------------------------------------------------ #
    # measurements                                                        #
    # ------------------------------------------------------------------ #
    def volume(self) -> float:
        """Signed volume (positive when faces wind counter-clockwise outward)."""
        total = 0.0
        for i, j, k in self.faces:
            a = self.vertices[i]
            b = self.vertices[j]
            c = self.vertices[k]
            total += a.dot(b.cross(c)) / 6.0
        return total

    def surface_area(self) -> float:
        total = 0.0
        for i, j, k in self.faces:
            a = self.vertices[i]
            b = self.vertices[j]
            c = self.vertices[k]
            total += 0.5 * (b - a).cross(c - a).length()
        return total

    def center_of_mass(self) -> Optional[Vec3]:
        """Centroid of the solid assuming uniform density (None if degenerate)."""
        vol = 0.0
        cx = cy = cz = 0.0
        for i, j, k in self.faces:
            a = self.vertices[i]
            b = self.vertices[j]
            c = self.vertices[k]
            tet = a.dot(b.cross(c)) / 6.0
            vol += tet
            cx += (a.x + b.x + c.x) / 4.0 * tet
            cy += (a.y + b.y + c.y) / 4.0 * tet
            cz += (a.z + b.z + c.z) / 4.0 * tet
        if abs(vol) < 1e-12:
            return None
        return Vec3(cx / vol, cy / vol, cz / vol)

    def degenerate_faces(self) -> List[int]:
        """Indices of zero-area or repeated-index faces."""
        bad: List[int] = []
        for idx, (i, j, k) in enumerate(self.faces):
            if i == j or j == k or i == k:
                bad.append(idx)
                continue
            a = self.vertices[i]
            b = self.vertices[j]
            c = self.vertices[k]
            if (b - a).cross(c - a).length_sq() <= 1e-18:
                bad.append(idx)
        return bad

    def edge_counts(self) -> Dict[Tuple[int, int], int]:
        counts: Dict[Tuple[int, int], int] = {}
        for i, j, k in self.faces:
            for a, b in ((i, j), (j, k), (k, i)):
                edge = (a, b) if a < b else (b, a)
                counts[edge] = counts.get(edge, 0) + 1
        return counts

    def non_manifold_edges(self) -> List[Tuple[int, int]]:
        """Edges not shared by exactly two faces (boundary or junction edges)."""
        return [edge for edge, count in self.edge_counts().items() if count != 2]

    def is_watertight(self) -> bool:
        """True when every edge is shared by exactly two faces (closed solid)."""
        if self.is_empty():
            return False
        return not self.non_manifold_edges()

    # ------------------------------------------------------------------ #
    # repair helpers                                                      #
    # ------------------------------------------------------------------ #
    def fix_orientation(self) -> "Mesh":
        """Flip every face when the mesh is closed but wound inside-out."""
        if self.is_empty():
            return self
        if self.is_watertight() and self.volume() < 0.0:
            self.faces = [(k, j, i) for (i, j, k) in self.faces]
        return self

    def repair_winding(self) -> "Mesh":
        """Make face winding mutually consistent for closed manifold meshes.

        Faces are re-oriented by a BFS over shared edges: two faces sharing an
        edge must traverse that edge in opposite directions.  Afterwards the
        whole mesh is flipped globally if needed so that normals point outward.
        Best-effort: faces unreachable through the adjacency walk (possible for
        non-manifold input) keep their original orientation.
        """
        if self.is_empty() or not self.faces:
            return self
        adjacency: Dict[Tuple[int, int], List[int]] = {}
        for fi, (i, j, k) in enumerate(self.faces):
            for a, b in ((i, j), (j, k), (k, i)):
                edge = (a, b) if a < b else (b, a)
                adjacency.setdefault(edge, []).append(fi)

        oriented = [False] * len(self.faces)
        directed: List[Optional[Tuple[Tuple[int, int], Tuple[int, int], Tuple[int, int]]]] = [
            None
        ] * len(self.faces)
        for start in range(len(self.faces)):
            if oriented[start]:
                continue
            oriented[start] = True
            directed[start] = self.faces[start]
            stack = [start]
            while stack:
                fi = stack.pop()
                i, j, k = directed[fi]
                for a, b in ((i, j), (j, k), (k, i)):
                    edge = (a, b) if a < b else (b, a)
                    for nb in adjacency.get(edge, ()):  # neighbours over the edge
                        if oriented[nb] or nb == fi:
                            continue
                        ni, nj, nk = self.faces[nb]
                        # the neighbour must traverse the shared edge backwards
                        if (a, b) in ((ni, nj), (nj, nk), (nk, ni)):
                            directed[nb] = (nk, nj, ni)  # flip
                        else:
                            directed[nb] = (ni, nj, nk)
                        oriented[nb] = True
                        stack.append(nb)
        if all(d is not None for d in directed):
            self.faces = [tuple(d) for d in directed]  # type: ignore[arg-type]
        return self.fix_orientation()

    # ------------------------------------------------------------------ #
    # combination                                                         #
    # ------------------------------------------------------------------ #
    def merge(self, other: "Mesh") -> "Mesh":
        """Concatenate another mesh into this one (no boolean operation)."""
        if other.is_empty():
            return self
        offset = len(self.vertices)
        if self.colors is not None or other.colors is not None:
            if self.colors is None:
                self.colors = [(0.75, 0.75, 0.75)] * len(self.faces)
            extra = other.colors if other.colors is not None else [
                (0.75, 0.75, 0.75)
            ] * len(other.faces)
            self.colors = list(self.colors) + list(extra)
        self.vertices.extend(v.copy() for v in other.vertices)
        self.faces.extend((i + offset, j + offset, k + offset) for i, j, k in other.faces)
        return self

    # ------------------------------------------------------------------ #
    # welding                                                             #
    # ------------------------------------------------------------------ #
    def weld(self, decimals: int = WELD_DECIMALS) -> "Mesh":
        """Merge duplicate vertices and drop duplicate/degenerate faces.

        Used after CSG operations so that split vertices coincide again and the
        result stays manifold-checkable.
        """
        if self.is_empty():
            return self
        index_of: Dict[Tuple[float, float, float], int] = {}
        remap: List[int] = []
        new_vertices: List[Vec3] = []
        for v in self.vertices:
            key = (round(v.x, decimals), round(v.y, decimals), round(v.z, decimals))
            idx = index_of.get(key)
            if idx is None:
                idx = len(new_vertices)
                index_of[key] = idx
                new_vertices.append(v.copy())
            remap.append(idx)

        seen_faces = set()
        new_faces: List[Tuple[int, int, int]] = []
        new_colors: Optional[List[RGB]] = [] if self.colors is not None else None
        for fi, (i, j, k) in enumerate(self.faces):
            tri = (remap[i], remap[j], remap[k])
            if tri[0] == tri[1] or tri[1] == tri[2] or tri[0] == tri[2]:
                if new_colors is not None:
                    new_colors.append(self.colors[fi])
                continue
            key = tuple(sorted(tri))
            if key in seen_faces:
                if new_colors is not None:
                    new_colors.append(self.colors[fi])
                continue
            seen_faces.add(key)
            new_faces.append(tri)
            if new_colors is not None:
                new_colors.append(self.colors[fi])

        self.vertices = new_vertices
        self.faces = new_faces
        self.colors = new_colors
        return self
