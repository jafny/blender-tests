"""Room shell (bulging walls, domed ceiling), floor, windows, door, trim and the world outside."""
import math
import bpy
from mathutils import Vector, Matrix
from helpers import (TAU, sring, cring, loft, slab, tube, blob, sphere, torus, cylinder, MB, link, lerp,
                     smoothstep, rng, add_subsurf, curl_top, transform_pts)
import materials as M

# --- Room: rounded-rectangle plan, walls bulge outward at mid height, ceiling is a dome ---
A = 4.8          # half width  (x)
B = 3.6          # half depth  (y)  +y = back wall (cabinets), -y = front
E = 7.0          # superellipse exponent (rounded rectangle)
H = 3.2          # wall height where the dome starts
DOME = 1.1       # extra height of the ceiling dome
BULGE = 0.035
WOB = 0.018
NSEG = 192


def shell_ring(z, n=NSEG, extra=0.0):
    t = z / H
    s = 1.0 + BULGE * math.sin(math.pi * min(max(t, 0.0), 1.0)) + extra
    return sring(0, 0, z, A * s, B * s, E, n, wob=WOB, wob_freq=5, phase=z * 0.9 + 0.4)


def wall_surface(u, z, side):
    """Wall surface coordinate. side: 'back' -> y at x=u, 'front' -> y at x=u, 'right' -> x at y=u, 'left' -> x at y=u."""
    ring = shell_ring(z, n=512)
    if side in ('back', 'front'):
        pts = [(p.x, p.y) for p in ring if (p.y > 0) == (side == 'back')]
        pts.sort()
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 <= u <= x1:
                return lerp(y0, y1, (u - x0) / (x1 - x0) if x1 > x0 else 0)
        return pts[0][1] if u < pts[0][0] else pts[-1][1]
    else:
        pts = [(p.y, p.x) for p in ring if (p.x > 0) == (side == 'right')]
        pts.sort()
        for (y0, x0), (y1, x1) in zip(pts, pts[1:]):
            if y0 <= u <= y1:
                return lerp(x0, x1, (u - y0) / (y1 - y0) if y1 > y0 else 0)
        return pts[0][1] if u < pts[0][0] else pts[-1][1]


def to_wall(side, u, z, off=0.0):
    """Point on the wall surface (moved `off` metres into the room)."""
    w = wall_surface(u, z, side)
    if side == 'back':
        return Vector((u, w - off, z))
    if side == 'front':
        return Vector((u, w + off, z))
    if side == 'right':
        return Vector((w - off, u, z))
    return Vector((w + off, u, z))


def wall_normal(side):
    """Inward-pointing normal (into the room) and the in-wall 'u' axis."""
    return {'back': (Vector((0, -1, 0)), Vector((1, 0, 0))), 'front': (Vector((0, 1, 0)), Vector((-1, 0, 0))),
            'right': (Vector((-1, 0, 0)), Vector((0, 1, 0))), 'left': (Vector((1, 0, 0)), Vector((0, -1, 0)))}[side]


def panel(name, side, outline_uz, depth, mat, off=0.02, subsurf=1, collection="Room"):
    """A plate hugging the wall: outline given in (u, z) wall coordinates, extruded `depth` into the room."""
    back = [to_wall(side, u, z, -off) for u, z in outline_uz]
    front = [to_wall(side, u, z, depth) for u, z in outline_uz]
    nrm, _ = wall_normal(side)
    r1 = [p + nrm * (depth + off) * 0.15 for p in back]
    r2 = [p - nrm * (depth + off) * 0.15 for p in front]
    rings = [back, r1, r2, front] if subsurf else [back, front]
    # make the ring order consistent with an "outward" normal of the loft (bottom=back)
    return loft(name, rings, mat, collection, subsurf=subsurf)


# name, side, u0, z0, ru, rz, frame colour, mullion colour, wobble, phase, tilt, mullions
WINDOWS = [
    ("WinSink", 'back', 0.15, 2.0, 0.66, 0.60, "red", "yellow", 0.06, 0.3, 0.0, True),
    ("WinBack2", 'back', 2.25, 2.62, 0.36, 0.40, "teal", "orange", 0.07, 1.7, 0.0, False),
    ("WinRight", 'right', 0.0, 2.05, 0.85, 0.62, "orange", "sky", 0.05, 2.2, -0.18, True),
    ("WinFront", 'front', -1.3, 2.15, 0.75, 0.75, "magenta", "lime", 0.06, 0.9, 0.0, True),
    ("WinFront2", 'front', 2.2, 2.5, 0.38, 0.38, "lime", "purple", 0.08, 2.5, 0.0, False),
]


