"""Mesh exporters: binary/ASCII STL, OBJ and SVG preview rendering.

All exporters are pure standard library.  ``save`` dispatches on the file
extension (``.stl``, ``.obj``, ``.svg``).
"""
from __future__ import annotations

import math
import os
import struct
from typing import Iterable, List, Optional, Sequence, Tuple

from .errors import ExportError
from .mesh import Mesh
from .vec import Vec3

__all__ = [
    "save",
    "save_stl",
    "save_obj",
    "save_svg",
    "mesh_to_stl_binary",
    "mesh_to_stl_ascii",
    "mesh_to_obj",
    "mesh_to_svg",
]


# ---------------------------------------------------------------------- #
# STL                                                                    #
# ---------------------------------------------------------------------- #
def mesh_to_stl_binary(mesh: Mesh) -> bytes:
    """Binary STL payload (80-byte header, uint32 count, 50 bytes per tri)."""
    header = b"TextToSolid binary STL"
    header = header + b"\x00" * (80 - len(header))
    parts = [header, struct.pack("<I", len(mesh.faces))]
    for face in mesh.faces:
        a, b, c = (mesh.vertices[i] for i in face)
        normal = (b - a).cross(c - a)
        if normal.length_sq() > 0.0:
            normal = normal.normalized()
        else:
            normal = Vec3(0.0, 0.0, 0.0)
        parts.append(
            struct.pack(
                "<12fH",
                normal.x, normal.y, normal.z,
                a.x, a.y, a.z,
                b.x, b.y, b.z,
                c.x, c.y, c.z,
                0,
            )
        )
    return b"".join(parts)


def mesh_to_stl_ascii(mesh: Mesh) -> str:
    """ASCII STL document."""
    lines = ["solid {0}".format(mesh.name)]
    for face in mesh.faces:
        a, b, c = (mesh.vertices[i] for i in face)
        normal = (b - a).cross(c - a)
        if normal.length_sq() > 0.0:
            normal = normal.normalized()
        else:
            normal = Vec3(0.0, 0.0, 0.0)
        lines.append(
            "  facet normal {0:.6e} {1:.6e} {2:.6e}".format(normal.x, normal.y, normal.z)
        )
        lines.append("    outer loop")
        for v in (a, b, c):
            lines.append("      vertex {0:.6e} {1:.6e} {2:.6e}".format(v.x, v.y, v.z))
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append("endsolid {0}".format(mesh.name))
    return "\n".join(lines) + "\n"


def save_stl(mesh: Mesh, path: str, ascii: bool = False) -> str:
    if ascii:
        _write_text(path, mesh_to_stl_ascii(mesh))
    else:
        _write_bytes(path, mesh_to_stl_binary(mesh))
    return path


# ---------------------------------------------------------------------- #
# OBJ                                                                    #
# ---------------------------------------------------------------------- #
def mesh_to_obj(mesh: Mesh) -> str:
    """Wavefront OBJ document.

    When the mesh carries per-face colors they are averaged onto the vertices
    and written with the widely supported ``v x y z r g b`` extension.
    """
    vertex_colors: Optional[List[Tuple[float, float, float]]] = None
    if mesh.colors is not None:
        sums = [[0.0, 0.0, 0.0] for _ in mesh.vertices]
        counts = [0 for _ in mesh.vertices]
        for (i, j, k), color in zip(mesh.faces, mesh.colors):
            for idx in (i, j, k):
                sums[idx][0] += color[0]
                sums[idx][1] += color[1]
                sums[idx][2] += color[2]
                counts[idx] += 1
        vertex_colors = [
            (s[0] / c if c else 0.75, s[1] / c if c else 0.75, s[2] / c if c else 0.75)
            for s, c in zip(sums, counts)
        ]

    lines = [
        "# TextToSolid OBJ export",
        "# units: {0}".format(mesh.units),
        "o {0}".format(mesh.name),
    ]
    for idx, v in enumerate(mesh.vertices):
        if vertex_colors is not None:
            c = vertex_colors[idx]
            lines.append(
                "v {0:.6f} {1:.6f} {2:.6f} {3:.4f} {4:.4f} {5:.4f}".format(
                    v.x, v.y, v.z, c[0], c[1], c[2]
                )
            )
        else:
            lines.append("v {0:.6f} {1:.6f} {2:.6f}".format(v.x, v.y, v.z))
    for face in mesh.faces:
        i, j, k = face
        lines.append("f {0} {1} {2}".format(i + 1, j + 1, k + 1))
    return "\n".join(lines) + "\n"


def save_obj(mesh: Mesh, path: str) -> str:
    _write_text(path, mesh_to_obj(mesh))
    return path


# ---------------------------------------------------------------------- #
# SVG preview                                                            #
# ---------------------------------------------------------------------- #
def _rotate_view(v: Vec3, yaw: float, pitch: float) -> Vec3:
    """Rotate a point for the preview camera (yaw around Y, then pitch around X)."""
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    x = v.x * cy + v.z * sy
    z = -v.x * sy + v.z * cy
    y = v.y
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    y, z = y * cp - z * sp, y * sp + z * cp
    return Vec3(x, y, z)


def _hex(color: Tuple[float, float, float], brightness: float) -> str:
    r = min(255, max(0, int(round(color[0] * brightness * 255))))
    g = min(255, max(0, int(round(color[1] * brightness * 255))))
    b = min(255, max(0, int(round(color[2] * brightness * 255))))
    return "#{0:02x}{1:02x}{2:02x}".format(r, g, b)


