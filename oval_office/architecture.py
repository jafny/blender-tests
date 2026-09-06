"""Room shell: elliptical walls with openings, floor, ceiling/cornice, windows, doors, fireplace, exterior."""
import math
from math import radians as rad
import bpy
from mathutils import Vector, Matrix
from helpers import (A, B, H, WALL_T, MB, ell_pt, ell_normal, dtheta, frame_at, box, cyl, empty, parent,
                     add_bevel, coll, link, TAU)

# Opening layout (theta: 0=east, 90=north, -90=south)
WIN_W, WIN_Z0, WIN_Z1 = 1.55, 0.75, 4.40
DOOR_W, DOOR_H = 1.15, 2.75
FIRE_W, FIRE_H = 1.00, 1.00
WINDOWS = [rad(-90 - 37), rad(-90), rad(-90 + 37)]
DOORS = {"east": rad(0), "west": rad(180), "ne": rad(52), "nw": rad(128)}
FIREPLACE = rad(90)


def openings():
    ops = []
    for t in WINDOWS:
        ops.append(dict(kind="window", theta=t, dt=dtheta(t, WIN_W), z0=WIN_Z0, z1=WIN_Z1))
    for k, t in DOORS.items():
        ops.append(dict(kind="door", name=k, theta=t, dt=dtheta(t, DOOR_W), z0=0.0, z1=DOOR_H))
    ops.append(dict(kind="fire", theta=FIREPLACE, dt=dtheta(FIREPLACE, FIRE_W), z0=0.0, z1=FIRE_H))
    ops.sort(key=lambda o: o["theta"])
    return ops


def wall_segments(ops):
    """Angular ranges of solid wall between openings (from -pi to pi)."""
    segs = []
    start = -math.pi
    for o in ops:
        segs.append((start, o["theta"] - o["dt"]))
        start = o["theta"] + o["dt"]
    segs.append((start, math.pi))
    return segs


def band(mb, t1, t2, z1, z2, thick=WALL_T, step=rad(1.5)):
    n = max(2, int((t2 - t1) / step))
    for i in range(n):
        a = t1 + (t2 - t1) * i / n
        b = t1 + (t2 - t1) * (i + 1) / n
        i1, i2 = ell_pt(a, 0, z1), ell_pt(b, 0, z1)
        i3, i4 = ell_pt(a, 0, z2), ell_pt(b, 0, z2)
        o1, o2 = ell_pt(a, -thick, z1), ell_pt(b, -thick, z1)
        o3, o4 = ell_pt(a, -thick, z2), ell_pt(b, -thick, z2)
        mb.add_quad(i1, i3, i4, i2)      # inner
        mb.add_quad(o1, o2, o4, o3)      # outer
        mb.add_quad(i3, o3, o4, i4)      # top
        mb.add_quad(i1, i2, o2, o1)      # bottom
    for t in (t1, t2):
        mb.add_quad(ell_pt(t, 0, z1), ell_pt(t, 0, z2), ell_pt(t, -thick, z2), ell_pt(t, -thick, z1))


def sweep(mb, profile, t1, t2, step=rad(1.5), close=True):
    """Sweep a (inset, z) profile polyline along the ellipse; caps the ends with the profile polygon."""
    n = max(2, int((t2 - t1) / step))
    rings = []
    for i in range(n + 1):
        t = t1 + (t2 - t1) * i / n
        rings.append([ell_pt(t, d, z) for d, z in profile])
    for i in range(n):
        r1, r2 = rings[i], rings[i + 1]
        for j in range(len(profile) - (0 if close else 1)):
            j2 = (j + 1) % len(profile)
            mb.add_quad(r1[j], r2[j], r2[j2], r1[j2])
    if abs((t2 - t1) - TAU) > 1e-6:
        mb.add_poly(rings[0])
        mb.add_poly(list(reversed(rings[-1])))


def disc(mb, inset, z, step=rad(1.5), a=A, b=B):
    n = int(TAU / step)
    mb.add_poly([ell_pt(TAU * i / n, inset, z, a, b) for i in range(n)])


