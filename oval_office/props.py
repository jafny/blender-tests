"""Furniture and props for the Oval Office."""
import math
import random
from math import radians as rad
import bpy
from mathutils import Vector, Matrix
from helpers import (A, B, H, MB, ell_pt, frame_at, box, cyl, empty, parent, add_bevel, add_subsurf,
                     shade_smooth, cushion, link, TAU)
import lighting

RZ = lambda deg: Matrix.Rotation(rad(deg), 4, 'Z')
RX = lambda deg: Matrix.Rotation(rad(deg), 4, 'X')
RY = lambda deg: Matrix.Rotation(rad(deg), 4, 'Y')
T = lambda x, y, z: Matrix.Translation((x, y, z))


def place(name, loc, rot_deg=0.0):
    return empty(name, T(*loc) @ RZ(rot_deg), "Props")


def annulus(mb, r_in, r_out, z0, z1, n=64, mat=None, cx=0, cy=0, sx=1.0, sy=1.0):
    i = len(mb.v)
    pts = []
    for zz in (z0, z1):
        for r in (r_in, r_out):
            for k in range(n):
                t = TAU * k / n
                p = Vector((cx + r * sx * math.cos(t), cy + r * sy * math.sin(t), zz))
                pts.append(mat @ p if mat is not None else p)
    mb.v.extend(pts)
    # indices: [z][ring][k]
    def idx(zi, ri, k):
        return i + zi * 2 * n + ri * n + (k % n)
    for k in range(n):
        mb.f.append((idx(0, 0, k), idx(0, 0, k + 1), idx(1, 0, k + 1), idx(1, 0, k)))  # inner wall
        mb.f.append((idx(0, 1, k), idx(1, 1, k), idx(1, 1, k + 1), idx(0, 1, k + 1)))  # outer wall
        mb.f.append((idx(1, 0, k), idx(1, 0, k + 1), idx(1, 1, k + 1), idx(1, 1, k)))  # top
        mb.f.append((idx(0, 0, k), idx(0, 1, k), idx(0, 1, k + 1), idx(0, 0, k + 1)))  # bottom


def star(mb, center, r_out, r_in, z0, z1, mat=None):
    cx, cy = center
    pts = []
    for k in range(10):
        r = r_out if k % 2 == 0 else r_in
        t = math.pi / 2 + TAU * k / 10
        pts.append((cx + r * math.cos(t), cy + r * math.sin(t)))
    i = len(mb.v)
    for zz in (z0, z1):
        for x, y in pts:
            p = Vector((x, y, zz))
            mb.v.append(mat @ p if mat is not None else p)
    mb.f.append(tuple(reversed(range(i, i + 10))))
    mb.f.append(tuple(range(i + 10, i + 20)))
    for k in range(10):
        k2 = (k + 1) % 10
        mb.f.append((i + k, i + k2, i + 10 + k2, i + 10 + k))


def eagle(mb, s=1.0, mat=None):
    """Stylised heraldic eagle (wings spread), centred at origin, facing -Y, size ~1.6*s wide."""
    mb.add_sphere((0, 0, 0.05 * s), 0.22 * s, 16, 10, mat, scale=(0.75, 0.5, 1.4))
    mb.add_sphere((0, -0.05 * s, 0.40 * s), 0.09 * s, 14, 8, mat, scale=(1, 1.1, 1))
    mb.add_cyl((0, -0.16 * s, 0.39 * s), 0.035 * s, 0.09 * s, 10, (mat or Matrix.Identity(4)) @ RX(90), r_top=0.005 * s)
    for side in (-1, 1):
        # upper wing arm
        wm = (mat or Matrix.Identity(4)) @ T(side * 0.30 * s, 0, 0.22 * s) @ RY(side * 30)
        mb.add_sphere((0, 0, 0), 0.20 * s, 12, 8, wm, scale=(1.5, 0.35, 0.55))
        # primary feathers fanning up and out
        for k in range(9):
            f = k / 8
            ang = -10 + 95 * f          # from pointing outward to pointing up
            ln = (0.55 - 0.18 * abs(f - 0.35)) * s
            wm = (mat or Matrix.Identity(4)) @ T(side * (0.42 + 0.06 * (1 - f)) * s, 0, (0.10 + 0.08 * f) * s) @ RY(side * (90 - ang))
            mb.add_sphere((0, 0, ln / 2), ln / 2, 8, 6, wm, scale=(0.13, 0.30, 1.0))
    for k in range(7):
        tm = (mat or Matrix.Identity(4)) @ T((k - 3) * 0.045 * s, 0, -0.30 * s) @ RY((k - 3) * 9)
        mb.add_sphere((0, 0, -0.10 * s), 0.16 * s, 8, 6, tm, scale=(0.18, 0.3, 1.0))
    mb.add_box((0, -0.12 * s, 0.0), (0.22 * s, 0.05 * s, 0.28 * s), mat)