def mesh_to_svg(
    mesh: Mesh,
    width: int = 640,
    height: int = 480,
    yaw: float = 35.0,
    pitch: float = 25.0,
    background: str = "#ffffff",
    default_color: Tuple[float, float, float] = (0.31, 0.49, 1.0),
    light: Tuple[float, float, float] = (0.35, 0.55, 0.76),
    margin: float = 12.0,
    show_edges: bool = False,
) -> str:
    """Render a shaded preview of the mesh as an SVG document.

    Uses an orthographic camera with a painter's-algorithm sort — good enough
    for documentation previews without any 3D dependency.
    """
    if mesh.is_empty():
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="{0}" height="{1}" '
            'viewBox="0 0 {0} {1}"><rect width="100%" height="100%" fill="{2}"/>'
            "<text x=\"{3}\" y=\"{4}\" fill=\"#888\" font-family=\"sans-serif\" "
            "font-size=\"14\">empty model</text></svg>\n".format(
                width, height, background, width / 2, height / 2
            )
        )

    projected = [_rotate_view(v, yaw, pitch) for v in mesh.vertices]
    light_dir = Vec3(*light).normalized()

    tris = []
    for fi, (i, j, k) in enumerate(mesh.faces):
        p0, p1, p2 = projected[i], projected[j], projected[k]
        area2 = (p1.x - p0.x) * (p2.y - p0.y) - (p1.y - p0.y) * (p2.x - p0.x)
        if abs(area2) < 1e-9:
            continue  # edge-on or degenerate in screen space
        depth = (p0.z + p1.z + p2.z) / 3.0
        n = _rotate_view(mesh.face_normal((i, j, k)), yaw, pitch)
        if n.length_sq() == 0.0:
            shade = 0.25
        else:
            n = n.normalized()
            if n.z < 0:
                n = -n  # always shade the side facing the camera
            shade = 0.25 + 0.75 * max(0.0, n.dot(light_dir))
        base = (0.75, 0.75, 0.75)
        if mesh.colors is not None and fi < len(mesh.colors):
            base = mesh.colors[fi]
        else:
            base = default_color
        tris.append((depth, area2, p0, p1, p2, base, shade))

    if not tris:
        return _empty_svg(width, height, background)

    xs = [p.x for t in tris for p in t[2:5]]
    ys = [p.y for t in tris for p in t[2:5]]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1e-9)
    span_y = max(max_y - min_y, 1e-9)
    scale = min((width - 2 * margin) / span_x, (height - 2 * margin) / span_y)
    off_x = (width - span_x * scale) / 2.0
    off_y = (height - span_y * scale) / 2.0

    def to_screen(p: Vec3) -> Tuple[float, float]:
        return (off_x + (p.x - min_x) * scale, off_y + (p.y - min_y) * scale)

    # painter's algorithm: draw far (small depth) first
    tris.sort(key=lambda t: t[0])

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="{0}" height="{1}" '
        'viewBox="0 0 {0} {1}">'.format(width, height),
        '<rect width="100%" height="100%" fill="{0}"/>'.format(background),
        "<g stroke-linejoin=\"round\">",
    ]
    for depth, area2, p0, p1, p2, base, shade in tris:
        (x0, y0), (x1, y1), (x2, y2) = to_screen(p0), to_screen(p1), to_screen(p2)
        stroke = ' stroke="{0}" stroke-width="0.4"'.format(_hex(base, shade * 0.6)) if show_edges else ""
        parts.append(
            '<polygon points="{0:.2f},{1:.2f} {2:.2f},{3:.2f} {4:.2f},{5:.2f}" '
            'fill="{6}"{7}/>'.format(x0, y0, x1, y1, x2, y2, _hex(base, shade), stroke)
        )
    parts.append("</g>")
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _empty_svg(width: int, height: int, background: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="{0}" height="{1}" '
        'viewBox="0 0 {0} {1}"><rect width="100%" height="100%" fill="{2}"/></svg>\n'.format(
            width, height, background
        )
    )


def save_svg(mesh: Mesh, path: str, **kwargs) -> str:
    _write_text(path, mesh_to_svg(mesh, **kwargs))
    return path


# ---------------------------------------------------------------------- #
# dispatch                                                               #
# ---------------------------------------------------------------------- #
def save(mesh: Mesh, path: str, ascii: bool = False, **kwargs) -> str:
    """Save a mesh, dispatching on the file extension.

    ``.stl`` -> STL (binary by default, ASCII with ``ascii=True``)
    ``.obj`` -> Wavefront OBJ
    ``.svg`` -> SVG preview
    """
    ext = os.path.splitext(path)[1].lower()
    if ext == ".stl":
        return save_stl(mesh, path, ascii=ascii)
    if ext == ".obj":
        return save_obj(mesh, path)
    if ext == ".svg":
        return save_svg(mesh, path, **kwargs)
    raise ExportError("unsupported export format: {0!r}".format(ext))


# ---------------------------------------------------------------------- #
# io helpers                                                             #
# ---------------------------------------------------------------------- #
def _write_bytes(path: str, payload: bytes) -> None:
    try:
        with open(path, "wb") as handle:
            handle.write(payload)
    except OSError as exc:
        raise ExportError("cannot write {0}: {1}".format(path, exc))


def _write_text(path: str, payload: str) -> None:
    try:
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    except OSError as exc:
        raise ExportError("cannot write {0}: {1}".format(path, exc))