def window_holes():
    """Alpha-mask description of every window opening, in the wall's object space."""
    holes = []
    for name, side, u0, z0, ru, rz, fc, mc, wob, phase, tilt, mull in WINDOWS:
        axis_u = 'x' if side in ('back', 'front') else 'y'
        axis_side = {'back': ('y', 1), 'front': ('y', -1), 'right': ('x', 1), 'left': ('x', -1)}[side]
        holes.append(dict(axis_u=axis_u, axis_side=axis_side, u0=u0, z0=z0, ru=ru, rz=rz, tilt=tilt, wob=wob, freq=3,
                          phase=phase))
    return holes


def room():
    """Walls + dome as one object; floor separate. Returns (walls, floor)."""
    rings = []
    zs = [0.0, 0.05, 0.15, 0.3, 0.5, 0.75, 1.0, 1.3, 1.6, 1.9, 2.2, 2.5, 2.8, 3.0, 3.1, 3.2]
    for z in zs:
        rings.append(shell_ring(z))
    # dome: shrink rings while rising
    for k in range(1, 13):
        phi = (math.pi / 2) * (k / 13.0) * 0.93
        s = math.cos(phi)
        z = H + DOME * math.sin(phi)
        rings.append(sring(0, 0, z, A * s, B * s, E, NSEG, wob=WOB * 0.5, wob_freq=5, phase=z * 0.9 + 0.4))
    wall_mat = M.wall("WallPaint", lower="teal", upper="cream", rail="magenta", stripe="#FFE3EE", stripe_w=0.45,
                      holes=window_holes())
    mb = MB()
    mb.add_loft(rings, cap_bottom=False, cap_top=True)
    walls = mb.build("Walls", wall_mat, "Room", smooth=True)
    # ceiling colour: separate material slot for the dome faces
    ceil_mat = M.candy("Ceiling", "lavender", rough=0.6, coat=0.05)
    walls.data.materials.append(ceil_mat)
    n = NSEG
    nwall = (len(zs) - 1) * n
    for i, p in enumerate(walls.data.polygons):
        if i >= nwall:
            p.material_index = 1
    # floor
    floor_mat = M.checker("Floor", "#3D2A6E", "#FFF1C9", size=0.62, warp=0.35, wfreq=0.45, rot=0.12)
    fr = shell_ring(0.0, extra=0.02)
    mb = MB()
    mb.add_poly([Vector((p.x, p.y, 0.0)) for p in fr])
    floor = mb.build("Floor", floor_mat, "Room", smooth=False)
    return walls, floor


def trim(walls):
    """Fat piping along the floor and the ceiling line, plus a wavy 'rail' tube around the room."""
    base_mat = M.candy("TrimBase", "purple")
    pts = [Vector((p.x * 0.995, p.y * 0.995, 0.07)) for p in shell_ring(0.07, n=96)]
    tube("Baseboard", pts, radius=0.075, mat=base_mat, cyclic=True, collection="Room", res=6)
    crown_mat = M.candy("TrimCrown", "sun")
    pts = [Vector((p.x, p.y, H - 0.02)) for p in shell_ring(H - 0.02, n=96)]
    tube("Crown", pts, radius=0.09, mat=crown_mat, cyclic=True, collection="Room", res=6)


# ------------------------------------------------------------------ windows
def window_path(side, u0, z0, ru, rz, n=40, wob=0.05, freq=3, phase=0.0, tilt=0.0):
    """Wobbly ellipse in wall (u, z) coordinates -> list of (u, z)."""
    out = []
    for k in range(n):
        t = TAU * k / n
        w = 1 + wob * math.sin(freq * t + phase)
        a, b = ru * w * math.cos(t), rz * w * math.sin(t)
        u = a * math.cos(tilt) - b * math.sin(tilt)
        z = a * math.sin(tilt) + b * math.cos(tilt)
        out.append((u0 + u, z0 + z))
    return out


def window(name, walls, side, u0, z0, ru, rz, frame_col="red", mullion_col="yellow", wob=0.05, phase=0.0, tilt=0.0,
           mullions=True, thick=0.075):
    path = window_path(side, u0, z0, ru, rz, wob=wob, phase=phase, tilt=tilt)
    # the opening itself is an alpha cut-out in the wall material (see window_holes); here: frame + mullions
    # frame: fat tube that hugs the wall surface
    fmat = M.candy("Frame_" + frame_col, frame_col)
    fpts = [to_wall(side, u, z, 0.0) for u, z in path]
    tube(name + "_frame", fpts, radius=thick, mat=fmat, cyclic=True, collection="Room", res=4)
    # an outer, thinner second ring in a contrasting colour (like a drawn double outline)
    path2 = window_path(side, u0, z0, ru + thick * 1.9, rz + thick * 1.9, wob=wob, phase=phase, tilt=tilt)
    fpts2 = [to_wall(side, u, z, 0.0) for u, z in path2]
    tube(name + "_frame2", fpts2, radius=thick * 0.55, mat=M.candy("Frame_" + mullion_col, mullion_col), cyclic=True,
         collection="Room", res=4)
    if mullions:
        mmat = M.candy("Frame_" + mullion_col, mullion_col)
        # a wavy vertical + horizontal bar, sinking into the frame
        for kind in ("v", "h"):
            pts = []
            for i in range(9):
                t = -1.0 + 2.0 * i / 8
                if kind == "v":
                    u, z = u0 + 0.10 * ru * math.sin(2.5 * t + phase), z0 + rz * 1.05 * t
                else:
                    u, z = u0 + ru * 1.05 * t, z0 + 0.10 * rz * math.sin(2.5 * t + phase + 1)
                pts.append(to_wall(side, u, z, 0.01))
            tube(f"{name}_mullion_{kind}", pts, radius=thick * 0.42, mat=mmat, collection="Room", res=6)
    return path