# ------------------------------------------------------------------ rug
def build_rug(M):
    mb = MB()
    n = 128
    top = [Vector((3.5 * math.cos(TAU * k / n), 4.5 * math.sin(TAU * k / n), 0.015)) for k in range(n)]
    bot = [Vector((p.x, p.y, 0.0)) for p in top]
    i = len(mb.v)
    mb.v.extend(bot + top)
    mb.f.append(tuple(range(i + n, i + 2 * n)))
    for k in range(n):
        k2 = (k + 1) % n
        mb.f.append((i + k, i + k2, i + n + k2, i + n + k))
    r = mb.build("Rug", M["rug"], "Props")
    # gold eagle relief in the centre of the rug seal
    em = MB()
    eagle(em, 0.9, T(0, 0, 0.02) @ Matrix.Scale(0.06, 4, (0, 0, 1)) @ RX(0))
    e = em.build("RugEagle", M["gold"], "Props", smooth=True)
    e.scale = (1, 1, 0.06)
    return r


# ------------------------------------------------------------------ Resolute desk
def build_desk(M):
    root = place("ResoluteDesk", (0, -3.10, 0), 0)
    W, D, Hh = 1.83, 1.22, 0.79
    body = MB()
    body.add_box((0, 0, 0.04), (W, D, 0.08))                       # plinth
    body.add_box((0, 0, Hh - 0.025), (W + 0.02, D + 0.02, 0.05))   # top
    body.add_box((0, 0, Hh - 0.07), (W + 0.06, D + 0.06, 0.04))    # top edge moulding
    for s in (-1, 1):
        body.add_box((s * (W / 2 - 0.29), 0, 0.42), (0.58, D - 0.04, 0.68))  # pedestals
    body.add_box((0, D / 2 - 0.03, 0.42), (W - 1.16 + 0.02, 0.05, 0.68))     # modesty panel (north/front)
    body.add_box((0, -D / 2 + 0.02, 0.42), (W - 1.16 + 0.02, 0.03, 0.30))   # kneehole rail (south)
    desk = body.build("DeskBody", M["oak_dark"], "Props", bevel=0.006)
    parent(desk, root)
    # raised panel mouldings on sides/front/back, drawer fronts on the president's (south) side
    pm = MB()
    for s in (-1, 1):
        # outer side panels
        x = s * (W / 2 + 0.005)
        for (yc, w) in ((-0.30, 0.48), (0.30, 0.48)):
            pm.add_box((x, yc, 0.42), (0.012, w, 0.52))
            pm.add_box((x, yc, 0.42), (0.02, w - 0.10, 0.42))
        # front (north) pedestal faces: carved panels
        xc = s * (W / 2 - 0.29)
        pm.add_box((xc, D / 2 - 0.013, 0.42), (0.48, 0.012, 0.58))
        pm.add_box((xc, D / 2 - 0.006, 0.42), (0.38, 0.012, 0.48))
        # drawers (south)
        for k in range(3):
            zc = 0.16 + k * 0.215
            pm.add_box((xc, -D / 2 - 0.006, zc), (0.50, 0.012, 0.19))
    panels = pm.build("DeskPanels", M["oak_dark"], "Props", bevel=0.004)
    parent(panels, root)
    hm = MB()
    for s in (-1, 1):
        xc = s * (W / 2 - 0.29)
        for k in range(3):
            zc = 0.16 + k * 0.215
            hm.add_cyl((xc, -D / 2 - 0.03, zc), 0.006, 0.09, 10, RY(90))
            for dx in (-0.045, 0.045):
                hm.add_cyl((xc + dx, -D / 2 - 0.015, zc), 0.006, 0.03, 10, RX(90))
    handles = hm.build("DeskHandles", M["brass"], "Props", smooth=True)
    parent(handles, root)
    # presidential seal carving on the modesty panel
    sm = MB()
    seal_m = T(0, D / 2 + 0.005, 0.44) @ RX(90)
    annulus(sm, 0.20, 0.235, 0.0, 0.02, 48, seal_m)
    annulus(sm, 0.0, 0.20, 0.0, 0.008, 48, seal_m)
    for k in range(20):
        t = TAU * k / 20
        star(sm, (0.215 * math.cos(t), 0.215 * math.sin(t)), 0.012, 0.005, 0.02, 0.028, seal_m)
    eagle(sm, 0.22, seal_m @ T(0, 0, 0.01) @ RX(-90) @ RZ(180))
    seal = sm.build("DeskSeal", M["oak"], "Props", smooth=True)
    parent(seal, root)
    # desk top items
    it = MB()
    it.add_box((-0.55, -0.15, Hh + 0.02), (0.32, 0.45, 0.04))      # leather folder
    it.add_box((0.45, 0.05, Hh + 0.01), (0.22, 0.30, 0.02))        # paper stack (will get paper material below)
    folder = it.build("DeskFolder", M["leather"], "Props", bevel=0.003)
    parent(folder, root)
    pp = MB()
    pp.add_box((0.45, 0.05, Hh + 0.025), (0.215, 0.295, 0.012))
    pp.add_box((-0.05, 0.30, Hh + 0.006), (0.30, 0.21, 0.012))
    papers = pp.build("DeskPapers", M["paper"], "Props")
    parent(papers, root)
    ph = MB()
    ph.add_box((0.62, -0.30, Hh + 0.035), (0.24, 0.20, 0.07))
    ph.add_cyl((0.62, -0.30, Hh + 0.085), 0.025, 0.24, 12, RY(90))
    phone = ph.build("DeskPhone", M["black_metal"], "Props", bevel=0.004)
    parent(phone, root)
    pc = MB()
    pc.add_cyl((-0.70, 0.35, Hh + 0.06), 0.04, 0.12, 20)
    for k in range(4):
        pc.add_cyl((-0.70 + 0.015 * math.cos(k), 0.35 + 0.015 * math.sin(k), Hh + 0.14), 0.004, 0.16, 8,
                   RX(8 * math.cos(k * 2)) @ RY(8 * math.sin(k * 2)))
    pens = pc.build("PenCup", M["brass"], "Props", smooth=True)
    parent(pens, root)
    fm = MB()
    for k, (x, y) in enumerate([(0.15, 0.42), (-0.30, 0.42)]):
        fm.add_box((x, y, Hh + 0.09), (0.16, 0.012, 0.13), T(0, 0, 0) @ RX(-8))
    frames = fm.build("DeskPhotoFrames", M["brass"], "Props", bevel=0.002)
    parent(frames, root)
    pf = MB()
    for k, (x, y) in enumerate([(0.15, 0.42), (-0.30, 0.42)]):
        pf.add_box((x, y - 0.007, Hh + 0.09), (0.13, 0.002, 0.10), RX(-8))
    photos = pf.build("DeskPhotos", M["photo"], "Props")
    parent(photos, root)
    # brass wastebasket
    wb = cyl("Wastebasket", (-1.15, -3.55, 0.16), 0.13, 0.32, M["brass"], r_top=0.15)
    return root