# ------------------------------------------------------------------ shell
def build_shell(M):
    ops = openings()
    segs = wall_segments(ops)
    walls = MB()
    for t1, t2 in segs:
        band(walls, t1, t2, 0.0, H)
    for o in ops:
        t1, t2 = o["theta"] - o["dt"], o["theta"] + o["dt"]
        band(walls, t1, t2, o["z1"], H)
        if o["z0"] > 0:
            band(walls, t1, t2, 0.0, o["z0"])
    walls.build("Walls", M["wall"], "Architecture")

    floor = MB()
    disc(floor, -WALL_T - 0.05, 0.0)
    fl = floor.build("Floor", M["parquet"], "Architecture")

    # cornice + cove + ceiling
    prof = [(0, 4.60), (0.04, 4.60), (0.04, 4.72), (0.10, 4.72), (0.10, 4.84), (0.12, 4.84), (0.12, 4.94),
            (0.24, 4.94), (0.24, 5.02), (0.34, 5.02), (0.34, 5.08), (0.02, 5.08), (0.02, 5.14)]
    for i in range(1, 9):
        t = math.pi / 2 * i / 8
        prof.append((0.02 + 0.58 * (1 - math.cos(t)), 5.14 + (H - 5.14) * math.sin(t)))
    prof.append((0.60 + 0.02, H))
    prof.append((0.60 + 0.02, H + 0.05))
    prof.append((-0.05, H + 0.05))
    prof.append((-0.05, 4.60))
    cm = MB()
    sweep(cm, prof, 0, TAU)
    cor = cm.build("Cornice", M["trim"], "Architecture", smooth=False)
    cl = MB()
    disc(cl, 0.60, H)
    cl.build("Ceiling", M["ceiling"], "Architecture")
    # dentils
    dm = MB()
    perim_steps = 240
    for i in range(perim_steps):
        t = TAU * i / perim_steps
        fr = frame_at(t, 0.12, 4.89)
        dm.add_box((0, 0.05, 0), (0.07, 0.10, 0.09), fr)
    dm.build("Dentils", M["trim"], "Architecture")
    # hidden cove light ring on top of the cornice lip
    lm = MB()
    sweep(lm, [(0.06, 5.085), (0.30, 5.085)], 0, TAU, close=False)
    ring = lm.build("CoveLightRing", M["cove_light"], "Lights")
    ring.visible_camera = False
    ring.visible_glossy = False

    # baseboard and chair rail between openings (doors reach the floor)
    door_ranges = [(o["theta"] - o["dt"], o["theta"] + o["dt"]) for o in ops if o["kind"] in ("door", "fire")]
    all_ranges = [(o["theta"] - o["dt"], o["theta"] + o["dt"]) for o in ops]
    bb = MB()
    for t1, t2 in _gaps(door_ranges):
        sweep(bb, [(0, 0), (0.035, 0), (0.035, 0.15), (0.02, 0.17), (0.02, 0.19), (0, 0.19)], t1, t2)
    bb.build("Baseboard", M["trim"], "Architecture")
    cr = MB()
    for t1, t2 in _gaps(all_ranges):
        sweep(cr, [(0, 0.86), (0.03, 0.86), (0.03, 0.90), (0.015, 0.92), (0, 0.92)], t1, t2)
    cr.build("ChairRail", M["trim"], "Architecture")
    return ops


def _gaps(ranges):
    ranges = sorted(ranges)
    out = []
    start = -math.pi
    for a, b in ranges:
        out.append((start, a))
        start = b
    out.append((start, math.pi))
    return [(a, b) for a, b in out if b - a > 1e-4]


