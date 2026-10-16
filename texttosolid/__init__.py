"""TextToSolid - zero-dependency parametric solid modeling in pure Python.

Turn text into watertight 3D solids: a small DSL, a BSP CSG engine, STL/OBJ/SVG
exporters and an agent-friendly JSON protocol.  Standard library only.
"""
from __future__ import annotations

__version__ = "1.0.0"
__all__ = [
    "__version__",
    # core
    "Mesh",
    "Vec3",
    "TextToSolidError",
    "ParseError",
    "MeshError",
    "ExportError",
    # primitives
    "box",
    "sphere",
    "cylinder",
    "cone",
    "torus",
    "wedge",
    "tube",
    "pyramid",
    # transforms
    "translate",
    "rotate",
    "scale",
    "mirror",
    # csg
    "union",
    "subtract",
    "intersect",
    "union_all",
    "subtract_all",
    # profiles
    "extrude",
    "revolve",
    "triangulate_polygon",
    # dsl
    "evaluate",
    "parse",
    "build",
    # agent protocol
    "build_from_spec",
    "model_info",
    "describe",
    # export
    "save",
    "save_stl",
    "save_obj",
    "save_svg",
    "mesh_to_stl_binary",
    "mesh_to_stl_ascii",
    "mesh_to_obj",
    "mesh_to_svg",
]

from .errors import ExportError, MeshError, ParseError, TextToSolidError
from .mesh import Mesh
from .vec import Vec3
from .primitives import box, cone, cylinder, pyramid, sphere, torus, tube, wedge
from .transforms import mirror, rotate, scale, translate
from . import csg
from .csg import intersect, subtract, union, union_all, subtract_all
from .profiles import extrude, revolve, triangulate_polygon
from .dsl import evaluate, parse
from .agent import build_from_spec, describe, model_info
from .export import (
    mesh_to_obj,
    mesh_to_stl_ascii,
    mesh_to_stl_binary,
    mesh_to_svg,
    save,
    save_obj,
    save_stl,
    save_svg,
)


def build(source: str, name: str = "model", units: str = "mm") -> Mesh:
    """Alias of :func:`texttosolid.dsl.evaluate` for quick scripting."""
    return evaluate(source, name=name, units=units)