def build_exec_chair(M):
    root = place("PresidentChair", (0, -3.95, 0), 0)
    seat = cushion("ChairSeat", (0, 0, 0.50), (0.56, 0.56, 0.12), M["leather"], "Props")
    parent(seat, root)
    back = cushion("ChairBack", (0, -0.26, 0.92), (0.56, 0.12, 0.78), M["leather"], "Props")
    back.rotation_euler = (rad(-6), 0, 0)
    parent(back, root)
    am = MB()
    for s in (-1, 1):
        am.add_box((s * 0.30, -0.02, 0.68), (0.06, 0.42, 0.04))
        am.add_box((s * 0.30, 0.12, 0.60), (0.04, 0.04, 0.14))
    arms = am.build("ChairArms", M["leather_black"], "Props", bevel=0.004)
    parent(arms, root)
    bm = MB()
    bm.add_cyl((0, 0, 0.30), 0.03, 0.30, 16)
    bm.add_cyl((0, 0, 0.42), 0.18, 0.04, 16)
    for k in range(5):
        t = TAU * k / 5
        bm.add_box((0, 0, 0.04), (0.06, 0.62, 0.03), RZ(math.degrees(t)) @ T(0, 0.15, 0))
        bm.add_sphere((0.30 * math.sin(t), 0.30 * math.cos(t), 0.035), 0.035, 12, 6)
    base = bm.build("ChairBase", M["black_metal"], "Props", smooth=True)
    parent(base, root)
    return root


def build_visitor_chair(M, name, loc, rot):
    root = place(name, loc, rot)
    fm = MB()
    for sx in (-1, 1):
        for sy in (-1, 1):
            fm.add_cyl((sx * 0.22, sy * 0.22, 0.22), 0.02, 0.44, 12, r_top=0.016)
        fm.add_cyl((sx * 0.22, -0.23, 0.72), 0.018, 0.56, 12)     # back posts
    fm.add_box((0, 0, 0.45), (0.50, 0.50, 0.05))                   # seat frame
    fm.add_box((0, -0.23, 0.96), (0.48, 0.03, 0.06))               # top rail
    fm.add_box((0, -0.23, 0.55), (0.44, 0.025, 0.04))              # lower rail
    frame = fm.build(name + "_Frame", M["mahogany"], "Props", bevel=0.003, smooth=True)
    parent(frame, root)
    cane = box(name + "_Cane", (0, -0.235, 0.755), (0.42, 0.008, 0.36), M["walnut"], "Props")
    parent(cane, root)
    seat = cushion(name + "_Seat", (0, 0.01, 0.51), (0.48, 0.48, 0.09), M["armchair"], "Props")
    parent(seat, root)
    return root