# ------------------------------------------------------------------ windows
def build_window(M, theta, info):
    fr = frame_at(theta)
    root = empty(f"Window_{int(math.degrees(theta))}", fr, "Architecture")
    W, z0, z1 = WIN_W, WIN_Z0, WIN_Z1
    d = WALL_T
    mb = MB()
    # jambs lining the opening
    mb.add_box((-W / 2 - 0.03, d / 2, (z0 + z1) / 2), (0.06, d + 0.12, z1 - z0))
    mb.add_box((W / 2 + 0.03, d / 2, (z0 + z1) / 2), (0.06, d + 0.12, z1 - z0))
    mb.add_box((0, d / 2, z1 + 0.03), (W + 0.12, d + 0.12, 0.06))
    mb.add_box((0, d / 2, z0 - 0.03), (W + 0.12, d + 0.12, 0.06))
    # stool + apron
    mb.add_box((0, 0.10, z0 - 0.01), (W + 0.30, 0.26 + 0.16, 0.04))
    mb.add_box((0, -0.02, z0 - 0.10), (W + 0.26, 0.04, 0.14))
    # casing
    cw = 0.13
    mb.add_box((-W / 2 - 0.06 - cw / 2, -0.015, (z0 + z1 + 0.1) / 2), (cw, 0.03, z1 - z0 + 0.10))
    mb.add_box((W / 2 + 0.06 + cw / 2, -0.015, (z0 + z1 + 0.1) / 2), (cw, 0.03, z1 - z0 + 0.10))
    mb.add_box((0, -0.02, z1 + 0.06 + cw / 2), (W + 0.12 + 2 * cw, 0.04, cw))
    mb.add_box((0, -0.03, z1 + 0.06 + cw + 0.03), (W + 0.12 + 2 * cw + 0.08, 0.06, 0.06))
    trim = mb.build("WinTrim", M["trim"], "Architecture", bevel=0.004)
    parent(trim, root)
    # sash: frame + muntins (3 x 8 panes)
    sm = MB()
    y = 0.24
    sw = 0.05
    sm.add_box((-W / 2 + sw / 2, y, (z0 + z1) / 2), (sw, 0.045, z1 - z0))
    sm.add_box((W / 2 - sw / 2, y, (z0 + z1) / 2), (sw, 0.045, z1 - z0))
    sm.add_box((0, y, z1 - sw / 2), (W, 0.045, sw))
    sm.add_box((0, y, z0 + sw / 2), (W, 0.045, sw))
    sm.add_box((0, y, (z0 + z1) / 2), (W, 0.06, 0.07))   # meeting rail
    cols, rows = 3, 8
    for i in range(1, cols):
        sm.add_box((-W / 2 + W * i / cols, y, (z0 + z1) / 2), (0.022, 0.03, z1 - z0))
    for j in range(1, rows):
        sm.add_box((0, y, z0 + (z1 - z0) * j / rows), (W, 0.03, 0.022))
    sash = sm.build("WinSash", M["trim"], "Architecture", bevel=0.003)
    parent(sash, root)
    gm = MB()
    gm.add_quad((-W / 2, y, z0), (W / 2, y, z0), (W / 2, y, z1), (-W / 2, y, z1))
    g = gm.build("WinGlass", M["glass"], "Architecture", recalc=False)
    parent(g, root)
    # drapes: rod, two folded panels, swag valance
    rod = cyl("DrapeRod", (0, -0.16, z1 + 0.28), 0.02, W + 1.3, M["brass"], mat4=Matrix.Rotation(math.pi / 2, 4, 'Y'))
    parent(rod, root)
    for s in (-1, 1):
        fm = MB()
        px = s * (W / 2 + 0.16)
        def panel(u, v, px=px):
            x = px + (u - 0.5) * 0.72 + 0.02 * math.sin(u * math.pi * 5 + v * 3)
            yy = -0.13 - 0.06 * math.sin(u * math.pi * 4) - 0.02 * math.sin(u * math.pi * 9 + v * 4)
            z = 0.02 + v * (z1 + 0.24)
            return (x, yy, z)
        fm.add_grid(panel, 60, 12)
        p = fm.build("Drape", M["drape"], "Architecture", smooth=True, recalc=False)
        parent(p, root)
    vm = MB()
    def valance(u, v):
        x = (u - 0.5) * (W + 1.10)
        yy = -0.13 - 0.045 * math.sin(u * math.pi * 16)
        # scalloped lower edge (three swags)
        bottom = z1 + 0.32 - 0.36 - 0.18 * abs(math.sin(u * math.pi * 3))
        z = bottom + v * (z1 + 0.32 - bottom)
        return (x, yy, z)
    vm.add_grid(valance, 80, 6)
    v = vm.build("Valance", M["drape"], "Architecture", smooth=True, recalc=False)
    parent(v, root)
    # portal info for Cycles (area light in the opening plane, facing into the room)
    info["portals"].append(dict(matrix=fr @ Matrix.Translation((0, 0.10, (z0 + z1) / 2)), w=W, h=z1 - z0))
    return root


