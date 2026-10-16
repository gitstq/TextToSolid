"""Agent-friendly JSON protocol for TextToSolid.

Instead of parsing prose, an AI agent can emit a small JSON document that
describes a solid declaratively::

    {
      "name": "bracket",
      "units": "mm",
      "shapes": [
        {"op": "box", "w": 40, "d": 20, "h": 4},
        {"op": "difference", "shapes": [
          {"op": "cylinder", "r": 3, "h": 12}
        ]}
      ]
    }

:func:`build_from_spec` turns such a document into a :class:`Mesh`, and
:func:`model_info` returns a JSON-serializable measurement report.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from . import csg
from .errors import MeshError, ParseError
from .mesh import Mesh, RGB
from .primitives import box, cone, cylinder, pyramid, sphere, torus, tube, wedge
from .profiles import extrude, revolve
from .transforms import mirror, rotate, scale, translate

__all__ = ["build_from_spec", "model_info", "describe"]


# ---------------------------------------------------------------------- #
# spec -> mesh                                                           #
# ---------------------------------------------------------------------- #
def _require_number(value: Any, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ParseError("parameter {0!r} must be a number, got {1!r}".format(key, value))
    return float(value)


def _parse_color(value: Any) -> RGB:
    if isinstance(value, str):
        from .dsl import _parse_color as _pc  # reuse the DSL color parser
        return _pc(value)
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return tuple(min(1.0, max(0.0, float(c))) for c in value)  # type: ignore[return-value]
    raise ParseError("invalid color: {0!r}".format(value))


def _point3(value: Any, key: str):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ParseError("{0!r} must be a 3-element list [x, y, z]".format(key))
    return (float(value[0]), float(value[1]), float(value[2]))


def _build_primitive(op: str, spec: Dict[str, Any]) -> Mesh:
    if op == "box":
        mesh = box(
            _require_number(spec.get("w", 1.0), "w"),
            _require_number(spec.get("d", 1.0), "d"),
            _require_number(spec.get("h", 1.0), "h"),
        )
    elif op == "sphere":
        mesh = sphere(
            _require_number(spec.get("r", 1.0), "r"),
            int(spec.get("segments", 24)),
            int(spec.get("rings", 12)),
        )
    elif op == "cylinder":
        mesh = cylinder(
            _require_number(spec.get("r", 1.0), "r"),
            _require_number(spec.get("h", 1.0), "h"),
            int(spec.get("segments", 32)),
        )
    elif op == "cone":
        mesh = cone(
            _require_number(spec.get("r1", 1.0), "r1"),
            _require_number(spec.get("r2", 0.0), "r2"),
            _require_number(spec.get("h", 1.0), "h"),
            int(spec.get("segments", 32)),
        )
    elif op == "torus":
        mesh = torus(
            _require_number(spec.get("R", 1.0), "R"),
            _require_number(spec.get("r", 0.3), "r"),
            int(spec.get("segments", 32)),
            int(spec.get("tube_segments", 12)),
        )
    elif op == "wedge":
        mesh = wedge(
            _require_number(spec.get("w", 1.0), "w"),
            _require_number(spec.get("d", 1.0), "d"),
            _require_number(spec.get("h", 1.0), "h"),
        )
    elif op == "tube":
        mesh = tube(
            _require_number(spec.get("r", 1.0), "r"),
            _require_number(spec.get("ri", 0.6), "ri"),
            _require_number(spec.get("h", 1.0), "h"),
            int(spec.get("segments", 32)),
        )
    elif op == "pyramid":
        mesh = pyramid(
            _require_number(spec.get("base", 1.0), "base"),
            _require_number(spec.get("h", 1.0), "h"),
        )
    else:  # pragma: no cover - guarded by the caller
        raise ParseError("unknown primitive op: {0!r}".format(op))
    if "at" in spec and spec["at"] is not None:
        mesh = translate(mesh, *_point3(spec["at"], "at"))
    if "color" in spec and spec["color"] is not None:
        mesh = mesh.copy()
        mesh.colors = [_parse_color(spec["color"])] * len(mesh.faces)
    return mesh


def _children(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    shapes = spec.get("shapes")
    if shapes is None:
        single = spec.get("shape")
        if single is None:
            raise ParseError("boolean/transform op needs 'shape' or 'shapes'")
        shapes = [single]
    if not isinstance(shapes, list) or not shapes:
        raise ParseError("'shapes' must be a non-empty list")
    return shapes


def _build_shape(spec: Any) -> Mesh:
    if not isinstance(spec, dict):
        raise ParseError("each shape must be a JSON object, got {0!r}".format(spec))
    op = spec.get("op") or spec.get("type")
    if not op or not isinstance(op, str):
        raise ParseError("shape is missing a string 'op' field")

    if op in ("box", "sphere", "cylinder", "cone", "torus", "wedge", "tube", "pyramid"):
        return _build_primitive(op, spec)

    if op == "union":
        meshes = [_build_shape(s) for s in _children(spec)]
        return csg.union_all(meshes)
    if op == "difference":
        meshes = [_build_shape(s) for s in _children(spec)]
        return csg.subtract_all(meshes[0], meshes[1:])
    if op == "intersection":
        meshes = [_build_shape(s) for s in _children(spec)]
        return csg.intersect(meshes[0], csg.union_all(meshes[1:]))

    if op in ("translate", "rotate", "scale", "mirror"):
        meshes = [_build_shape(s) for s in _children(spec)]
        base = csg.union_all(meshes)
        if op == "translate":
            return translate(base, *_point3(spec.get("offset", spec.get("at", [0, 0, 0])), "offset"))
        if op == "rotate":
            angles = spec.get("angles", spec.get("rotate", [0, 0, 0]))
            if not isinstance(angles, (list, tuple)) or len(angles) != 3:
                raise ParseError("rotate needs 'angles': [rx, ry, rz] in degrees")
            return rotate(base, float(angles[0]), float(angles[1]), float(angles[2]))
        if op == "scale":
            factor = spec.get("factor", spec.get("scale", 1.0))
            if isinstance(factor, (list, tuple)):
                if len(factor) != 3:
                    raise ParseError("scale 'factor' list must have 3 entries")
                return scale(base, (float(factor[0]), float(factor[1]), float(factor[2])))
            return scale(base, float(factor))
        axis = spec.get("axis", "x")
        return mirror(base, axis)

    if op == "extrude":
        profile = spec.get("profile") or spec.get("points")
        if not isinstance(profile, (list, tuple)) or len(profile) < 3:
            raise ParseError("extrude needs 'profile': [[x, y], ...] with >= 3 points")
        points = [(float(p[0]), float(p[1])) for p in profile]
        mesh = extrude(points, _require_number(spec.get("height", 1.0), "height"))
        if "at" in spec and spec["at"] is not None:
            mesh = translate(mesh, *_point3(spec["at"], "at"))
        return mesh
    if op == "revolve":
        profile = spec.get("profile") or spec.get("points")
        if not isinstance(profile, (list, tuple)) or len(profile) < 2:
            raise ParseError("revolve needs 'profile': [[radius, y], ...] with >= 2 points")
        points = [(float(p[0]), float(p[1])) for p in profile]
        mesh = revolve(
            points,
            float(spec.get("angle", 360.0)),
            int(spec.get("segments", 48)),
        )
        if "at" in spec and spec["at"] is not None:
            mesh = translate(mesh, *_point3(spec["at"], "at"))
        return mesh

    if op == "color":
        meshes = [_build_shape(s) for s in _children(spec)]
        mesh = csg.union_all(meshes).copy()
        mesh.colors = [_parse_color(spec.get("value", "#cccccc"))] * len(mesh.faces)
        return mesh

    raise ParseError("unknown op: {0!r}".format(op))


def build_from_spec(spec: Dict[str, Any]) -> Mesh:
    """Build a mesh from an agent JSON specification (see module docstring)."""
    if not isinstance(spec, dict):
        raise ParseError("spec must be a JSON object")
    shapes = spec.get("shapes")
    if not isinstance(shapes, list) or not shapes:
        raise ParseError("spec needs a non-empty 'shapes' list")
    meshes = [_build_shape(s) for s in shapes]
    result = csg.union_all(meshes)
    result.name = str(spec.get("name", "model"))
    result.units = str(spec.get("units", "mm"))
    return result


# ---------------------------------------------------------------------- #
# measurements                                                           #
# ---------------------------------------------------------------------- #
def model_info(mesh: Mesh) -> Dict[str, Any]:
    """Return a JSON-serializable measurement report for ``mesh``."""
    bounds = mesh.bounds()
    size = mesh.size()
    com = mesh.center_of_mass()
    volume = mesh.volume()
    info: Dict[str, Any] = {
        "name": mesh.name,
        "units": mesh.units,
        "triangles": mesh.triangle_count,
        "vertices": mesh.vertex_count,
        "volume": volume,
        "volume_abs": abs(volume),
        "surface_area": mesh.surface_area(),
        "watertight": mesh.is_watertight(),
        "non_manifold_edges": len(mesh.non_manifold_edges()),
        "degenerate_faces": len(mesh.degenerate_faces()),
        "bounding_box": None,
        "size": None,
        "center": None,
        "center_of_mass": None,
    }
    if bounds is not None:
        info["bounding_box"] = {
            "min": [bounds[0].x, bounds[0].y, bounds[0].z],
            "max": [bounds[1].x, bounds[1].y, bounds[1].z],
        }
    if size is not None:
        info["size"] = [size.x, size.y, size.z]
    center = mesh.center()
    if center is not None:
        info["center"] = [center.x, center.y, center.z]
    if com is not None:
        info["center_of_mass"] = [com.x, com.y, com.z]
    info["printable"] = bool(
        mesh.is_watertight()
        and not mesh.degenerate_faces()
        and abs(volume) > 1e-9
    )
    return info


def describe(mesh: Mesh) -> str:
    """Human-readable one-paragraph summary of a mesh."""
    info = model_info(mesh)
    size = info["size"] or [0.0, 0.0, 0.0]
    return (
        "{name}: {triangles} triangles, {vertices} vertices, "
        "bounding box {sx:.3f} x {sy:.3f} x {sz:.3f} {units}, "
        "volume {vol:.3f} {units}^3, {state}".format(
            name=info["name"],
            triangles=info["triangles"],
            vertices=info["vertices"],
            sx=size[0], sy=size[1], sz=size[2],
            units=info["units"],
            vol=info["volume_abs"],
            state="watertight (printable)" if info["printable"] else "NOT watertight",
        )
    )