# ------------------------------------------------------------------ seating area
def build_sofa(M, name, loc, rot):
    root = place(name, loc, rot)
    L, D = 2.30, 0.88
    base = box(name + "_Base", (0, 0.02, 0.22), (L, D - 0.10, 0.40), M["sofa"], "Props", bevel=0.02)
    parent(base, root)
    back = box(name + "_Back", (0, -D / 2 + 0.10, 0.62), (L, 0.20, 0.62), M["sofa"], "Props", bevel=0.03)
    parent(back, root)
    for k in range(3):
        x = (k - 1) * (L - 0.30) / 3
        c = cushion(name + f"_Seat{k}", (x, 0.06, 0.49), ((L - 0.30) / 3 - 0.02, 0.60, 0.15), M["sofa"], "Props")
        parent(c, root)
        b = cushion(name + f"_BackC{k}", (x, -D / 2 + 0.26, 0.74), ((L - 0.30) / 3 - 0.02, 0.15, 0.46), M["sofa"], "Props")
        b.rotation_euler = (rad(-8), 0, 0)
        parent(b, root)
    for s in (-1, 1):
        arm = cyl(name + f"_Arm{s}", (s * (L / 2 - 0.13), 0.0, 0.60), 0.13, D - 0.10, M["sofa"], mat4=RX(90))
        parent(arm, root)
        ab = box(name + f"_ArmB{s}", (s * (L / 2 - 0.13), 0.0, 0.50), (0.26, D - 0.10, 0.22), M["sofa"], "Props", bevel=0.02)
        parent(ab, root)
        pil = cushion(name + f"_Pillow{s}", (s * (L / 2 - 0.42), -0.10, 0.70), (0.42, 0.13, 0.42), M["drape"], "Props")
        pil.rotation_euler = (rad(-12), 0, rad(s * 12))
        parent(pil, root)
    lm = MB()
    for sx in (-1, 1):
        for sy in (-1, 1):
            lm.add_cyl((sx * (L / 2 - 0.10), sy * (D / 2 - 0.12), 0.02), 0.035, 0.05, 12, r_top=0.03)
    legs = lm.build(name + "_Legs", M["mahogany"], "Props", smooth=True)
    parent(legs, root)
    return root


def build_armchair(M, name, loc, rot):
    root = place(name, loc, rot)
    seat = cushion(name + "_Seat", (0, 0.04, 0.46), (0.62, 0.62, 0.14), M["armchair"], "Props")
    parent(seat, root)
    base = box(name + "_Base", (0, 0.02, 0.28), (0.66, 0.62, 0.22), M["armchair"], "Props", bevel=0.02)
    parent(base, root)
    back = cushion(name + "_Back", (0, -0.30, 0.78), (0.66, 0.18, 0.72), M["armchair"], "Props")
    back.rotation_euler = (rad(-8), 0, 0)
    parent(back, root)
    for s in (-1, 1):
        arm = box(name + f"_Arm{s}", (s * 0.36, -0.04, 0.58), (0.10, 0.54, 0.34), M["armchair"], "Props", bevel=0.03)
        parent(arm, root)
        wing = box(name + f"_Wing{s}", (s * 0.34, -0.26, 0.95), (0.08, 0.26, 0.40), M["armchair"], "Props", bevel=0.02)
        wing.rotation_euler = (0, 0, rad(-s * 20))
        parent(wing, root)
    lm = MB()
    for sx in (-1, 1):
        for sy in (-1, 1):
            lm.add_cyl((sx * 0.28, sy * 0.26, 0.09), 0.03, 0.18, 12, r_top=0.022)
    legs = lm.build(name + "_Legs", M["mahogany"], "Props", smooth=True)
    parent(legs, root)
    return root


def build_table(M, name, loc, size, height, rot=0, mat=None, legs="tapered"):
    mat = mat or M["mahogany"]
    root = place(name, loc, rot)
    w, d = size
    mb = MB()
    mb.add_box((0, 0, height - 0.015), (w, d, 0.03))
    mb.add_box((0, 0, height - 0.07), (w - 0.10, d - 0.10, 0.08))
    for sx in (-1, 1):
        for sy in (-1, 1):
            if legs == "tapered":
                mb.add_box((sx * (w / 2 - 0.06), sy * (d / 2 - 0.06), (height - 0.11) / 2), (0.05, 0.05, height - 0.11))
            else:
                mb.add_cyl((sx * (w / 2 - 0.06), sy * (d / 2 - 0.06), (height - 0.11) / 2), 0.025, height - 0.11, 12, r_top=0.02)
    t = mb.build(name + "_Mesh", mat, "Props", bevel=0.004)
    parent(t, root)
    return root


def build_lamp(M, name, loc, watts=11.0):
    root = place(name, loc, 0)
    mb = MB()
    mb.add_cyl((0, 0, 0.015), 0.11, 0.03, 32)
    mb.add_cyl((0, 0, 0.07), 0.05, 0.08, 24, r_top=0.035)
    mb.add_cyl((0, 0, 0.26), 0.055, 0.30, 24, r_top=0.085)
    mb.add_cyl((0, 0, 0.47), 0.085, 0.12, 24, r_top=0.03)
    mb.add_cyl((0, 0, 0.60), 0.012, 0.16, 12)
    mb.add_sphere((0, 0, 0.94), 0.02, 12, 6)
    base = mb.build(name + "_Body", M["brass"], "Props", smooth=True)
    parent(base, root)
    sm = MB()
    sm.add_cyl((0, 0, 0.78), 0.20, 0.30, 48, r_top=0.15, closed=False)
    shade = sm.build(name + "_Shade", M["shade"], "Props", smooth=True, recalc=False)
    parent(shade, root)
    lt = lighting.point(name + "_Light", (0, 0, 0.78), watts, (1.0, 0.80, 0.58), 0.03)
    parent(lt, root)
    return root