# ------------------------------------------------------------------ doors
def build_door(M, name, theta, info, french=False):
    fr = frame_at(theta)
    root = empty(f"Door_{name}", fr, "Architecture")
    W, Hd, d = DOOR_W, DOOR_H, WALL_T
    mb = MB()
    mb.add_box((-W / 2 - 0.03, d / 2, Hd / 2), (0.06, d + 0.12, Hd))
    mb.add_box((W / 2 + 0.03, d / 2, Hd / 2), (0.06, d + 0.12, Hd))
    mb.add_box((0, d / 2, Hd + 0.03), (W + 0.12, d + 0.12, 0.06))
    cw = 0.15
    mb.add_box((-W / 2 - 0.06 - cw / 2, -0.015, (Hd + 0.06) / 2), (cw, 0.03, Hd + 0.06))
    mb.add_box((W / 2 + 0.06 + cw / 2, -0.015, (Hd + 0.06) / 2), (cw, 0.03, Hd + 0.06))
    mb.add_box((0, -0.02, Hd + 0.06 + cw / 2), (W + 0.12 + 2 * cw, 0.04, cw))
    mb.add_box((0, -0.035, Hd + 0.06 + cw + 0.04), (W + 0.12 + 2 * cw + 0.10, 0.07, 0.08))  # header cap
    trim = mb.build("DoorTrim", M["trim"], "Architecture", bevel=0.004)
    parent(trim, root)
    lm = MB()
    leaf_y = 0.12
    lw, lh, lt = W - 0.02, Hd - 0.01, 0.05
    if not french:
        lm.add_box((0, leaf_y, lh / 2), (lw, lt, lh))
        # six raised panels (2 cols x 3 rows)
        pw = (lw - 3 * 0.11) / 2
        rows = [(0.12, 0.55), (0.78, 1.65), (1.78, 2.62)]
        for c in (-1, 1):
            for za, zb in rows:
                lm.add_box((c * (pw / 2 + 0.055), leaf_y - lt / 2 - 0.009, (za + zb) / 2), (pw - 0.06, 0.018, zb - za - 0.06))
                lm.add_box((c * (pw / 2 + 0.055), leaf_y - lt / 2 - 0.022, (za + zb) / 2), (pw - 0.16, 0.012, zb - za - 0.16))
        leaf = lm.build("DoorLeaf", M["trim"], "Architecture", bevel=0.005)
        parent(leaf, root)
    else:
        sw = 0.10
        lm.add_box((-lw / 2 + sw / 2, leaf_y, lh / 2), (sw, lt, lh))
        lm.add_box((lw / 2 - sw / 2, leaf_y, lh / 2), (sw, lt, lh))
        lm.add_box((0, leaf_y, lh - sw / 2), (lw, lt, sw))
        lm.add_box((0, leaf_y, 0.20), (lw, lt, 0.40))
        cols, rows = 3, 5
        gz0, gz1 = 0.40, lh - sw
        gw = lw - 2 * sw
        for i in range(1, cols):
            lm.add_box((-gw / 2 + gw * i / cols, leaf_y, (gz0 + gz1) / 2), (0.025, 0.035, gz1 - gz0))
        for j in range(1, rows):
            lm.add_box((0, leaf_y, gz0 + (gz1 - gz0) * j / rows), (gw, 0.035, 0.025))
        leaf = lm.build("DoorLeafFrench", M["trim"], "Architecture", bevel=0.004)
        parent(leaf, root)
        gm = MB()
        gm.add_quad((-gw / 2, leaf_y, gz0), (gw / 2, leaf_y, gz0), (gw / 2, leaf_y, gz1), (-gw / 2, leaf_y, gz1))
        g = gm.build("DoorGlass", M["glass"], "Architecture", recalc=False)
        parent(g, root)
        info["portals"].append(dict(matrix=fr @ Matrix.Translation((0, 0.05, (gz0 + gz1) / 2)), w=gw, h=gz1 - gz0))
    km = MB()
    km.add_sphere((W / 2 - 0.10, leaf_y - lt / 2 - 0.05, 1.02), 0.03)
    km.add_cyl((W / 2 - 0.10, leaf_y - lt / 2 - 0.02, 1.02), 0.035, 0.012, 24, Matrix.Rotation(math.pi / 2, 4, 'X'))
    km.add_cyl((W / 2 - 0.10, leaf_y - lt / 2 - 0.03, 1.02), 0.008, 0.05, 12, Matrix.Rotation(math.pi / 2, 4, 'X'))
    knob = km.build("DoorKnob", M["brass"], "Architecture", smooth=True)
    parent(knob, root)
    return root


