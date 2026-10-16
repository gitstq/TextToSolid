"""Built-in TextToSolid example programs.

The same sources ship as ``examples/*.t2s`` in the repository and can be built
from the CLI with ``t2s example <name> -o part.stl``.
"""
from __future__ import annotations

__all__ = ["EXAMPLES"]

EXAMPLES = {
    "bracket": """# L-bracket with four mounting holes
# A base plate plus a vertical rib, drilled for M3 screws.
let t = 4          # plate thickness
let W = 40         # overall width
let D = 20         # overall depth
let H = 30         # rib height
let hole = 1.7     # M3 clearance radius

difference {
    union {
        box(W, D, t)
        translate(0, 0, t / 2 + H / 2) { box(W, D, H) }
    }
    repeat(2, translate=(28, 0, 0)) {
        repeat(2, translate=(0, 14, 0)) {
            translate(0, 0, 0) { cylinder(r=hole, h=t * 3) }
        }
    }
}
""",
    "gear": """# Spur gear: 12 teeth, bore and lightening holes
let teeth = 12
let R = 20         # pitch radius
let th = 8         # gear thickness

difference {
    union {
        cylinder(r=R, h=th, segments=72)
        repeat(teeth, rotate=(0, 0, 360 / teeth)) {
            translate(0, R + 1.5, 0) { box(4, 6, th) }
        }
    }
    cylinder(r=4, h=th + 4)                        # central bore
    repeat(6, rotate=(0, 0, 60)) {
        translate(0, 12, 0) { cylinder(r=2.2, h=th + 4) }
    }
}
""",
    "vase": """# Hollow vase revolved from a profile
difference {
    revolve(360, segments=64) {
        polygon([
            (0, 0), (20, 0), (21, 3), (21, 30),
            (15, 45), (15, 55), (19, 58), (17, 60), (0, 60)
        ])
    }
    translate(0, 3, 0) {
        revolve(360, segments=64) {
            polygon([
                (0, 0), (17, 0), (18, 2), (18, 27),
                (12, 42), (12, 52), (16, 55), (14, 57), (0, 57)
            ])
        }
    }
}
""",
    "phone-stand": """# Phone stand: base plate, tilted back support and retaining lip
let W = 70
let D = 60
let T = 4

difference {
    union {
        box(W, D, T)
        translate(0, -26, 30) { rotate(-72, 0, 0) { box(W, T, 58) } }
        translate(0, -8, 54) { rotate(-72, 0, 0) { box(W, 8, T) } }
    }
    translate(0, 26, 0) { cylinder(r=7, h=T + 2) }   # cable notch
    translate(0, 26, 0) { box(10, 20, T + 2) }
}
""",
}