# ------------------------------------------------------------------ flags
def build_flag(M, name, theta, mat, inset=0.55):
    fr = frame_at(theta, inset)
    root = empty(name, fr, "Props")
    pm = MB()
    pm.add_cyl((0, 0, 0.03), 0.17, 0.06, 32, r_top=0.10)
    pm.add_cyl((0, 0, 1.40), 0.018, 2.74, 16)
    pm.add_sphere((0, 0, 2.80), 0.05, 12, 6)
    pole = pm.build(name + "_Pole", M["brass"], "Props", smooth=True)
    parent(pole, root)
    em = MB()
    eagle(em, 0.32, T(0, 0, 2.90) @ RZ(180))
    e = em.build(name + "_Finial", M["gold"], "Props", smooth=True)
    parent(e, root)
    fm = MB()
    # hanging cloth: hoist along the pole at x=0, fly end droops; folds in y
    def cloth(u, v):
        x = 0.03 + u * 0.55
        top = 2.72 - 0.30 * u
        z = top * v + (1.30 - 0.30 * u) * (1 - v)
        y = 0.07 * math.sin(u * math.pi * 6 + v * 2) + 0.03 * math.sin(u * math.pi * 13)
        return (x, y, z)
    fm.add_grid(cloth, 48, 16)
    cl = fm.build(name + "_Cloth", mat, "Props", smooth=True, recalc=False)
    parent(cl, root)
    # gold fringe along the fly & bottom edge
    frm = MB()
    frm.add_box((0.31, 0.0, 1.14), (0.55, 0.16, 0.03))
    fringe = frm.build(name + "_Fringe", M["gold"], "Props")
    parent(fringe, root)
    return root


# ------------------------------------------------------------------ wall items
def build_painting(M, name, matrix, w, h, kind, seed, frame_w=0.07):
    """matrix: wall frame; painting hangs on the -Y side of the wall surface (y=0), centred at local origin."""
    root = empty(name, matrix, "Props")
    fm = MB()
    fw = frame_w
    fm.add_box((0, -0.03, h / 2 + fw / 2), (w + 2 * fw, 0.06, fw))
    fm.add_box((0, -0.03, -h / 2 - fw / 2), (w + 2 * fw, 0.06, fw))
    fm.add_box((-w / 2 - fw / 2, -0.03, 0), (fw, 0.06, h))
    fm.add_box((w / 2 + fw / 2, -0.03, 0), (fw, 0.06, h))
    fm.add_box((0, -0.02, h / 2 + fw * 0.4), (w + 2 * fw + 0.02, 0.075, fw * 0.25))
    fm.add_box((0, -0.02, -h / 2 - fw * 0.4), (w + 2 * fw + 0.02, 0.075, fw * 0.25))
    fr = fm.build(name + "_Frame", M["gold"], "Props", bevel=0.006)
    parent(fr, root)
    cm = MB()
    cm.add_box((0, -0.02, 0), (w, 0.01, h))
    cv = cm.build(name + "_Canvas", __import__("materials").painting(name + "_Paint", kind, seed), "Props")
    parent(cv, root)
    return root


def build_bookcase(M, theta):
    fr = frame_at(theta)
    root = empty(f"Bookcase_{int(math.degrees(theta))}", fr, "Props")
    W, D, Hb = 1.20, 0.38, 2.55
    mb = MB()
    mb.add_box((0, -D / 2, 0.06), (W, D, 0.12))                 # plinth
    mb.add_box((0, -0.02, Hb / 2), (W - 0.06, 0.03, Hb))        # back panel
    for s in (-1, 1):
        mb.add_box((s * (W / 2 - 0.03), -D / 2, Hb / 2), (0.06, D, Hb))
    mb.add_box((0, -D / 2, Hb - 0.03), (W, D, 0.06))
    mb.add_box((0, -D / 2 - 0.02, Hb + 0.05), (W + 0.08, D + 0.06, 0.10))   # cornice
    mb.add_box((0, -D / 2, 0.92), (W, D, 0.04))                 # counter
    mb.add_box((0, -D + 0.01, 0.52), (W - 0.06, 0.03, 0.80))   # cabinet doors below
    for s in (-1, 1):
        mb.add_box((s * (W / 4 - 0.02), -D - 0.006, 0.52), (W / 2 - 0.14, 0.012, 0.66))
    for k in range(1, 5):
        mb.add_box((0, -D / 2, 0.94 + k * 0.38), (W - 0.06, D - 0.06, 0.03))
    case = mb.build("BookcaseBody", M["trim"], "Props", bevel=0.004)
    parent(case, root)
    rnd = random.Random(int(theta * 100))
    bm = MB()
    for k in range(0, 4):
        z0 = 0.955 + k * 0.38
        x = -W / 2 + 0.06
        while x < W / 2 - 0.10:
            bw = rnd.uniform(0.025, 0.05)
            bh = rnd.uniform(0.20, 0.30)
            bd = rnd.uniform(0.14, 0.22)
            bm.add_box((x + bw / 2, -D / 2 - 0.02, z0 + bh / 2), (bw, bd, bh))
            x += bw + 0.002
            if rnd.random() < 0.08:
                x += 0.06
    bk = bm.build("Books", M["books"], "Props")
    # give per-book colour variation: split into separate objects is expensive; use random per-face via object info
    parent(bk, root)
    km = MB()
    for s in (-1, 1):
        km.add_sphere((s * 0.05, -D - 0.02, 0.52), 0.012, 10, 6)
    knobs = km.build("BookcaseKnobs", M["brass"], "Props", smooth=True)
    parent(knobs, root)
    return root


