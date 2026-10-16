"""TextToSolid — zero-dependency parametric solid modeling engine in pure Python.

Public error hierarchy. Every error raised by the library is a subclass of
:class:`TextToSolidError`, so callers can catch a single type.
"""
from __future__ import annotations

__all__ = ["TextToSolidError", "ParseError", "MeshError", "ExportError"]


class TextToSolidError(Exception):
    """Base class for every error raised by TextToSolid."""


class ParseError(TextToSolidError):
    """Raised when a TextToSolid DSL document or JSON spec cannot be parsed."""


class MeshError(TextToSolidError):
    """Raised for invalid geometry (degenerate profiles, empty results, ...)."""


class ExportError(TextToSolidError):
    """Raised when a mesh cannot be written to the requested format."""
