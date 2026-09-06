"""Furniture and appliances: cabinets, counter, sink, stove, fridge, table, chairs, lamps and clutter."""
import math
from math import radians as rad
import bpy
from mathutils import Vector, Matrix
from helpers import (TAU, sring, cring, loft, slab, tube, blob, sphere, torus, cylinder, lathe, helix, spiral2d,
                     curl_top, lerp, smoothstep, rng, interp, rotate_about, set_origin, MB, link)
import materials as M
from architecture import wall_surface, to_wall, A, B, E, H, DOME

C = "Props"
COUNTER_Z = 0.92
DEPTH = 0.64


def ceiling_z(x, y):
    s = ((abs(x) / A) ** E + (abs(y) / B) ** E) ** (1.0 / E)
    if s >= 1.0:
        return H
    return H + DOME * math.sin(math.acos(s))


def back_y(x, z=COUNTER_Z):
    return wall_surface(x, z, 'back')


# ------------------------------------------------------------------ doors / knobs
PILLOW = [(0.0, 0.80), (0.10, 0.95), (0.35, 1.0), (0.65, 1.0), (0.90, 0.95), (1.0, 0.78)]


def pillow(name, center, w, h, depth, mat, e=4.0, wob=0.015, yaw=0.0, collection=C, phase=0.0):
    """Puffy door/drawer front. center = (x, y_back, z_centre); the pillow extends `depth` toward -y (rotated by yaw)."""
    m4 = Matrix.Translation(Vector(center)) @ Matrix.Rotation(yaw, 4, 'Z') @ Matrix.Rotation(math.pi / 2, 4, 'X')
    return blob(name, (0, 0, 0), (w, h, depth), mat, e=e, n=32, profile=PILLOW, wob=wob, wob_freq=4, phase=phase,
                subsurf=2, collection=collection, mat4=m4)


def knob(name, pos, color, r=0.045, stem=0.05, direction=(0, -1, 0), collection=C, stem_col="Chrome"):
    d = Vector(direction).normalized()
    p = Vector(pos)
    m4 = Matrix.Translation(p) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
    cylinder(name + "_stem", (0, 0, 0), r * 0.45, stem, M.metal(stem_col), n=12, collection=collection, mat4=m4)
    sphere(name, p + d * (stem + r * 0.7), r, M.candy("Knob_" + color, color), seg=20, rings=10, scale=(1, 1, 1),
           collection=collection)


def handle(name, p0, p1, color, r=0.022, bulge=0.07, collection=C):
    """U-shaped pull handle between two points on a front face (front = -y)."""
    p0, p1 = Vector(p0), Vector(p1)
    mid = (p0 + p1) / 2
    out = Vector((0, -1, 0)) * bulge
    pts = [p0, p0 + out * 0.9, mid + out, p1 + out * 0.9, p1]
    return tube(name, pts, radius=r, mat=M.metal("Chrome") if color == "Chrome" else M.candy("Knob_" + color, color),
                collection=collection, res=8)


# ------------------------------------------------------------------ base cabinets & counter
def base_cabinet(name, x0, x1, color, knob_col, kind="doors", ndoors=None, lean=0.0):
    w = x1 - x0
    xc = (x0 + x1) / 2
    yb = min(back_y(x0, 0.5), back_y(x1, 0.5)) + 0.02
    yc = yb - DEPTH / 2
    h = COUNTER_Z - 0.05
    z0 = 0.11
    body = blob(name, (xc, yc, z0), (w, DEPTH, h - z0), M.candy("Cab_" + color, color), e=5.0, n=36, bulge=0.025,
                lean=(lean, 0.0), wob=0.006, wob_freq=4, phase=rng.uniform(0, 6), subsurf=2, collection=C)
    # toe kick (dark, recessed)
    blob(name + "_kick", (xc, yc + 0.05, 0.0), (w - 0.1, DEPTH - 0.12, z0 + 0.02), M.matte("Kick", "ink"), e=6.0, n=24,
         subsurf=1, collection=C)
    yf = yc - DEPTH / 2 + 0.02   # front face (before bulge)
    if kind == "doors":
        nd = ndoors or (2 if w > 1.0 else 1)
        dw = (w - 0.10 * (nd + 1)) / nd
        for i in range(nd):
            dx = x0 + 0.10 + dw / 2 + i * (dw + 0.10) + lean * 0.5
            pillow(f"{name}_door{i}", (dx, yf - 0.01, z0 + (h - z0) / 2 + 0.02), dw, h - z0 - 0.16, 0.07,
                   M.candy("Door_" + color, color), phase=rng.uniform(0, 6))
            kx = dx + (dw / 2 - 0.10) * (1 if (nd == 1 or i == 0) else -1)
            knob(f"{name}_knob{i}", (kx, yf - 0.065, z0 + (h - z0) * 0.55), knob_col)
    else:  # drawers
        nd = 3
        dh = (h - z0 - 0.08 * (nd + 1)) / nd
        for i in range(nd):
            zc = z0 + 0.08 + dh / 2 + i * (dh + 0.08)
            pillow(f"{name}_drawer{i}", (xc + lean * (zc / h), yf - 0.01, zc), w - 0.16, dh, 0.07,
                   M.candy("Door_" + color, color), phase=rng.uniform(0, 6))
            handle(f"{name}_pull{i}", (xc - 0.16, yf - 0.06, zc), (xc + 0.16, yf - 0.06, zc), knob_col)
    return body


def countertop(name, x0, x1, mat):
    """Thick wavy slab that hugs the back wall; front edge waves, ends droop a little."""
    n = 60
    outline = []
    # front edge, left -> right
    for i in range(n + 1):
        x = lerp(x0, x1, i / n)
        yfront = back_y(x) - DEPTH - 0.06 + 0.035 * math.sin(2.1 * x + 0.5) + 0.02 * math.sin(5.3 * x)
        outline.append((x, yfront))
    # right end (rounded)
    yr_b = back_y(x1) + 0.06
    yr_f = outline[-1][1]
    for k in range(1, 8):
        t = k / 8
        outline.append((x1 + 0.10 * math.sin(math.pi * t), lerp(yr_f, yr_b, t)))
    # back edge, right -> left, following the wall (pushed 6 cm into it)
    for i in range(n, -1, -1):
        x = lerp(x0, x1, i / n)
        outline.append((x, back_y(x) + 0.06))
    yl_f = outline[0][1]
    for k in range(7, 0, -1):
        t = k / 8
        outline.append((x0 - 0.10 * math.sin(math.pi * t), lerp(yl_f, back_y(x0) + 0.06, t)))
    top = slab(name, outline, COUNTER_Z - 0.07, COUNTER_Z, mat, subsurf=1, collection=C,
               zfn_bottom=lambda x, y: -0.02 * math.sin(3.0 * x) - 0.01, zfn_top=lambda x, y: 0.0)
    return top