def build_clock(M, theta):
    fr = frame_at(theta, 0.33)
    root = empty("TallClock", fr, "Props")
    mb = MB()
    mb.add_box((0, 0, 0.30), (0.56, 0.32, 0.60))            # base
    mb.add_box((0, 0, 0.62), (0.60, 0.36, 0.04))
    mb.add_box((0, 0, 1.30), (0.44, 0.26, 1.35))            # waist
    mb.add_box((0, 0, 2.00), (0.60, 0.36, 0.04))
    mb.add_box((0, 0, 2.32), (0.56, 0.32, 0.60))            # hood
    mb.add_box((0, 0, 2.64), (0.60, 0.36, 0.05))
    mb.add_box((0, 0, 2.72), (0.30, 0.30, 0.12))            # pediment centre
    body = mb.build("ClockBody", M["mahogany"], "Props", bevel=0.005)
    parent(body, root)
    fm = MB()
    fm.add_cyl((0, -0.165, 2.32), 0.20, 0.01, 40, RX(90))
    face = fm.build("ClockFace", M["paper"], "Props")
    parent(face, root)
    hm = MB()
    hm.add_box((0, -0.175, 2.32 + 0.07), (0.012, 0.004, 0.14))
    hm.add_box((0.05, -0.175, 2.32 + 0.02), (0.10, 0.004, 0.012), RZ(-30))
    hm.add_cyl((0, -0.172, 2.32), 0.015, 0.006, 16, RX(90))
    for s in (-1, 0, 1):
        hm.add_sphere((s * 0.22, 0, 2.70 + (0.12 if s == 0 else 0.02)), 0.035, 12, 6)
        hm.add_cyl((s * 0.22, 0, 2.66 + (0.1 if s == 0 else 0)), 0.012, 0.06, 10)
    hands = hm.build("ClockHands", M["brass"], "Props", smooth=True)
    parent(hands, root)
    gm = MB()
    gm.add_quad((-0.16, -0.131, 0.70), (0.16, -0.131, 0.70), (0.16, -0.131, 1.90), (-0.16, -0.131, 1.90))
    g = gm.build("ClockGlass", M["glass"], "Props", recalc=False)
    parent(g, root)
    pm = MB()
    pm.add_cyl((0, 0, 1.00), 0.09, 0.02, 24, RX(90))
    pm.add_cyl((0, 0, 1.45), 0.006, 0.9, 8)
    pend = pm.build("Pendulum", M["brass"], "Props", smooth=True)
    parent(pend, root)
    return root


def build_bust(M, name, matrix, scale=1.0, mat=None):
    mat = mat or M["marble"]
    root = empty(name, matrix, "Props")
    s = scale
    mb = MB()
    mb.add_box((0, 0, 0.04 * s), (0.28 * s, 0.22 * s, 0.08 * s))                       # plinth
    mb.add_box((0, 0, 0.20 * s), (0.42 * s, 0.24 * s, 0.24 * s))                       # shoulders
    mb.add_cyl((0, 0, 0.36 * s), 0.06 * s, 0.12 * s, 16)
    mb.add_sphere((0, 0, 0.50 * s), 0.11 * s, 20, 12, scale=(0.9, 1.0, 1.15))
    b = mb.build(name + "_Mesh", mat, "Props", smooth=True, bevel=0.01 * s)
    parent(b, root)
    return root


def build_bronze_horse(M, matrix):
    root = empty("BroncoBuster", matrix, "Props")
    mb = MB()
    mb.add_box((0, 0, 0.03), (0.34, 0.22, 0.06))
    hm = T(0, 0, 0.25) @ RX(-35)
    mb.add_sphere((0, 0, 0.14), 0.12, 16, 10, hm, scale=(0.9, 1.6, 0.9))            # body reared
    mb.add_sphere((0, -0.20, 0.36), 0.07, 12, 8, hm, scale=(0.6, 1.2, 0.8))         # neck
    mb.add_sphere((0, -0.30, 0.44), 0.05, 12, 8, hm, scale=(0.6, 1.4, 0.7))         # head
    for s in (-1, 1):
        mb.add_cyl((s * 0.06, 0.12, 0.12), 0.02, 0.28, 10, T(0, 0, 0) @ RX(10))        # hind legs
        mb.add_cyl((s * 0.07, -0.1, 0.42), 0.017, 0.22, 10, hm @ RX(-60))             # forelegs
    mb.add_sphere((0, 0.05, 0.50), 0.06, 12, 8, scale=(0.8, 0.7, 1.6))                 # rider torso
    mb.add_sphere((0, 0.03, 0.66), 0.045, 12, 8)                                        # rider head
    mb.add_cyl((0, 0.03, 0.70), 0.10, 0.012, 16)                                        # hat brim
    h = mb.build("Bronco_Mesh", M["bronze"], "Props", smooth=True)
    parent(h, root)
    return root


