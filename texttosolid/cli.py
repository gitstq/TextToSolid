"""TextToSolid command line interface.

Subcommands::

    t2s build     model.t2s -o part.stl      build and export
    t2s info      model.t2s                  print measurements
    t2s check     model.t2s                  validate printability
    t2s preview   model.t2s -o preview.svg   render an SVG preview
    t2s validate  model.t2s                  syntax check only
    t2s examples                            list built-in examples
    t2s example   gear -o gear.stl          build a built-in example
    t2s spec      model.json -o part.stl    build from an agent JSON spec
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional

from . import __version__
from .agent import build_from_spec, describe, model_info
from .dsl import evaluate
from .errors import ParseError, TextToSolidError
from .examples_data import EXAMPLES
from .export import save
from .mesh import Mesh

__all__ = ["main"]


# ---------------------------------------------------------------------- #
# helpers                                                                #
# ---------------------------------------------------------------------- #
def _load_mesh(path: str, as_spec: bool = False) -> Mesh:
    """Load a mesh from a .t2s DSL file or a .json agent spec."""
    if not os.path.exists(path):
        raise TextToSolidError("file not found: {0}".format(path))
    with open(path, "r", encoding="utf-8") as handle:
        source = handle.read()
    is_json = as_spec or path.lower().endswith(".json")
    if is_json:
        try:
            spec = json.loads(source)
        except json.JSONDecodeError as exc:
            raise ParseError("invalid JSON in {0}: {1}".format(path, exc))
        return build_from_spec(spec)
    return evaluate(source, name=os.path.splitext(os.path.basename(path))[0])


def _print_info(mesh: Mesh, as_json: bool = False) -> None:
    if as_json:
        print(json.dumps(model_info(mesh), indent=2))
        return
    info = model_info(mesh)
    size = info["size"] or [0.0, 0.0, 0.0]
    print("model            : {0}".format(info["name"]))
    print("units            : {0}".format(info["units"]))
    print("triangles        : {0}".format(info["triangles"]))
    print("vertices         : {0}".format(info["vertices"]))
    print(
        "bounding box     : {0:.3f} x {1:.3f} x {2:.3f} {3}".format(
            size[0], size[1], size[2], info["units"]
        )
    )
    print("volume           : {0:.4f} {1}^3".format(info["volume_abs"], info["units"]))
    print("surface area     : {0:.4f} {1}^2".format(info["surface_area"], info["units"]))
    print("watertight       : {0}".format("yes" if info["watertight"] else "no"))
    print("non-manifold     : {0} edge(s)".format(info["non_manifold_edges"]))
    print("degenerate faces : {0}".format(info["degenerate_faces"]))
    print("printable        : {0}".format("yes" if info["printable"] else "no"))


# ---------------------------------------------------------------------- #
# subcommands                                                            #
# ---------------------------------------------------------------------- #
def _cmd_build(args: argparse.Namespace) -> int:
    mesh = _load_mesh(args.input, as_spec=args.spec)
    if mesh.is_empty():
        print("warning: model is empty", file=sys.stderr)
        return 1
    output = args.output
    if not output:
        base = os.path.splitext(os.path.basename(args.input))[0]
        output = base + ".stl"
    save(mesh, output, ascii=args.ascii,
         width=args.width, height=args.height, yaw=args.yaw, pitch=args.pitch)
    print("built {0} ({1} triangles) -> {2}".format(
        mesh.name, mesh.triangle_count, output))
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    mesh = _load_mesh(args.input, as_spec=args.spec)
    _print_info(mesh, as_json=args.json)
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    mesh = _load_mesh(args.input, as_spec=args.spec)
    _print_info(mesh, as_json=False)
    info = model_info(mesh)
    if info["printable"]:
        print("check            : PASS")
        return 0
    print("check            : FAIL")
    return 1


def _cmd_preview(args: argparse.Namespace) -> int:
    mesh = _load_mesh(args.input, as_spec=args.spec)
    output = args.output or (
        os.path.splitext(os.path.basename(args.input))[0] + ".svg"
    )
    save(mesh, output, width=args.width, height=args.height,
         yaw=args.yaw, pitch=args.pitch)
    print("preview -> {0}".format(output))
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    mesh = _load_mesh(args.input, as_spec=args.spec)
    print("{0}: OK ({1} triangles)".format(args.input, mesh.triangle_count))
    return 0


def _cmd_examples(args: argparse.Namespace) -> int:
    print("built-in examples:")
    for name in sorted(EXAMPLES):
        print("  {0:<14} build with: t2s example {0} -o {0}.stl".format(name))
    print("\nrun 't2s example <name> -o <file>' to build one")
    return 0


def _cmd_example(args: argparse.Namespace) -> int:
    if args.name not in EXAMPLES:
        raise TextToSolidError(
            "unknown example {0!r}; available: {1}".format(
                args.name, ", ".join(sorted(EXAMPLES))
            )
        )
    mesh = evaluate(EXAMPLES[args.name], name=args.name)
    if mesh.is_empty():
        print("warning: example produced an empty model", file=sys.stderr)
        return 1
    output = args.output or (args.name + ".stl")
    save(mesh, output, ascii=args.ascii,
         width=args.width, height=args.height, yaw=args.yaw, pitch=args.pitch)
    print("built {0} ({1} triangles) -> {2}".format(
        mesh.name, mesh.triangle_count, output))
    return 0


def _cmd_spec(args: argparse.Namespace) -> int:
    mesh = _load_mesh(args.input, as_spec=True)
    output = args.output or (
        os.path.splitext(os.path.basename(args.input))[0] + ".stl"
    )
    save(mesh, output, ascii=args.ascii,
         width=args.width, height=args.height, yaw=args.yaw, pitch=args.pitch)
    print("built {0} ({1} triangles) -> {2}".format(
        mesh.name, mesh.triangle_count, output))
    return 0


# ---------------------------------------------------------------------- #
# parser                                                                 #
# ---------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="t2s",
        description="TextToSolid - text-to-solid parametric modeling engine "
                    "(zero dependencies, pure Python)",
    )
    parser.add_argument("--version", action="version",
                        version="TextToSolid {0}".format(__version__))

    def add_view_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("--width", type=int, default=640, help="SVG width in px")
        p.add_argument("--height", type=int, default=480, help="SVG height in px")
        p.add_argument("--yaw", type=float, default=35.0, help="preview yaw in degrees")
        p.add_argument("--pitch", type=float, default=25.0, help="preview pitch in degrees")

    sub = parser.add_subparsers(dest="command")

    p = sub.add_parser("build", help="build a model and export it")
    p.add_argument("input", help=".t2s source or .json spec")
    p.add_argument("-o", "--output", help="output file (.stl/.obj/.svg)")
    p.add_argument("--ascii", action="store_true", help="write ASCII STL")
    p.add_argument("--spec", action="store_true", help="force JSON spec parsing")
    add_view_args(p)
    p.set_defaults(func=_cmd_build)

    p = sub.add_parser("info", help="print model measurements")
    p.add_argument("input")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--spec", action="store_true", help="force JSON spec parsing")
    p.set_defaults(func=_cmd_info)

    p = sub.add_parser("check", help="validate a model for 3D printing")
    p.add_argument("input")
    p.add_argument("--spec", action="store_true", help="force JSON spec parsing")
    p.set_defaults(func=_cmd_check)

    p = sub.add_parser("preview", help="render an SVG preview")
    p.add_argument("input")
    p.add_argument("-o", "--output")
    p.add_argument("--spec", action="store_true", help="force JSON spec parsing")
    add_view_args(p)
    p.set_defaults(func=_cmd_preview)

    p = sub.add_parser("validate", help="syntax-check a source file")
    p.add_argument("input")
    p.add_argument("--spec", action="store_true", help="force JSON spec parsing")
    p.set_defaults(func=_cmd_validate)

    p = sub.add_parser("examples", help="list built-in examples")
    p.set_defaults(func=_cmd_examples)

    p = sub.add_parser("example", help="build a built-in example")
    p.add_argument("name", help="example name (see 't2s examples')")
    p.add_argument("-o", "--output")
    p.add_argument("--ascii", action="store_true", help="write ASCII STL")
    add_view_args(p)
    p.set_defaults(func=_cmd_example)

    p = sub.add_parser("spec", help="build from an agent JSON spec")
    p.add_argument("input", help=".json spec file")
    p.add_argument("-o", "--output")
    p.add_argument("--ascii", action="store_true", help="write ASCII STL")
    add_view_args(p)
    p.set_defaults(func=_cmd_spec)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    try:
        return int(args.func(args))
    except TextToSolidError as exc:
        print("error: {0}".format(exc), file=sys.stderr)
        return 2
    except BrokenPipeError:  # pragma: no cover
        return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
