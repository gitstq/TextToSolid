"""Rigid and non-rigid transforms for meshes.

All functions return a new mesh; the input is never modified.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple, Union

from .mesh import Mesh
from .vec import Vec3

__all__ = ["translate", "rotate", "scale", "mirror"]


def translate(mesh: Mesh, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> Mesh:
    """Move a mesh by ``(dx, dy, dz)``."""
    out = mesh.copy()
    offset = Vec3(dx, dy, dz)
    if offset.x or offset.y or offset.z:
        out.vertices = [v + offset for v in out.vertices]
    return out


def rotate(
    mesh: Mesh,
    rx: float = 0.0,
    ry: float = 0.0,
    rz: float = 0.0,
) -> Mesh:
    """Rotate a mesh by Euler angles in degrees.

    The rotation is applied in X -> Y -> Z order (extrinsic XYZ), which matches
    the ``rotate=(rx, ry, rz)`` argument of the TextToSolid DSL.
    """
    if rx == 0.0 and ry == 0.0 and rz == 0.0:
        return mesh.copy()
    ax, ay, az = math.radians(rx), math.radians(ry), math.radians(rz)
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    out = mesh.copy()
    new_vertices = []
    for v in out.vertices:
        # rotate around X
        x, y, z = v.x, v.y, v.z
        y, z = y * cx - z * sx, y * sx + z * cx
        # rotate around Y
        x, z = x * cy + z * sy, -x * sy + z * cy
        # rotate around Z
        x, y = x * cz - y * sz, x * sz + y * cz
        new_vertices.append(Vec3(x, y, z))
    out.vertices = new_vertices
    return out


def scale(
    mesh: Mesh,
    s: Union[float, Tuple[float, float, float]],
    sy: Optional[float] = None,
    sz: Optional[float] = None,
) -> Mesh:
    """Scale a mesh uniformly (``s``) or per-axis (``sx, sy, sz``)."""
    if isinstance(s, (tuple, list)):
        if len(s) != 3:
            raise ValueError("scale tuple must have 3 components")
        sx, sy, sz = float(s[0]), float(s[1]), float(s[2])
    else:
        sx = float(s)
        if sy is None and sz is None:
            sy = sz = sx
        else:
            sy = float(sy if sy is not None else sx)
            sz = float(sz if sz is not None else sx)
    if sx == 0.0 or sy == 0.0 or sz == 0.0:
        raise ValueError("scale factors must be non-zero")
    out = mesh.copy()
    out.vertices = [Vec3(v.x * sx, v.y * sy, v.z * sz) for v in out.vertices]
    if sx * sy * sz < 0:
        # an odd number of negative factors mirrors the solid
        out.fix_orientation()
    return out


def mirror(mesh: Mesh, axis: Union[str, int] = "x") -> Mesh:
    """Mirror a mesh across the plane through the origin perpendicular to ``axis``.

    ``axis`` may be ``"x"``/``"y"``/``"z"`` or ``0``/``1``/``2``.
    """
    index = {"x": 0, "y": 1, "z": 2}.get(str(axis).lower())
    if index is None:
        try:
            index = int(axis)
        except (TypeError, ValueError):
            raise ValueError("mirror axis must be 'x', 'y', 'z' or 0/1/2")
        if index not in (0, 1, 2):
            raise ValueError("mirror axis must be 'x', 'y', 'z' or 0/1/2")
    out = mesh.copy()
    new_vertices = []
    for v in out.vertices:
        x, y, z = v.x, v.y, v.z
        if index == 0:
            x = -x
        elif index == 1:
            y = -y
        else:
            z = -z
        new_vertices.append(Vec3(x, y, z))
    out.vertices = new_vertices
    out.fix_orientation()  # mirroring inverts the winding
    return out