def build_plant(M, matrix, fronds=14, size=1.0):
    root = empty("Plant", matrix, "Props")
    pot = cyl("PlantPot", (0, 0, 0.20 * size), 0.20 * size, 0.40 * size, M["brass"], r_top=0.24 * size)
    parent(pot, root)
    soil = cyl("PlantSoil", (0, 0, 0.39 * size), 0.22 * size, 0.01, M["soot"])
    parent(soil, root)
    fm = MB()
    rnd = random.Random(3)
    for k in range(fronds):
        t = TAU * k / fronds + rnd.uniform(-0.2, 0.2)
        tilt = rnd.uniform(25, 60)
        ln = rnd.uniform(0.45, 0.75) * size
        m = T(0, 0, 0.42 * size) @ RZ(math.degrees(t)) @ RX(-tilt) @ T(0, ln / 2, 0)
        fm.add_sphere((0, 0, 0), ln / 2, 10, 6, m, scale=(0.14, 1.0, 0.04))
    fr = fm.build("PlantFronds", M["foliage"], "Props", smooth=True)
    parent(fr, root)
    return root


def build_ivy(M, matrix):
    """Swedish ivy on the mantel: pot plus trailing clumps."""
    root = empty("SwedishIvy", matrix, "Props")
    pot = cyl("IvyPot", (0, 0, 0.07), 0.08, 0.14, M["porcelain"], r_top=0.10)
    parent(pot, root)
    mb = MB()
    rnd = random.Random(11)
    for k in range(22):
        t = TAU * k / 22
        r = rnd.uniform(0.06, 0.16)
        mb.add_sphere((r * math.cos(t), r * math.sin(t), 0.14 + rnd.uniform(-0.02, 0.06) - 0.5 * max(0, r - 0.09)),
                      rnd.uniform(0.035, 0.06), 10, 6)
    for k in range(6):
        t = TAU * k / 6 + 0.3
        for j in range(4):
            mb.add_sphere((0.17 * math.cos(t), 0.17 * math.sin(t), 0.10 - 0.06 * j), 0.035, 8, 5)
    iv = mb.build("IvyLeaves", M["foliage"], "Props", smooth=True)
    parent(iv, root)
    return root


def build_flowers(M, matrix):
    root = empty("Flowers", matrix, "Props")
    vase = cyl("Vase", (0, 0, 0.13), 0.06, 0.26, M["porcelain"], r_top=0.05)
    parent(vase, root)
    mb = MB()
    rnd = random.Random(5)
    for k in range(20):
        t = TAU * k / 20
        r = rnd.uniform(0.02, 0.14)
        mb.add_sphere((r * math.cos(t), r * math.sin(t), 0.34 + rnd.uniform(-0.04, 0.06)), rnd.uniform(0.03, 0.045), 10, 6)
    fl = mb.build("FlowerHeads", __import__("materials").simple("FlowerWhite", (0.95, 0.9, 0.85, 1), 0.6, sheen=0.5), "Props", smooth=True)
    parent(fl, root)
    gm = MB()
    for k in range(14):
        t = TAU * k / 14
        gm.add_sphere((0.13 * math.cos(t), 0.13 * math.sin(t), 0.30), 0.05, 8, 5, scale=(1, 1, 0.5))
    gr = gm.build("FlowerGreens", M["foliage"], "Props", smooth=True)
    parent(gr, root)
    return root


def build_apple_bowl(M, loc):
    root = place("AppleBowl", loc, 0)
    bowl = cyl("Bowl", (0, 0, 0.04), 0.06, 0.08, M["porcelain"], r_top=0.16)
    parent(bowl, root)
    mb = MB()
    rnd = random.Random(2)
    for k in range(7):
        t = TAU * k / 7
        r = 0.08 if k < 6 else 0.0
        mb.add_sphere((r * math.cos(t), r * math.sin(t), 0.09 + (0.05 if k == 6 else 0)), 0.038, 14, 8)
    ap = mb.build("Apples", M["red_apple"], "Props", smooth=True)
    parent(ap, root)
    return root


def build_ceiling_seal(M):
    mb = MB()
    z = H - 0.001
    annulus(mb, 1.36, 1.46, z - 0.07, z, 96)
    annulus(mb, 1.00, 1.07, z - 0.05, z, 96)
    annulus(mb, 0.0, 1.00, z - 0.02, z, 96)
    for k in range(50):
        t = TAU * k / 50
        star(mb, (1.215 * math.cos(t), 1.215 * math.sin(t)), 0.055, 0.022, z - 0.05, z)
    # outer oval band on the ceiling
    n = 240
    for k in range(n):
        t1, t2 = TAU * k / n, TAU * (k + 1) / n
        for (d1, d2, zz) in ((0.95, 1.05, z - 0.03),):
            p1, p2 = ell_pt(t1, d1, zz), ell_pt(t2, d1, zz)
            q1, q2 = ell_pt(t1, d2, zz), ell_pt(t2, d2, zz)
            mb.add_quad(p1, p2, q2, q1)
            mb.add_quad(ell_pt(t1, d1, z), p1, p2, ell_pt(t2, d1, z))
            mb.add_quad(q1, q2, ell_pt(t2, d2, z), ell_pt(t1, d2, z))
    rings = mb.build("CeilingSealRings", M["plaster"], "Props", smooth=False)
    em = MB()
    eagle(em, 1.15, T(0, 0, z - 0.03) @ RX(90) @ RZ(0))
    e = em.build("CeilingEagle", M["plaster"], "Props", smooth=True)
    e.scale = (1, 1, 1)
    return rings