def windows(walls):
    for name, side, u0, z0, ru, rz, fc, mc, wob, phase, tilt, mull in WINDOWS:
        window(name, walls, side, u0, z0, ru, rz, fc, mc, wob=wob, phase=phase, tilt=tilt, mullions=mull)


# ------------------------------------------------------------------ door (closed, on the left wall)
def door():
    side = 'left'
    u0, w, h = -0.9, 1.05, 2.25
    # arched, slightly lopsided outline in (u, z)
    pts = []
    n = 48
    for k in range(n):
        t = k / n
        # parametrize: bottom edge -> right side -> arch -> left side
        if t < 0.2:
            u, z = lerp(-w / 2, w / 2, t / 0.2), 0.0
        elif t < 0.4:
            u, z = w / 2, lerp(0.0, h - w / 2, (t - 0.2) / 0.2)
        elif t < 0.6:
            th = math.pi * (t - 0.4) / 0.2
            u, z = (w / 2) * math.cos(th) * (1 + 0.08 * math.sin(3 * th)), h - w / 2 + (w / 2) * 1.15 * math.sin(th)
        elif t < 0.8:
            u, z = -w / 2, lerp(h - w / 2, 0.0, (t - 0.6) / 0.2)
        else:
            u, z = -w / 2, 0.0
            continue
        pts.append((u0 + u + 0.03 * math.sin(4 * z), z))
    # dedupe consecutive duplicates
    clean = []
    for p in pts:
        if not clean or (abs(p[0] - clean[-1][0]) > 1e-4 or abs(p[1] - clean[-1][1]) > 1e-4):
            clean.append(p)
    # reverse if needed so the loft faces are fine (recalc normals handles it)
    dmat = M.candy("Door", "lime")
    panel("Door", side, clean, 0.07, dmat, off=0.0, subsurf=1)
    # frame tube around the door (skip the bottom edge)
    frame_pts = [to_wall(side, u, z, 0.0) for u, z in clean if z > 0.02]
    tube("DoorFrame", frame_pts, radius=0.07, mat=M.candy("Frame_red", "red"), collection="Room", res=4)
    # porthole in the door: ring + inset disc
    cz = 1.55
    ring = [to_wall(side, u0 + 0.3 * math.cos(t) * (1 + 0.06 * math.sin(3 * t)), cz + 0.28 * math.sin(t), 0.075)
            for t in [TAU * k / 32 for k in range(32)]]
    tube("DoorPorthole", ring, radius=0.045, mat=M.candy("Frame_yellow", "yellow"), cyclic=True, collection="Room", res=4)
    disc = [to_wall(side, u0 + 0.3 * math.cos(t), cz + 0.28 * math.sin(t), 0.06) for t in [TAU * k / 32 for k in range(32)]]
    disc2 = [p + Vector((0.02, 0, 0)) for p in disc]
    loft("DoorGlass", [disc, disc2], M.candy("DoorGlassCol", "#BFEFFF", rough=0.1, coat=0.8), "Room", subsurf=0)
    # big ball knob on a stalk
    kx = to_wall(side, u0 + 0.38, 1.05, 0.07)
    sphere("DoorKnob", kx + Vector((0.10, 0, 0)), 0.075, M.candy("Knob_red", "red"), scale=(1, 1.15, 1.15), collection="Room")
    cylinder("DoorKnobStem", (kx.x, kx.y, kx.z), 0.028, 0.10, M.metal("Chrome"), n=16, collection="Room",
             mat4=Matrix.Translation(kx) @ Matrix.Rotation(math.pi / 2, 4, 'Y') @ Matrix.Translation(-kx))
    # a couple of drawn "panels" on the door: raised pillowy blobs
    for (pz, ph) in ((0.55, 0.55),):
        pan = [(u0 + 0.36 * math.cos(t) * (1 + 0.05 * math.sin(2 * t)), pz + ph * 0.5 * (1 + math.sin(t)))
               for t in [TAU * k / 32 for k in range(32)]]
        panel("DoorPanel", side, pan, 0.10, M.candy("DoorPanel", "green"), off=-0.05, subsurf=1)