# ------------------------------------------------------------------ fireplace
def build_fireplace(M, info):
    fr = frame_at(FIREPLACE)
    root = empty("Fireplace", fr, "Architecture")
    W, Hf = FIRE_W, FIRE_H
    depth = 0.40
    # firebox (open toward room, -Y)
    fb = MB()
    fb.add_quad((-W / 2, 0, 0), (-W / 2, depth, 0), (-W / 2, depth, Hf), (-W / 2, 0, Hf))
    fb.add_quad((W / 2, 0, 0), (W / 2, 0, Hf), (W / 2, depth, Hf), (W / 2, depth, 0))
    fb.add_quad((-W / 2, depth, 0), (W / 2, depth, 0), (W / 2, depth, Hf), (-W / 2, depth, Hf))
    fb.add_quad((-W / 2, 0, Hf), (W / 2, 0, Hf), (W / 2, depth, Hf), (-W / 2, depth, Hf))
    fb.add_quad((-W / 2, 0, 0), (W / 2, 0, 0), (W / 2, depth, 0), (-W / 2, depth, 0))
    box_ob = fb.build("Firebox", M["soot"], "Architecture", recalc=False)
    parent(box_ob, root)
    # marble surround, pilasters, frieze, shelf
    mm = MB()
    for s in (-1, 1):
        mm.add_box((s * 0.55, -0.015, Hf / 2), (0.12, 0.03, Hf))
        mm.add_box((s * 0.70, -0.08, 1.16 / 2), (0.20, 0.16, 1.16))
        mm.add_box((s * 0.70, -0.09, 1.16 + 0.02), (0.24, 0.18, 0.04))  # capital
        mm.add_box((s * 0.70, -0.09, 0.03), (0.24, 0.18, 0.06))        # base
    mm.add_box((0, -0.015, Hf + 0.08), (1.22, 0.03, 0.16))
    mm.add_box((0, -0.08, 1.16 + 0.10), (1.64, 0.16, 0.20))          # frieze
    mm.add_box((0, -0.115, 1.16 + 0.20 + 0.025), (1.80, 0.23, 0.05))  # shelf
    mm.add_box((0, -0.10, 1.16 + 0.20 - 0.01), (1.72, 0.20, 0.03))
    mm.add_box((0, -0.24, 0.01), (1.80, 0.48, 0.02))                  # hearth
    mantel = mm.build("Mantel", M["marble"], "Architecture", bevel=0.005)
    parent(mantel, root)
    # centre plaque on frieze
    pm = MB()
    pm.add_box((0, -0.165, 1.26), (0.36, 0.02, 0.12))
    pl = pm.build("MantelPlaque", M["marble_dark"], "Architecture", bevel=0.004)
    parent(pl, root)
    # andirons + grate + logs
    am = MB()
    for s in (-1, 1):
        am.add_cyl((s * 0.32, 0.10, 0.20), 0.018, 0.40, 16)
        am.add_sphere((s * 0.32, 0.10, 0.43), 0.04)
        am.add_box((s * 0.32, 0.20, 0.05), (0.03, 0.30, 0.03))
    for i in range(6):
        am.add_cyl((-0.30 + 0.12 * i, 0.20, 0.10), 0.008, 0.28, 8, Matrix.Rotation(math.pi / 2, 4, 'X'))
    am.add_cyl((0, 0.20, 0.10), 0.01, 0.62, 8, Matrix.Rotation(math.pi / 2, 4, 'Y'))
    and_ = am.build("Andirons", M["brass"], "Architecture", smooth=True)
    parent(and_, root)
    lg = MB()
    lg.add_cyl((0.0, 0.16, 0.17), 0.06, 0.66, 14, Matrix.Rotation(math.pi / 2, 4, 'Y'))
    lg.add_cyl((0.0, 0.27, 0.17), 0.055, 0.62, 14, Matrix.Rotation(math.pi / 2, 4, 'Y'))
    lg.add_cyl((0.02, 0.21, 0.27), 0.055, 0.58, 14, Matrix.Rotation(math.pi / 2, 4, 'Y') @ Matrix.Rotation(0.15, 4, 'Z'))
    logs = lg.build("Logs", M["walnut"], "Architecture", smooth=True)
    parent(logs, root)
    fm = MB()
    for (x, yy, h, r) in [(-0.15, 0.21, 0.55, 0.10), (0.05, 0.19, 0.70, 0.12), (0.2, 0.24, 0.5, 0.09), (-0.02, 0.26, 0.45, 0.08)]:
        fm.add_cyl((x, yy, 0.22 + h / 2), r, h, 12, r_top=0.005, closed=False)
    flames = fm.build("Flames", M["fire"], "Lights", smooth=True, recalc=False)
    flames.visible_shadow = False
    parent(flames, root)
    info["fire_light"] = fr @ Matrix.Translation((0, 0.18, 0.45))
    # mantel decor
    dm = MB()
    for s in (-1, 1):
        dm.add_cyl((s * 0.62, -0.11, 1.41 + 0.12), 0.05, 0.24, 20, r_top=0.03)
        dm.add_cyl((s * 0.62, -0.11, 1.41 + 0.26), 0.035, 0.04, 20, r_top=0.045)
    dec = dm.build("MantelVases", M["porcelain"], "Architecture", smooth=True)
    parent(dec, root)
    cm = MB()
    cm.add_box((0, -0.11, 1.41 + 0.11), (0.22, 0.10, 0.22))
    cm.add_cyl((0, -0.165, 1.41 + 0.11), 0.08, 0.01, 24, Matrix.Rotation(math.pi / 2, 4, 'X'))
    clock = cm.build("MantelClock", M["mahogany"], "Architecture", bevel=0.004)
    parent(clock, root)
    fm2 = MB()
    fm2.add_cyl((0, -0.172, 1.41 + 0.11), 0.07, 0.004, 24, Matrix.Rotation(math.pi / 2, 4, 'X'))
    face = fm2.build("MantelClockFace", M["paper"], "Architecture")
    parent(face, root)
    return root


