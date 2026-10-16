"""Minimal 3D vector used across the TextToSolid engine.

Pure standard library — no third-party dependencies.
"""
from __future__ import annotations

import math

__all__ = ["Vec3"]


class Vec3:
    """A small 3D vector with the operations the geometry engine needs."""

    __slots__ = ("x", "y", "z")

    def __init__(self, x: float = 0.0, y: float = 0.0, z: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    # ------------------------------------------------------------------ #
    # construction helpers                                                #
    # ------------------------------------------------------------------ #
    @classmethod
    def zero(cls) -> "Vec3":
        return cls(0.0, 0.0, 0.0)

    def copy(self) -> "Vec3":
        return Vec3(self.x, self.y, self.z)

    def as_tuple(self):
        return (self.x, self.y, self.z)

    # ------------------------------------------------------------------ #
    # arithmetic                                                          #
    # ------------------------------------------------------------------ #
    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, scalar: float) -> "Vec3":
        return Vec3(self.x * scalar, self.y * scalar, self.z * scalar)

    __rmul__ = __mul__

    def __truediv__(self, scalar: float) -> "Vec3":
        return Vec3(self.x / scalar, self.y / scalar, self.z / scalar)

    def __neg__(self) -> "Vec3":
        return Vec3(-self.x, -self.y, -self.z)

    def __pos__(self) -> "Vec3":
        return self.copy()

    # ------------------------------------------------------------------ #
    # products                                                            #
    # ------------------------------------------------------------------ #
    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z

    def cross(self, other: "Vec3") -> "Vec3":
        return Vec3(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    # ------------------------------------------------------------------ #
    # metrics                                                             #
    # ------------------------------------------------------------------ #
    def length_sq(self) -> float:
        return self.x * self.x + self.y * self.y + self.z * self.z

    def length(self) -> float:
        return math.sqrt(self.length_sq())

    def distance_to(self, other: "Vec3") -> float:
        return (self - other).length()

    def normalized(self) -> "Vec3":
        n = self.length()
        if n == 0.0:
            return Vec3(0.0, 0.0, 0.0)
        return self / n

    def lerp(self, other: "Vec3", t: float) -> "Vec3":
        return Vec3(
            self.x + (other.x - self.x) * t,
            self.y + (other.y - self.y) * t,
            self.z + (other.z - self.z) * t,
        )

    # ------------------------------------------------------------------ #
    # protocols                                                           #
    # ------------------------------------------------------------------ #
    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z

    def __getitem__(self, index: int) -> float:
        return (self.x, self.y, self.z)[index]

    def __len__(self) -> int:
        return 3

    def __eq__(self, other) -> bool:
        if not isinstance(other, Vec3):
            return NotImplemented
        return self.x == other.x and self.y == other.y and self.z == other.z

    def __hash__(self) -> int:
        return hash((self.x, self.y, self.z))

    def __repr__(self) -> str:
        return "Vec3({0:.6g}, {1:.6g}, {2:.6g})".format(self.x, self.y, self.z)