def backsplash(x0, x1):
    """Fat wavy piping where the counter meets the wall plus a scalloped tile band."""
    pts = [to_wall('back', lerp(x0, x1, i / 40), COUNTER_Z + 0.06 + 0.02 * math.sin(4 * lerp(x0, x1, i / 40)), 0.03)
           for i in range(41)]
    tube("Splash_pipe", pts, radius=0.05, mat=M.candy("Splash", "orange"), collection=C, res=6)
    # scallops: row of half-discs above the pipe
    n = int((x1 - x0) / 0.32)
    cols = ["yellow", "sky", "pink", "lime"]
    for i in range(n):
        x = x0 + 0.16 + i * 0.32
        pts = [to_wall('back', x + 0.16 * math.cos(t), COUNTER_Z + 0.09 + 0.16 * math.sin(t) * 1.15, 0.0)
               for t in [math.pi * k / 16 for k in range(17)]]
        pts += [to_wall('back', x - 0.16, COUNTER_Z + 0.09, 0.0)]
        loft(f"Scallop{i}", [pts, [p + Vector((0, -0.025, 0)) for p in pts]], M.candy("Scal_" + cols[i % 4], cols[i % 4]),
             C, subsurf=0, smooth=False)


# ------------------------------------------------------------------ sink & faucet
SINK_X = 0.12
SINK_A, SINK_B = 0.46, 0.30


def sink_hole():
    yc = back_y(SINK_X) - DEPTH / 2 - 0.02
    return [dict(axis_u='xy', u0=SINK_X, z0=yc, ru=SINK_A * 0.97, rz=SINK_B * 0.97, wob=0.03, freq=3, phase=0.0)]


def sink(counter, x):
    yb = back_y(x)
    yc = yb - DEPTH / 2 - 0.02
    a, b = SINK_A, SINK_B
    prof = [(0.06, 0.60), (0.55, 0.63), (0.85, 0.70), (0.95, 0.80), (1.0, 0.905), (1.06, 0.92), (1.10, 0.94), (1.0, 0.95),
            (0.94, 0.94)]
    basin = lathe("Sink_basin", [(r * a, z) for r, z in prof], (x, yc, 0), n=40, mat=M.metal("Steel", "#DDE3EA", 0.28),
                  wob=0.03, wob_freq=3, scale=(1, b / a), e=2.6, subsurf=1, collection=C)
    # drain
    torus("Sink_drain", (x, yc, 0.61), 0.05, 0.012, M.metal("Chrome"), nu=24, nv=8, collection=C)
    # faucet: stalk up, loop-de-loop, arch over the basin, hook down
    fx, fy = x + 0.05, yb - 0.11
    pts = [(fx, fy, COUNTER_Z), (fx, fy, COUNTER_Z + 0.25), (fx, fy - 0.02, COUNTER_Z + 0.45)]
    # a full loop in the (y, z) plane, radius 0.13, centred a little in front of the stalk
    cy, cz = fy - 0.13, COUNTER_Z + 0.55
    for k in range(1, 13):
        th = -math.pi / 2 + TAU * k / 12 * 1.0
        pts.append((fx + 0.02 * math.sin(th), cy + 0.13 * math.cos(th), cz + 0.13 * math.sin(th) + 0.02 * k / 12))
    pts += [(fx, fy - 0.36, COUNTER_Z + 0.66), (fx, fy - 0.50, COUNTER_Z + 0.55), (fx, fy - 0.52, COUNTER_Z + 0.40)]
    radii = [1.0] * len(pts)
    radii[0] = 1.5
    radii[-1] = 1.25
    tube("Faucet", pts, radius=0.032, mat=M.metal("Chrome"), radii=radii, collection=C, res=10)
    lathe("Faucet_base", [(0.07, 0.0), (0.07, 0.02), (0.05, 0.05), (0.04, 0.08)], (fx, fy, COUNTER_Z - 0.01), n=24,
          mat=M.metal("Chrome"), collection=C)
    # hot / cold: ball taps on bent stalks
    for dx, colr, nm in ((-0.26, "red", "Hot"), (0.32, "blue", "Cold")):
        sp = [(fx + dx, fy, COUNTER_Z), (fx + dx * 1.15, fy - 0.02, COUNTER_Z + 0.10), (fx + dx * 1.3, fy - 0.06, COUNTER_Z + 0.16)]
        tube(f"Tap{nm}_stalk", sp, radius=0.02, mat=M.metal("Chrome"), collection=C, res=6)
        sphere(f"Tap{nm}", (fx + dx * 1.32, fy - 0.07, COUNTER_Z + 0.20), 0.055, M.candy("Knob_" + colr, colr), collection=C)
    return basin