# ------------------------------------------------------------------ assemble
def build(M, info):
    import materials as mat
    build_rug(M)
    build_desk(M)
    build_exec_chair(M)
    build_visitor_chair(M, "VisitorChairW", (-0.95, -2.05, 0), -160)
    build_visitor_chair(M, "VisitorChairE", (0.95, -2.05, 0), 160)
    build_sofa(M, "SofaW", (-1.30, 1.45, 0), -90)
    build_sofa(M, "SofaE", (1.30, 1.45, 0), 90)
    build_table(M, "CoffeeTable", (0, 1.45, 0), (0.75, 1.40), 0.46)
    build_apple_bowl(M, (0, 1.75, 0.46))
    bm = MB()
    bm.add_box((0, 1.15, 0.475), (0.30, 0.22, 0.03))
    bm.add_box((0, 1.15, 0.505), (0.26, 0.19, 0.03))
    bk = bm.build("CoffeeTableBooks", M["books"], "Props", bevel=0.002)
    build_armchair(M, "ArmchairW", (-1.15, 3.55, 0), -160)
    build_armchair(M, "ArmchairE", (1.15, 3.55, 0), 160)
    for s, sfx in ((-1, "W"), (1, "E")):
        build_table(M, f"SideTableS{sfx}", (s * 1.30, 0.05, 0), (0.60, 0.60), 0.64, legs="turned")
        build_lamp(M, f"LampS{sfx}", (s * 1.30, 0.05, 0.64))
        build_table(M, f"SideTableN{sfx}", (s * 1.30, 2.85, 0), (0.60, 0.60), 0.64, legs="turned")
    build_bust(M, "LincolnBust", T(-1.30, 2.85, 0.64), 0.9)
    build_flowers(M, T(1.30, 2.85, 0.64))
    # flags between the windows (US flag on the president's right = east)
    build_flag(M, "USFlag", rad(-90 + 18.5), M["us_flag"])
    build_flag(M, "PresFlag", rad(-90 - 18.5), M["pres_flag"])
    # credenza under the centre window with photos
    build_table(M, "Credenza", (0, -4.78, 0), (1.60, 0.42), 0.76)
    pm = MB()
    fm = MB()
    rnd = random.Random(9)
    for k in range(6):
        x = -0.65 + k * 0.26
        w, h = rnd.uniform(0.12, 0.18), rnd.uniform(0.15, 0.22)
        m = T(x, -4.78 + rnd.uniform(-0.06, 0.06), 0.76 + h / 2) @ RZ(rnd.uniform(-15, 15)) @ RX(-6)
        fm.add_box((0, 0, 0), (w + 0.03, 0.012, h + 0.03), m)
        pm.add_box((0, -0.007, 0), (w, 0.002, h), m)
    fm.build("CredenzaFrames", M["brass"], "Props", bevel=0.002)
    pm.build("CredenzaPhotos", M["photo"], "Props")
    # wall items
    build_painting(M, "WashingtonPortrait", frame_at(rad(90), 0.0, 2.55), 1.05, 1.30, "portrait", 1, 0.09)
    build_painting(M, "PaintingE", frame_at(rad(-26), 0.0, 2.15), 0.95, 1.15, "landscape", 2)
    build_painting(M, "PaintingW", frame_at(rad(-154), 0.0, 2.15), 1.15, 0.90, "landscape", 3)
    build_painting(M, "PaintingNW", frame_at(rad(110), 0.0, 2.35), 0.70, 0.90, "portrait", 4)
    build_painting(M, "PaintingNE", frame_at(rad(70), 0.0, 3.55), 0.70, 0.55, "landscape", 5, 0.05)
    build_painting(M, "PaintingBookE", frame_at(rad(26), 0.0, 3.45), 0.85, 0.65, "landscape", 6, 0.05)
    build_painting(M, "PaintingBookW", frame_at(rad(154), 0.0, 3.45), 0.85, 0.65, "portrait", 7, 0.05)
    build_bookcase(M, rad(26))
    build_bookcase(M, rad(154))
    build_clock(M, rad(70))
    # pedestal tables with sculptures under the east/west paintings
    for th, name in ((rad(-26), "PedE"), (rad(-154), "PedW")):
        fr = frame_at(th, 0.45)
        t = empty(name, fr, "Props")
        mb = MB()
        mb.add_box((0, 0, 0.76), (0.62, 0.42, 0.03))
        mb.add_box((0, 0, 0.70), (0.52, 0.34, 0.09))
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.add_cyl((sx * 0.24, sy * 0.15, 0.33), 0.022, 0.66, 12, r_top=0.018)
        ob = mb.build(name + "_Mesh", M["mahogany"], "Props", bevel=0.003, smooth=True)
        parent(ob, t)
    build_bronze_horse(M, frame_at(rad(-154), 0.45, 0.775))
    build_bust(M, "ChurchillBust", frame_at(rad(-26), 0.45, 0.775), 0.75, M["bronze"])
    build_plant(M, frame_at(rad(110), 0.55), 16, 1.1)
    build_ivy(M, frame_at(rad(90), 0.12, 1.41) @ T(-0.32, 0, 0))
    build_ceiling_seal(M)
