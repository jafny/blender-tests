"""Blue morpho butterflies (flapping) - small, bright accents of colour."""
import math
import random
import bpy
from mathutils import Vector
import helpers as H
import materials as M

R = random.Random(5)
FORE = [(0.0, 0.02), (0.03, 0.08), (0.2, 0.3), (0.38, 0.45), (0.55, 0.47), (0.64, 0.4), (0.6, 0.22), (0.45, 0.08), (0.25, 0.0)]
HIND = [(0.0, -0.01), (0.25, 0.0), (0.42, -0.08), (0.46, -0.22), (0.38, -0.36), (0.22, -0.4), (0.08, -0.3), (0.0, -0.12)]


def wing_mesh(name, sgn, span):
    mb = H.MB()
    for outline in (FORE, HIND):
        c = mb.vert((0, 0, 0), luv=(0, 0, 0))
        ids = [mb.vert((sgn * x * span, y * span, 0.0), luv=(x / 0.62, y / 0.62, 0)) for x, y in outline]
        for a, b in zip(ids, ids[1:] + ids[:1]):
            mb.face((c, a, b))
    return mb.build(name, [M.wing()], "Fauna", smooth=False, recalc=False)


def butterfly(i, loc, heading, span=0.075, perched=False, frames=360):
    root = H.empty(f"Morpho_{i}", loc, "Fauna")
    root.rotation_euler = (0, 0, heading)
    body = H.MB()
    H.tube(body, [Vector((0, y, 0)) for y in (-0.03, -0.01, 0.01, 0.025)], [0.004, 0.006, 0.005, 0.004], 6, cap0=True)
    b = body.build(f"Morpho_{i}_body", [M.flat("MorphoBody", M.col("#1A140E"), 0.6)], "Fauna")
    b.parent = root
    wings = []
    for sgn in (1, -1):
        w = wing_mesh(f"Morpho_{i}_wing{'R' if sgn > 0 else 'L'}", sgn, span)
        w.parent = root
        wings.append((w, sgn))
    period = R.uniform(7, 10) if not perched else R.uniform(30, 50)
    amp = math.radians(70 if not perched else 25)
    rest = math.radians(15 if not perched else 55)
    for f in range(1, frames + 1, 2):
        ph = math.sin(H.TAU * f / period + i)
        for w, sgn in wings:
            w.rotation_euler = (0, -sgn * (rest + amp * ph), 0)
            w.keyframe_insert("rotation_euler", index=1, frame=f)
    if not perched:
        # meandering flight: noise on location around the start point
        root.keyframe_insert("location", frame=1)
        for fc in root.animation_data.action.fcurves:
            if fc.data_path == "location":
                m = fc.modifiers.new('NOISE')
                m.scale = R.uniform(40, 70)
                m.strength = 1.4 if fc.array_index < 2 else 0.6
                m.phase = R.uniform(0, 100)
    return root


def build(spots):
    out = []
    specs = [(spots["brom_top"], 0.4, True)]
    for k, (p, z) in enumerate([(spots["floor_aim"], 0.6), (spots["log"], 1.0), (spots["stair_foot"], 1.2),
                                (spots["falls_view"], 1.5), (spots["kapok_front"], 1.0), (spots["river_mid"], 1.6)]):
        specs.append((Vector((p.x, p.y, p.z + z)), R.uniform(0, H.TAU), False))
    for i, (loc, hd, perched) in enumerate(specs):
        out.append(butterfly(i, loc, hd, perched=perched))
    return out