# ------------------------------------------------------------------ stove, hood
def stove(x0, x1):
    w = x1 - x0
    xc = (x0 + x1) / 2
    yb = min(back_y(x0, 0.5), back_y(x1, 0.5)) + 0.02
    yc = yb - DEPTH / 2
    h = COUNTER_Z - 0.02
    body_mat = M.candy("Stove", "red")
    blob("Stove", (xc, yc, 0.08), (w, DEPTH, h - 0.08), body_mat, e=5.5, n=36, bulge=0.03, lean=(0.03, 0.0),
         wob=0.006, wob_freq=4, subsurf=2, collection=C)
    blob("Stove_kick", (xc, yc + 0.05, 0.0), (w - 0.12, DEPTH - 0.12, 0.10), M.matte("Kick", "ink"), e=6.0, n=24,
         subsurf=1, collection=C)
    # cooktop plate
    blob("Stove_top", (xc, yc, h - 0.01), (w - 0.06, DEPTH - 0.06, 0.05), M.candy("StoveTop", "ink", rough=0.4),
         e=5.5, n=36, subsurf=1, collection=C)
    yf = yc - DEPTH / 2
    # oven door (pillow) with porthole window + fat handle
    pillow("Oven_door", (xc, yf, 0.45), w - 0.16, 0.50, 0.07, M.candy("OvenDoor", "coral"), phase=2.0)
    torus("Oven_window", (xc, yf - 0.07, 0.45), 0.16, 0.03, M.candy("OvenRim", "yellow"), nu=32, nv=10, wob=0.05,
          scale=(1.15, 1.0), mat4=Matrix.Translation((xc, yf - 0.07, 0.45)) @ Matrix.Rotation(math.pi / 2, 4, 'X')
          @ Matrix.Translation((-xc, -yf + 0.07, -0.45)), collection=C)
    cylinder("Oven_glass", (xc, yf - 0.065, 0.45), 0.155, 0.02, M.candy("OvenGlass", "#40303A", rough=0.15, coat=0.9), n=32,
             collection=C, mat4=Matrix.Translation((xc, yf - 0.065, 0.45)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
             @ Matrix.Translation((-xc, -yf + 0.065, -0.45)))
    handle("Oven_handle", (xc - w * 0.36, yf - 0.06, 0.74), (xc + w * 0.36, yf - 0.06, 0.74), "Chrome", r=0.03, bulge=0.10)
    # warming drawer below the oven door
    pillow("Stove_drawer", (xc, yf, 0.17), w - 0.16, 0.14, 0.06, M.candy("OvenDoor", "coral"), phase=4.0)
    # control knobs along the top front lip
    for i in range(5):
        kx = x0 + 0.13 + i * (w - 0.26) / 4
        knob(f"Stove_knob{i}", (kx, yf - 0.01, h - 0.10), ["yellow", "sky", "lime", "magenta", "orange"][i], r=0.04, stem=0.03)
    # burners: black rings with coil spirals
    coil_mat = M.matte("Coil", "ink", rough=0.5)
    ring_mat = M.candy("BurnerRing", "yellow")
    for i, (bx, by, br) in enumerate(((-0.24, 0.13, 0.13), (0.24, 0.13, 0.11), (-0.22, -0.14, 0.11), (0.24, -0.14, 0.14))):
        cx_, cy_ = xc + bx, yc + by
        torus(f"Burner_ring{i}", (cx_, cy_, h + 0.035), br + 0.02, 0.018, ring_mat, nu=32, nv=8, wob=0.03, collection=C)
        pts = helix((cx_, cy_), 0.015, br - 0.005, h + 0.035, h + 0.04, 3.0, n=70)
        tube(f"Burner_coil{i}", pts, radius=0.012, mat=coil_mat, collection=C, res=6)
    # backguard: a wavy raised lip at the back of the cooktop with a wobbly clock/timer bubble
    guard = [(xc + w * 0.5 * math.cos(t) * 1.0, h + 0.03 + 0.22 * math.sin(t) * (1 + 0.15 * math.sin(3 * t)))
             for t in [math.pi * k / 24 for k in range(25)]]
    guard += [(xc - w * 0.5, h + 0.03)]
    bg = [Vector((u, yb - 0.10, z)) for u, z in guard]
    loft("Stove_backguard", [bg, [p + Vector((0, -0.07, 0)) for p in bg]], body_mat, C, subsurf=1)
    sphere("Stove_timer", (xc + 0.02, yb - 0.19, h + 0.14), 0.07, M.candy("Timer", "sky"), scale=(1.2, 0.5, 1.0), collection=C)
    # hood: funnel + bendy pipe with hoop bands
    hz = 1.62
    hood_mat = M.candy("Hood", "teal")
    prof = [(0.55, 0.0), (0.56, 0.05), (0.42, 0.12), (0.30, 0.22), (0.20, 0.35), (0.15, 0.45), (0.14, 0.50)]
    lathe("Hood", prof, (xc, yc - 0.03, hz), n=36, mat=hood_mat, wob=0.05, wob_freq=4, scale=(1.0, 0.62), e=3.0,
          subsurf=1, collection=C, caps=False)
    lathe("Hood_lip", [(0.58, -0.02), (0.60, 0.0), (0.58, 0.03), (0.52, 0.04)], (xc, yc - 0.03, hz), n=36,
          mat=M.candy("HoodLip", "yellow"), wob=0.05, wob_freq=4, scale=(1.0, 0.62), e=3.0, subsurf=1, collection=C)
    pipe = [(xc, yc - 0.03, hz + 0.48), (xc + 0.05, yc - 0.02, hz + 0.75), (xc + 0.30, yc + 0.02, hz + 1.05),
            (xc + 0.10, yc + 0.12, hz + 1.35), (xc - 0.05, yc + 0.25, hz + 1.5), (xc - 0.02, yb + 0.3, hz + 1.6)]
    tube("Hood_pipe", pipe, radius=0.13, mat=hood_mat, collection=C, res=10)
    for i, t in enumerate((0.15, 0.42, 0.7)):
        # hoop bands: approximate by sampling the pipe polyline
        seg = int(t * (len(pipe) - 1))
        f = t * (len(pipe) - 1) - seg
        p = Vector(pipe[seg]).lerp(Vector(pipe[seg + 1]), f)
        d = (Vector(pipe[seg + 1]) - Vector(pipe[seg])).normalized()
        m4 = Matrix.Translation(p) @ d.to_track_quat('Z', 'Y').to_matrix().to_4x4() @ Matrix.Translation(-p)
        torus(f"Hood_band{i}", p, 0.14, 0.025, M.candy("HoodBand", ["yellow", "magenta", "yellow"][i]), nu=32, nv=8,
              mat4=m4, collection=C)
    # a light under the hood
    ld = bpy.data.lights.new("HoodLight", 'POINT')
    ld.energy = 25
    ld.color = (1.0, 0.85, 0.6)
    ld.shadow_soft_size = 0.08
    lo = bpy.data.objects.new("HoodLight", ld)
    lo.location = (xc, yc - 0.1, hz - 0.05)
    link(lo, "Lights")


def teapot(pos, color="yellow", stripe="red", scale=1.0):
    x, y, z = pos
    s = scale
    body = [(0.05, 0.0), (0.11, 0.01), (0.15, 0.05), (0.17, 0.12), (0.15, 0.19), (0.10, 0.23), (0.07, 0.245)]
    mat = M.stripes("Teapot_" + color + stripe, [color, stripe], width=0.05 * s, axis='z', wobble=0.05, wfreq=3)
    lathe("Teapot", [(r * s, zz * s) for r, zz in body], (x, y, z), n=32, mat=mat, wob=0.03, subsurf=1, collection=C)
    lathe("Teapot_lid", [(0.0, 0.0), (0.075, 0.0), (0.05, 0.03), (0.02, 0.05), (0.03, 0.08), (0.0, 0.10)],
          (x, y, z + 0.235 * s), n=24, mat=M.candy("Knob_" + stripe, stripe), subsurf=1, collection=C)
    spout = [(x + 0.14 * s, y, z + 0.10 * s), (x + 0.22 * s, y, z + 0.14 * s), (x + 0.26 * s, y - 0.01 * s, z + 0.24 * s),
             (x + 0.24 * s, y - 0.02 * s, z + 0.31 * s), (x + 0.19 * s, y - 0.02 * s, z + 0.33 * s)]
    tube("Teapot_spout", spout, radius=0.028 * s, mat=M.candy("Knob_" + stripe, stripe), radii=[1.3, 1.0, 0.8, 0.7, 0.6],
         collection=C, res=8)
    hnd = [(x - 0.14 * s, y, z + 0.08 * s), (x - 0.24 * s, y, z + 0.12 * s), (x - 0.27 * s, y, z + 0.22 * s),
           (x - 0.19 * s, y, z + 0.28 * s), (x - 0.09 * s, y, z + 0.24 * s)]
    tube("Teapot_handle", hnd, radius=0.02 * s, mat=M.candy("Knob_" + stripe, stripe), collection=C, res=8)
    # steam curl
    st = [(x + 0.19 * s, y - 0.02 * s, z + 0.35 * s)]
    st += spiral2d((x + 0.10 * s, y - 0.02 * s, z + 0.55 * s), 0.16 * s, 0.03 * s, 1.1, n=30, plane='XZ')
    tube("Teapot_steam", st, radius=0.025 * s, mat=M.matte("Steam", "#F4F6FF", rough=0.9),
         radii=[1.0] + [1.0 - 0.8 * (i / 30) for i in range(31)], collection=C, res=8)


# ------------------------------------------------------------------ fridge
def fridge(x, y_back):
    w, d, h = 1.02, 0.86, 2.15
    yc = y_back - d / 2
    body = M.candy("Fridge", "sky")
    blob("Fridge", (x, yc, 0.0), (w, d, h), body, e=3.4, n=40, bulge=0.07, lean=(-0.14, 0.03), taper=(0.86, 0.86),
         wob=0.008, wob_freq=4, subsurf=2, collection=C, edge=0.03)
    # dome cap
    lathe("Fridge_cap", [(0.40, 0.0), (0.42, 0.04), (0.36, 0.12), (0.22, 0.20), (0.0, 0.24)], (x - 0.14, yc + 0.03, h - 0.03),
          n=32, mat=M.candy("FridgeCap", "magenta"), scale=(1.0, 0.85), e=3.0, subsurf=1, collection=C)
    sphere("Fridge_capball", (x - 0.14, yc + 0.03, h + 0.24), 0.06, M.candy("Knob_yellow", "yellow"), collection=C)
    # doors follow the lean: front face y and x offset by height
    def lean_x(z):
        return x - 0.14 * smoothstep(z / h)

    def front_y(z):
        return yc - (d / 2) * (1 + 0.07 * math.sin(math.pi * z / h)) * lerp(1.0, 0.86, z / h)

    dmat = M.candy("FridgeDoor", "cream")
    zl = 0.75  # lower door centre
    pillow("Fridge_door_lo", (lean_x(zl), front_y(zl) + 0.03, zl), w * 0.82 * (1 + 0.05), 1.30, 0.08, dmat, e=3.5, phase=1.0)
    zu = 1.75
    pillow("Fridge_door_up", (lean_x(zu), front_y(zu) + 0.03, zu), w * 0.72, 0.50, 0.08, dmat, e=3.5, phase=3.0)
    # handles: vertical wavy tubes
    for nm, z0, z1 in (("lo", 0.35, 1.25), ("up", 1.58, 1.92)):
        pts = []
        for i in range(7):
            zz = lerp(z0, z1, i / 6)
            pts.append((lean_x(zz) - w * 0.30 + 0.02 * math.sin(6 * zz), front_y(zz) - 0.11 - 0.02 * math.sin(4 * zz), zz))
        tube(f"Fridge_handle_{nm}", pts, radius=0.04, mat=M.candy("Knob_red", "red"), collection=C, res=8,
             radii=[1.0, 1.15, 1.25, 1.3, 1.25, 1.15, 1.0])
        for p in (pts[0], pts[-1]):
            cylinder(f"Fridge_hstem_{nm}_{p[2]:.2f}", (0, 0, 0), 0.022, 0.10, M.metal("Chrome"), n=10, collection=C,
                     mat4=Matrix.Translation((p[0], p[1] + 0.10, p[2])) @ Matrix.Rotation(-math.pi / 2, 4, 'X'))
    # magnets: little coloured discs on the lower door
    for i, (dx, dz, colr) in enumerate(((0.10, 1.05, "red"), (0.22, 0.95, "lime"), (0.05, 0.62, "purple"), (0.25, 0.55, "orange"),
                                         (0.16, 0.78, "yellow"))):
        zz = dz
        cylinder(f"Magnet{i}", (0, 0, 0), 0.045, 0.02, M.candy("Knob_" + colr, colr), n=20, collection=C,
                 mat4=Matrix.Translation((lean_x(zz) + dx, front_y(zz) - 0.075, zz)) @ Matrix.Rotation(math.pi / 2, 4, 'X'))


# ------------------------------------------------------------------ upper cabinets
def upper_cabinet(name, x0, x1, z0, z1, color, knob_col, lean=0.0, taper=0.92, depth=0.38, finial=None):
    w = x1 - x0
    xc = (x0 + x1) / 2
    yb = min(back_y(x0, (z0 + z1) / 2), back_y(x1, (z0 + z1) / 2)) + 0.03
    yc = yb - depth / 2
    h = z1 - z0
    blob(name, (xc, yc, z0), (w, depth, h), M.candy("Cab_" + color, color), e=5.0, n=36, bulge=0.02,
         lean=(lean, 0.0), taper=(taper, 1.0), wob=0.006, wob_freq=4, phase=rng.uniform(0, 6), subsurf=2, collection=C)
    yf = yc - depth / 2 + 0.02
    nd = 2 if w > 0.85 else 1
    dw = (w * 0.96 - 0.08 * (nd + 1)) / nd
    for i in range(nd):
        zc = z0 + h / 2
        dx = xc - (w * 0.96) / 2 + 0.08 + dw / 2 + i * (dw + 0.08) + lean * 0.5
        pillow(f"{name}_door{i}", (dx, yf - 0.01, zc), dw, h - 0.16, 0.07, M.candy("Door_" + color, color), phase=rng.uniform(0, 6))
        kx = dx + (dw / 2 - 0.09) * (1 if (nd == 1 or i == 0) else -1)
        knob(f"{name}_knob{i}", (kx, yf - 0.065, z0 + h * 0.3), knob_col, r=0.04)
    # bottom "under-cabinet" light strip: skipped; a curly finial on top instead
    if finial:
        pts, radii = curl_top((xc + lean + 0.1, yc, z1 - 0.01), 0.45, 0.16, turns=1.4, dir_xy=(1.0, 0.0), bend=0.15)
        tube(name + "_finial", pts, radius=0.045, mat=M.candy("Knob_" + finial, finial), radii=radii, collection=C, res=8)


def wall_shelves():
    """Two wavy shelves on the right wall (front of the window) on curly brackets, loaded with jars."""
    side = 'right'
    shelf_mat = M.candy("Shelf", "orange")
    jars = [("teal", "white"), ("magenta", "yellow"), ("lime", "purple"), ("red", "cream"), ("sky", "orange"), ("yellow", "ink")]
    for si, (y0, y1, z) in enumerate(((-2.8, -1.25, 1.35), (-2.7, -1.15, 1.95))):
        n = 24
        outline = []
        for i in range(n + 1):
            y = lerp(y0, y1, i / n)
            outline.append((wall_surface(y, z, side) - 0.30 - 0.03 * math.sin(4 * y + si), y))
        for k in range(1, 6):
            t = k / 6
            outline.append((wall_surface(y1, z, side) - 0.30 + 0.30 * t, y1 + 0.06 * math.sin(math.pi * t)))
        for i in range(n, -1, -1):
            y = lerp(y0, y1, i / n)
            outline.append((wall_surface(y, z, side) + 0.04, y))
        for k in range(5, 0, -1):
            t = k / 6
            outline.append((wall_surface(y0, z, side) - 0.30 + 0.30 * t, y0 - 0.06 * math.sin(math.pi * t)))
        # outline is CW seen from above (x decreasing first) -> reverse to CCW
        outline.reverse()
        slab(f"Shelf{si}", outline, z - 0.045, z, shelf_mat, subsurf=1, collection=C,
             zfn_bottom=lambda x, y: -0.015 * math.sin(5 * y))
        # brackets: curls under the shelf
        for by in (y0 + 0.25, y1 - 0.25):
            bx = wall_surface(by, z - 0.2, side) - 0.01
            pts = [(bx, by, z - 0.30), (bx - 0.05, by, z - 0.22), (bx - 0.16, by, z - 0.12), (bx - 0.22, by, z - 0.06)]
            pts += spiral2d((bx - 0.15, by, z - 0.12), 0.06, 0.015, 0.9, n=16, plane='XZ')
            tube(f"Bracket{si}_{by:.2f}", pts, radius=0.02, mat=M.candy("Frame_yellow", "yellow"),
                 radii=[1.2, 1.0, 1.0, 1.0] + [1.0 - 0.6 * i / 16 for i in range(17)], collection=C, res=8)
        # jars
        ys = [lerp(y0 + 0.15, y1 - 0.15, i / 3.0) for i in range(4)]
        for ji, jy in enumerate(ys):
            jc, jl = jars[(si * 4 + ji) % len(jars)]
            jh = rng.uniform(0.18, 0.34)
            jr = rng.uniform(0.07, 0.11)
            jx = wall_surface(jy, z, side) - 0.16 + rng.uniform(-0.03, 0.03)
            mat = M.stripes(f"Jar_{jc}_{jl}", [jc, jl], width=0.035, axis='z', wobble=0.03, wfreq=4)
            prof = [(jr * 0.8, 0.0), (jr, 0.03), (jr * 1.05, jh * 0.5), (jr * 0.9, jh * 0.85), (jr * 0.55, jh * 0.9),
                    (jr * 0.6, jh)]
            lathe(f"Jar{si}_{ji}", prof, (jx, jy, z), n=24, mat=mat, wob=0.03, subsurf=1, collection=C,
                  lean=(rng.uniform(-0.03, 0.03), rng.uniform(-0.03, 0.03)))
            lathe(f"JarLid{si}_{ji}", [(jr * 0.62, 0.0), (jr * 0.64, 0.02), (jr * 0.5, 0.05), (0.0, 0.07)],
                  (jx, jy, z + jh), n=20, mat=M.candy("Knob_" + jl, jl), subsurf=1, collection=C)


# ------------------------------------------------------------------ table & chairs
def table(cx, cy):
    top_mat = M.swirl("TableTop", "#FFB347", "#FFE08A", scale=2.5)
    lathe("Table_top", [(0.55, 0.70), (0.76, 0.70), (0.82, 0.735), (0.77, 0.77), (0.0, 0.77)], (cx, cy, 0), n=56,
          mat=top_mat, wob=0.05, wob_freq=5, phase=1.0, subsurf=1, collection=C)
    # thick coloured rim tube around the edge
    rim = [Vector((cx + 0.80 * (1 + 0.05 * math.sin(5 * t + 1.0)) * math.cos(t), cy + 0.80 * (1 + 0.05 * math.sin(5 * t + 1.0)) * math.sin(t), 0.735))
           for t in [TAU * k / 56 for k in range(56)]]
    tube("Table_rim", rim, radius=0.035, mat=M.candy("Frame_red", "red"), cyclic=True, collection=C, res=4)
    ped_mat = M.stripes("Pedestal", ["teal", "white"], width=0.06, axis='z', tilt=0.9, wobble=0.05, wfreq=2)
    blob("Table_pedestal", (cx, cy, 0.08), (0.30, 0.30, 0.64), ped_mat, e=2.6, n=32, bulge=0.30, twist=1.6, wob=0.14,
         wob_freq=4, subsurf=2, collection=C, zrings=[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
    lathe("Table_base", [(0.0, 0.0), (0.50, 0.0), (0.46, 0.06), (0.30, 0.10), (0.16, 0.12), (0.0, 0.13)], (cx, cy, 0),
          n=40, mat=M.candy("Knob_teal", "teal"), wob=0.05, wob_freq=4, subsurf=1, collection=C)


def chair(name, pos, yaw, color, accent):
    """Round seat on splayed legs with ball feet, tall back stalks that curl over."""
    x, y = pos
    R = Matrix.Translation((x, y, 0)) @ Matrix.Rotation(yaw, 4, 'Z')
    seat_z = 0.47
    cmat = M.candy("Chair_" + color, color)
    amat = M.candy("Knob_" + accent, accent)
    lathe(name + "_seat", [(0.20, -0.05), (0.26, -0.03), (0.28, 0.0), (0.26, 0.03), (0.0, 0.04)], (0, 0, seat_z), n=32,
          mat=cmat, wob=0.04, wob_freq=3, subsurf=1, collection=C, mat4=R)
    sphere(name + "_cushion", R @ Vector((0, 0, seat_z + 0.06)), 0.22, M.dots(f"Cushion_{accent}", accent, "white", 0.06, 0.32),
           seg=24, rings=12, scale=(1.0, 1.0, 0.32), collection=C)
    # legs
    for i, (lx, ly) in enumerate(((-0.17, -0.17), (0.17, -0.17), (-0.17, 0.17), (0.17, 0.17))):
        top = Vector((lx, ly, seat_z - 0.03))
        bot = Vector((lx * 1.7 + 0.03 * math.sin(i), ly * 1.7, 0.05))
        mid = (top + bot) / 2 + Vector((0.03 * (1 if i % 2 else -1), 0.02, 0))
        pts = [R @ top, R @ mid, R @ bot]
        tube(f"{name}_leg{i}", pts, radius=0.03, mat=cmat, radii=[1.3, 1.0, 0.7], collection=C, res=6)
        sphere(f"{name}_foot{i}", R @ bot, 0.05, amat, seg=16, rings=8, collection=C)
    # back: two stalks that rise, lean back a little and curl forward at the top (+y is the chair's back)
    for i, sx in enumerate((-0.15, 0.15)):
        base = (sx, 0.20, seat_z + 0.02)
        pts, radii = curl_top(base, 0.75 + 0.08 * i, 0.12, turns=1.3, dir_xy=(0.0, -1.0), bend=-0.18)
        pts = [tuple(R @ Vector(p)) for p in pts]
        tube(f"{name}_stalk{i}", pts, radius=0.03, mat=cmat, radii=radii, collection=C, res=8)
    # wavy rungs between the stalks
    for j, zz in enumerate((seat_z + 0.25, seat_z + 0.45, seat_z + 0.62)):
        pts = []
        for k in range(7):
            t = k / 6
            sx = lerp(-0.15, 0.15, t)
            back = 0.20 + 0.18 * ((zz - seat_z) / 0.8) ** 2 * 0.9
            pts.append(tuple(R @ Vector((sx, back + 0.02 * math.sin(3 * t * math.pi + j), zz + 0.03 * math.sin(2 * math.pi * t + j)))))
        tube(f"{name}_rung{j}", pts, radius=0.02, mat=amat, collection=C, res=6)


def rug(cx, cy):
    mat = M.swirl("Rug", "#F1479C", "#FFD23F", scale=1.6, rough=0.95, coat=0.0)
    ob = lathe("Rug", [(0.0, 0.0), (1.55, 0.0), (1.58, 0.012), (1.52, 0.02), (0.0, 0.02)], (0, 0, 0), n=48, mat=mat,
               wob=0.05, wob_freq=6, scale=(1.0, 0.8), subsurf=1, collection=C)
    ob.location = (cx, cy, 0.004)
    return ob


# ------------------------------------------------------------------ lamps
def pendant(name, x, y, z_bulb, shade_col, stripe_col, size=1.0, watts=45.0):
    cz = ceiling_z(x, y) + 0.1
    pts = []
    n = 8
    for i in range(n + 1):
        t = i / n
        pts.append((x + 0.06 * size * math.sin(3.5 * t * math.pi) * (1 - t), y + 0.05 * size * math.sin(2.5 * t * math.pi) * (1 - t),
                    lerp(cz, z_bulb + 0.32 * size, t)))
    tube(name + "_cord", pts, radius=0.012, mat=M.candy("Cord", "ink"), collection="Lights", res=8)
    smat = M.stripes(f"Shade_{shade_col}_{stripe_col}", [shade_col, stripe_col], width=0.05 * size, axis='z', tilt=0.35,
                     wobble=0.04, wfreq=3)
    prof = [(0.30, 0.0), (0.27, 0.04), (0.20, 0.13), (0.12, 0.24), (0.07, 0.31), (0.04, 0.34)]
    lathe(name + "_shade", [(r * size, zz * size) for r, zz in prof], (x, y, z_bulb - 0.02), n=36, mat=smat, wob=0.05,
          wob_freq=5, subsurf=1, collection="Lights", caps=False)
    # rim bead + top knob
    tube(name + "_rim", cring(x, y, z_bulb - 0.02, 0.30 * size, 36, wob=0.05, wob_freq=5), radius=0.018 * size,
         mat=M.candy("Knob_" + stripe_col, stripe_col), cyclic=True, collection="Lights", res=4)
    sphere(name + "_bulb", (x, y, z_bulb + 0.06 * size), 0.06 * size, M.glow_paint("Bulb", "#FFF1C4", strength=10.0), seg=16,
           rings=8, collection="Lights")
    ld = bpy.data.lights.new(name + "_light", 'POINT')
    ld.energy = watts
    ld.color = (1.0, 0.86, 0.66)
    ld.shadow_soft_size = 0.07
    lo = bpy.data.objects.new(name + "_light", ld)
    lo.location = (x, y, z_bulb + 0.02 * size)
    link(lo, "Lights")


# ------------------------------------------------------------------ clutter
def plant(pos):
    x, y = pos
    pot = M.stripes("Pot", ["orange", "purple"], width=0.06, axis='z', tilt=0.5, wobble=0.05, wfreq=3)
    lathe("Pot", [(0.20, 0.0), (0.24, 0.02), (0.26, 0.30), (0.32, 0.40), (0.34, 0.46), (0.30, 0.48), (0.0, 0.48)],
          (x, y, 0), n=32, mat=pot, wob=0.04, wob_freq=4, subsurf=1, collection=C)
    lathe("Pot_soil", [(0.0, 0.42), (0.28, 0.42), (0.0, 0.46)], (x, y, 0), n=24, mat=M.matte("Soil", "chocolate"), collection=C)
    stems = [((0.0, 0.0), 1.1, (0.35, 0.10), "pink", 0.24), ((0.10, -0.06), 0.8, (-0.3, 0.3), "yellow", 0.18),
             ((-0.08, 0.08), 0.95, (-0.2, -0.35), "orange", 0.2), ((0.05, 0.1), 0.6, (0.4, 0.3), "magenta", 0.15)]
    smat = M.candy("Stem", "green")
    for i, ((dx, dy), hgt, ln, colr, r) in enumerate(stems):
        pts, radii = [], []
        for k in range(11):
            t = k / 10
            pts.append((x + dx + ln[0] * t * t + 0.04 * math.sin(6 * t + i), y + dy + ln[1] * t * t, 0.44 + hgt * t))
            radii.append(1.0 - 0.5 * t)
        tube(f"Stem{i}", pts, radius=0.025, mat=smat, radii=radii, collection=C, res=8)
        s = sphere(f"Leafpom{i}", (pts[-1][0], pts[-1][1], pts[-1][2] + r * 0.6), r, M.fuzz("Pom_" + colr, colr), seg=24,
                   rings=12, scale=(1.1, 1.0, 0.85), collection=C)
        tex = bpy.data.textures.get("PomNoise") or bpy.data.textures.new("PomNoise", 'CLOUDS')
        d = s.modifiers.new("Fluff", 'DISPLACE')
        d.texture = tex
        d.strength = 0.12


def clock(side, u, z):
    r = 0.30
    face = [(u + r * math.cos(t) * (1 + 0.06 * math.sin(3 * t)), z + r * math.sin(t) * (1 + 0.05 * math.cos(2 * t)))
            for t in [TAU * k / 40 for k in range(40)]]
    from architecture import panel
    panel("Clock_face", side, face, 0.05, M.candy("ClockFace", "cream", rough=0.5), off=0.0)
    rim = [to_wall(side, uu, zz, 0.05) for uu, zz in face]
    tube("Clock_rim", rim, radius=0.04, mat=M.candy("Frame_red", "red"), cyclic=True, collection=C, res=4)
    for k in range(12):
        t = TAU * k / 12
        p = to_wall(side, u + r * 0.78 * math.cos(t), z + r * 0.78 * math.sin(t), 0.06)
        sphere(f"Clock_dot{k}", p, 0.02 if k % 3 else 0.032, M.candy("Knob_" + ("purple" if k % 3 else "teal"), "purple" if k % 3 else "teal"),
               seg=10, rings=6, collection=C)
    for nm, ang, ln in (("hour", 0.8, 0.14), ("minute", 2.4, 0.22)):
        pts = [to_wall(side, u + ln * t * math.cos(ang) + 0.03 * math.sin(3 * t), z + ln * t * math.sin(ang), 0.07) for t in
               (0, 0.3, 0.6, 0.85, 1.0)]
        tube("Clock_" + nm, pts, radius=0.022, mat=M.candy("Cord", "ink"), radii=[1.3, 1.1, 0.9, 0.7, 0.45], collection=C, res=6)
    sphere("Clock_pin", to_wall(side, u, z, 0.08), 0.03, M.candy("Knob_yellow", "yellow"), seg=12, rings=6, collection=C)


def cups(x, y, z):
    cols = ["red", "yellow", "sky", "lime", "magenta"]
    # leaning tower of cups
    lean = 0.0
    for i in range(5):
        h = 0.085
        cx, cy = x + lean, y + lean * 0.3
        lathe(f"Cup{i}", [(0.045, 0.0), (0.05, 0.01), (0.058, h * 0.8), (0.06, h)], (cx, cy, z + i * h * 0.78), n=20,
              mat=M.candy("Knob_" + cols[i], cols[i]), wob=0.02, subsurf=1, collection=C, lean=(0.012, 0.004))
        hn = [(cx + 0.058, cy, z + i * h * 0.78 + 0.02), (cx + 0.10, cy, z + i * h * 0.78 + 0.04), (cx + 0.06, cy, z + i * h * 0.78 + 0.07)]
        tube(f"Cup{i}_handle", hn, radius=0.009, mat=M.candy("Knob_" + cols[i], cols[i]), collection=C, res=6)
        lean += 0.014


def fruit_bowl(x, y, z):
    lathe("Bowl", [(0.06, 0.0), (0.16, 0.01), (0.27, 0.06), (0.30, 0.10), (0.28, 0.11), (0.25, 0.10), (0.14, 0.05), (0.0, 0.04)],
          (x, y, z), n=36, mat=M.dots("BowlDots", "teal", "yellow", 0.06, 0.3), wob=0.04, wob_freq=5, subsurf=1, collection=C)
    fruits = [((0.0, 0.0, 0.12), 0.075, "red", "yellow"), ((0.12, 0.05, 0.11), 0.06, "orange", "lime"),
              ((-0.11, 0.06, 0.11), 0.065, "purple", "pink"), ((0.02, -0.12, 0.11), 0.06, "lime", "magenta"),
              ((-0.03, 0.02, 0.24), 0.055, "yellow", "sky")]
    for i, (o, r, c1, c2) in enumerate(fruits):
        m = M.stripes(f"Fruit_{c1}_{c2}", [c1, c2], width=0.02, axis='z', tilt=0.6, wobble=0.02, wfreq=6)
        sphere(f"Fruit{i}", (x + o[0], y + o[1], z + o[2]), r, m, seg=20, rings=10, scale=(1, 1, 1.15), collection=C)
        stem = [(x + o[0], y + o[1], z + o[2] + r * 1.1), (x + o[0] + 0.02, y + o[1], z + o[2] + r * 1.1 + 0.04),
                (x + o[0] + 0.05, y + o[1] + 0.01, z + o[2] + r * 1.1 + 0.05)]
        tube(f"Fruit{i}_stem", stem, radius=0.006, mat=M.candy("Stem", "green"), radii=[1.0, 0.8, 0.5], collection=C, res=4)


def utensils(x, y, z):
    lathe("Crock", [(0.07, 0.0), (0.09, 0.02), (0.10, 0.16), (0.085, 0.19), (0.09, 0.20)], (x, y, z), n=24,
          mat=M.dots("CrockDots", "yellow", "red", 0.05, 0.3), wob=0.03, subsurf=1, collection=C)
    for i in range(4):
        ang = TAU * i / 4 + 0.4
        dx, dy = 0.04 * math.cos(ang), 0.04 * math.sin(ang)
        lean = (0.12 * math.cos(ang), 0.12 * math.sin(ang))
        pts = [(x + dx, y + dy, z + 0.05), (x + dx + lean[0] * 0.5, y + dy + lean[1] * 0.5, z + 0.25),
               (x + dx + lean[0], y + dy + lean[1], z + 0.42)]
        tube(f"Spoon{i}", pts, radius=0.008, mat=M.metal("Chrome"), collection=C, res=6)
        end = Vector(pts[-1])
        if i % 2 == 0:
            sphere(f"Spoon{i}_head", end + Vector((lean[0] * 0.15, lean[1] * 0.15, 0.03)), 0.035, M.metal("Chrome"), seg=14,
                   rings=8, scale=(1, 1, 0.5), collection=C)
        else:
            sphere(f"Spoon{i}_head", end + Vector((0, 0, 0.03)), 0.03, M.candy("Knob_red", "red"), seg=14, rings=8,
                   scale=(1.2, 0.5, 1.4), collection=C)


def plates(x, y, z):
    cols = ["sky", "pink", "lime", "yellow"]
    for i in range(4):
        m4 = Matrix.Translation((x, y, z + i * 0.03)) @ Matrix.Rotation(rad(3 + 2 * i), 4, 'Y') @ Matrix.Rotation(rad(i * 9), 4, 'Z')
        lathe(f"Plate{i}", [(0.0, 0.0), (0.08, 0.0), (0.14, 0.02), (0.16, 0.03), (0.15, 0.035), (0.06, 0.012), (0.0, 0.012)],
              (0, 0, 0), n=28, mat=M.candy("Knob_" + cols[i], cols[i]), wob=0.03, wob_freq=4, subsurf=1, collection=C, mat4=m4)


def pot_rail():
    """A curvy rail on the left wall near the stove with pans hanging from curly hooks."""
    side = 'left'
    z = 2.05
    ys = [lerp(0.55, 2.75, i / 24) for i in range(25)]
    rail = [to_wall(side, y, z + 0.08 * math.sin(2.2 * y) + 0.03 * math.sin(5 * y), 0.12) for y in ys]
    tube("PotRail", rail, radius=0.03, mat=M.candy("Frame_yellow", "yellow"), collection=C, res=6)
    for y in (0.7, 2.6):
        p0 = to_wall(side, y, z + 0.08 * math.sin(2.2 * y) + 0.03 * math.sin(5 * y), 0.0)
        pts = [p0, p0 + Vector((0.06, 0, -0.02)), p0 + Vector((0.12, 0, 0.0))]
        tube(f"PotRailMount{y:.1f}", pts, radius=0.025, mat=M.candy("Frame_red", "red"), collection=C, res=4)
    pans = [(0.95, 0.16, "red", "yellow"), (1.55, 0.12, "sky", "magenta"), (2.15, 0.19, "lime", "purple")]
    for i, (y, r, colr, acc) in enumerate(pans):
        zr = z + 0.08 * math.sin(2.2 * y) + 0.03 * math.sin(5 * y)
        top = to_wall(side, y, zr, 0.12)
        # hook: little curl hanging off the rail
        hook = [top, top + Vector((0.0, 0.0, -0.05)), top + Vector((0.03, 0.0, -0.09)), top + Vector((0.06, 0, -0.06))]
        tube(f"Hook{i}", hook, radius=0.012, mat=M.metal("Chrome"), collection=C, res=6)
        # handle hangs from the hook, pan below, dish facing the room (+x)
        hz = zr - 0.08
        handle_pts = [(top.x + 0.05, top.y, hz), (top.x + 0.06, top.y + 0.01, hz - 0.18), (top.x + 0.05, top.y, hz - 0.36)]
        tube(f"PanHandle{i}", handle_pts, radius=0.02, mat=M.candy("Knob_" + acc, acc), radii=[0.8, 1.1, 1.0], collection=C, res=6)
        cz = hz - 0.36 - r
        m4 = Matrix.Translation((top.x + 0.05, top.y, cz)) @ Matrix.Rotation(math.pi / 2, 4, 'Y')
        lathe(f"Pan{i}", [(0.0, 0.0), (r * 0.7, 0.0), (r * 0.95, 0.035), (r, 0.06), (r * 0.9, 0.065), (r * 0.7, 0.03), (0.0, 0.02)],
              (0, 0, 0), n=32, mat=M.candy("Cab_" + colr, colr), wob=0.03, wob_freq=4, subsurf=1, collection=C, mat4=m4)
        torus(f"PanRim{i}", (0, 0, 0), r * 0.98, 0.014, M.candy("Knob_" + acc, acc), nu=32, nv=8, collection=C,
              mat4=Matrix.Translation((top.x + 0.05 - 0.06, top.y, cz)) @ Matrix.Rotation(math.pi / 2, 4, 'Y'))


# ------------------------------------------------------------------ assemble
def build():
    x_left, x_right = -3.75, 2.62
    counter_mat = M.swirl("Counter", "#FFE08A", "#FFB347", scale=1.8, holes=sink_hole())
    # base run
    base_cabinet("Cab_A", x_left, -2.85, "yellow", "magenta", "doors", lean=-0.03)
    stove(-2.85, -1.75)
    base_cabinet("Cab_B", -1.75, -0.88, "teal", "orange", "drawers", lean=0.02)
    base_cabinet("Cab_Sink", -0.88, 1.10, "magenta", "yellow", "doors", ndoors=2, lean=0.0)
    base_cabinet("Cab_C", 1.10, 1.92, "purple", "lime", "doors", lean=0.03)
    base_cabinet("Cab_D", 1.92, x_right, "lime", "purple", "drawers", lean=-0.02)
    countertop("CounterL", x_left, -2.85, counter_mat)
    counter = countertop("CounterR", -1.75, x_right, counter_mat)
    backsplash(x_left + 0.05, x_right - 0.05)
    sink(counter, SINK_X)
    fridge(3.38, back_y(3.4, 1.0) - 0.02)
    # upper cabinets: staggered, leaning, with a curl on the tallest
    upper_cabinet("Up_A", -3.85, -2.95, 1.55, 2.55, "sky", "red", lean=0.06, taper=0.9, finial="red")
    upper_cabinet("Up_B", -2.95, -2.05, 1.85, 2.55, "orange", "teal", lean=-0.04, taper=0.94)
    upper_cabinet("Up_C", -2.05, -0.95, 1.55, 2.40, "green", "yellow", lean=0.05, taper=0.92)
    upper_cabinet("Up_D", 1.05, 1.95, 1.60, 2.50, "yellow", "purple", lean=-0.06, taper=0.9, finial="purple")
    # stacked little spice boxes on top of Up_B
    for i, (dx, colr, yaw) in enumerate(((-0.15, "magenta", 0.15), (0.12, "lime", -0.2))):
        yb = back_y(-2.5, 2.6) - 0.22
        blob(f"Spice{i}", (0, 0, 0), (0.30, 0.26, 0.28 + 0.06 * i), M.candy("Cab_" + colr, colr), e=4.5, n=24, bulge=0.05,
             wob=0.01, subsurf=2, collection=C, mat4=Matrix.Translation((-2.5 + dx, yb, 2.55 + 0.02)) @ Matrix.Rotation(yaw, 4, 'Z'))
        knob(f"Spice{i}_knob", (-2.5 + dx - 0.13 * math.sin(yaw), yb - 0.13 * math.cos(yaw), 2.70), "yellow", r=0.03, stem=0.02,
             direction=(-math.sin(yaw), -math.cos(yaw), 0))
    wall_shelves()
    # table & chairs
    tx, ty = 0.35, -0.55
    rug(tx, ty)
    table(tx, ty)
    for i, (ang, colr, acc) in enumerate(((rad(45), "red", "yellow"), (rad(135), "teal", "magenta"),
                                            (rad(225), "purple", "lime"), (rad(315), "orange", "sky"))):
        px, py = tx + 1.12 * math.cos(ang), ty + 1.12 * math.sin(ang)
        # chair faces the table: its +y (back) points away from the table
        chair(f"Chair{i}", (px, py), ang - math.pi / 2, colr, acc)
    fruit_bowl(tx + 0.05, ty - 0.05, 0.775)
    # lamps
    pendant("Lamp_table", tx, ty, 2.05, "magenta", "yellow", size=1.5, watts=90)
    pendant("Lamp_L", -2.3, back_y(-2.3) - 0.9, 2.15, "teal", "white", size=0.9, watts=40)
    pendant("Lamp_R", 1.6, back_y(1.6) - 0.9, 2.25, "orange", "purple", size=0.9, watts=40)
    # clutter
    teapot((-2.05, back_y(-2.05) - DEPTH + 0.28, COUNTER_Z + 0.045), "yellow", "red", scale=1.1)
    utensils(-3.3, back_y(-3.3) - 0.22, COUNTER_Z)
    cups(2.2, back_y(2.2) - 0.35, COUNTER_Z)
    plates(1.55, back_y(1.55) - 0.28, COUNTER_Z)
    plant((-3.7, -2.55))
    clock('right', 1.75, 2.35)
    pot_rail()