# ------------------------------------------------------------------ exterior
def build_exterior(M):
    lawn = MB()
    lawn.add_quad((-120, -120, -0.02), (120, -120, -0.02), (120, 120, -0.02), (-120, 120, -0.02))
    lawn.build("Lawn", M["lawn"], "Exterior", recalc=False)
    # boxwood hedge outside the south windows, plus a low inner hedge
    hm = MB()
    sweep(hm, [(-1.30, 0.0), (-2.10, 0.0), (-2.10, 1.05), (-1.30, 1.05)], rad(-160), rad(-20))
    sweep(hm, [(-2.60, 0.0), (-3.20, 0.0), (-3.20, 0.55), (-2.60, 0.55)], rad(-165), rad(-15))
    hm.build("Hedge", M["foliage"], "Exterior")
    # trees on the south lawn
    tm = MB()
    lm = MB()
    import random
    rnd = random.Random(7)
    for i in range(30):
        t = rad(-178 + 176 * i / 29) + rnd.uniform(-0.03, 0.03)
        r = rnd.uniform(24, 48)
        p = ell_pt(t, -r, 0)
        h = rnd.uniform(7, 12)
        tm.add_cyl((p.x, p.y, h * 0.45), 0.25, h * 0.9, 10)
        for k in range(14):
            ang = rnd.uniform(0, TAU)
            rr = rnd.uniform(0, 2.4)
            lm.add_sphere((p.x + rr * math.cos(ang), p.y + rr * math.sin(ang), h * 0.85 + rnd.uniform(-1.8, 1.6)),
                          rnd.uniform(0.9, 1.5), 20, 10)
    tm.build("TreeTrunks", M["walnut"], "Exterior", smooth=True)
    lm.build("TreeCanopy", M["foliage"], "Exterior", smooth=True)
    # Rose Garden colonnade outside the east door
    cm = MB()
    for i in range(6):
        y = -3.75 + 1.5 * i
        cm.add_cyl((B + 2.9, y, 1.9), 0.20, 3.8, 24)
        cm.add_box((B + 2.9, y, 3.85), (0.5, 0.5, 0.1))
        cm.add_box((B + 2.9, y, 0.05), (0.5, 0.5, 0.1))
    cm.add_box((B + 1.65, 0, 4.05), (3.4, 9.0, 0.30))
    cm.add_box((B + 1.65, 0, 4.30), (3.6, 9.2, 0.20))
    cm.build("Colonnade", M["exterior"], "Exterior", smooth=True)
    pm = MB()
    pm.add_box((B + 1.7, 0, -0.005), (3.4, 9.0, 0.03))
    pm.build("ColonnadePaving", M["marble_dark"], "Exterior")
    # distant west/east wing walls so the view beyond the colonnade is not empty
    wm = MB()
    wm.add_box((B + 3.6, 6.5, 2.2), (0.6, 5.0, 4.4))
    wm.add_box((B + 3.6, -6.5, 2.2), (0.6, 5.0, 4.4))
    wm.build("WingWalls", M["exterior"], "Exterior")


def build(M):
    info = {"portals": []}
    ops = build_shell(M)
    for t in WINDOWS:
        build_window(M, t, info)
    for name, t in DOORS.items():
        build_door(M, name, t, info, french=(name == "east"))
    build_fireplace(M, info)
    build_exterior(M)
    return info