# ------------------------------------------------------------------ outside
def truffula(name, base, height, lean=(0.6, 0.2), pom="pink", r=0.55, collection="Outside"):
    bx, by = base
    pts, radii = [], []
    n = 14
    for i in range(n + 1):
        t = i / n
        pts.append((bx + lean[0] * t * t * height * 0.5 + 0.15 * math.sin(3 * t),
                    by + lean[1] * t * t * height * 0.5, t * height))
        radii.append(1.0 - 0.45 * t)
    trunk_mat = M.stripes("Truffula_trunk", ["#F5E6A8", "#3A2A20"], width=0.22, axis='z', wobble=0.05)
    tube(name + "_trunk", pts, radius=0.11, mat=trunk_mat, radii=radii, collection=collection, res=8)
    top = Vector(pts[-1]) + Vector((0, 0, r * 0.7))
    s = sphere(name + "_pom", top, r, M.fuzz("Pom_" + pom, pom), seg=32, rings=16, scale=(1.15, 1.0, 0.85), subsurf=1,
               collection=collection)
    tex = bpy.data.textures.get("PomNoise") or bpy.data.textures.new("PomNoise", 'CLOUDS')
    tex.noise_scale = 0.35
    tex.noise_depth = 2
    d = s.modifiers.new("Fluff", 'DISPLACE')
    d.texture = tex
    d.strength = 0.22
    d.mid_level = 0.5
    return s


def outside():
    ground = cylinder("Ground", (0, 0, -0.5), 80.0, 0.48, M.matte("Grass", "#8CD84A", rough=0.9), n=48, collection="Outside")
    hills = [((9, 12, -1.5), 7.5, (1.3, 1.0, 0.45), "#79CC3E"), ((-12, 9, -1.5), 9.0, (1.4, 1.0, 0.4), "#5FBF52"),
             ((16, -3, -1.5), 8.0, (1.2, 1.1, 0.42), "#A3E05C"), ((-14, -10, -1.5), 10.0, (1.5, 1.0, 0.35), "#6FC760"),
             ((3, -16, -1.5), 9.0, (1.4, 1.0, 0.3), "#8CD84A"), ((22, 12, -2), 12.0, (1.5, 1.0, 0.5), "#57B86A")]
    for i, (c, r, s, colr) in enumerate(hills):
        sphere(f"Hill{i}", c, r, M.matte(f"Hill_{colr}", colr, rough=0.9), seg=40, rings=20, scale=s, subsurf=1,
               collection="Outside")
    trees = [((1.2, 7.0), 4.2, (0.5, 0.1), "pink", 0.7), ((3.2, 6.2), 3.0, (-0.4, 0.2), "orange", 0.55),
             ((7.5, 0.4), 4.6, (0.2, 0.6), "yellow", 0.75), ((6.8, 2.6), 3.3, (0.3, -0.5), "magenta", 0.55),
             ((-2.4, -7.6), 4.0, (-0.5, 0.2), "coral", 0.7), ((2.5, -7.2), 3.4, (0.3, 0.1), "sky", 0.55),
             ((-8.5, 3.5), 5.0, (0.2, 0.3), "purple", 0.8), ((-7.2, -3.0), 3.6, (0.4, -0.2), "lime", 0.6),
             ((10.5, -5.5), 5.5, (-0.3, 0.2), "pink", 0.9), ((0.5, 10.5), 5.2, (0.5, 0.3), "yellow", 0.85)]
    for i, (b, h, ln, pm, r) in enumerate(trees):
        truffula(f"Truffula{i}", b, h, ln, pm, r)
    cm = M.matte("Cloud", "white", rough=0.9)
    clouds = [(4, 14, 8.5), (-9, 12, 10), (14, 4, 9), (-6, -14, 9.5), (18, -8, 11), (-16, 0, 10.5), (8, -16, 8.8)]
    for i, (cx, cy, cz) in enumerate(clouds):
        for j in range(5):
            dx, dy, dz = rng.uniform(-1.6, 1.6), rng.uniform(-0.6, 0.6), rng.uniform(-0.3, 0.5)
            rr = rng.uniform(0.9, 1.6)
            sphere(f"Cloud{i}_{j}", (cx + dx, cy + dy, cz + dz), rr, cm, seg=16, rings=8, scale=(1.2, 1.0, 0.8),
                   subsurf=1, collection="Outside")


def build():
    walls, floor = room()
    trim(walls)
    windows(walls)
    door()
    outside()
    return walls, floor
