"""An overgrown Maya-style temple: a four-tier stepped pyramid of individual weathered blocks with a
central stairway, a corbel-vaulted shrine and roof comb, a collapsed corner spilling rubble, carved stelae,
a half-buried colossal stone head, and a strangler fig whose roots pour over the tiers.
"""
import math
import random
from mathutils import Vector, Matrix
import helpers as H
from helpers import lerp, fbm, clamp
import materials as M
import terrain as T

R = random.Random(77)
TIER_H = 1.3
TIERS = 4


def block(mb, c, size, rotz=0.0, tilt=(0.0, 0.0), erode=0.035, n=20, e=6.0, chip=True):
    """Weathered stone block: superellipse rings with a chamfer, eroded with noise (c = centre of base)."""
    sx, sy, sz = size
    seed = R.random() * 100
    rot = Matrix.Translation(Vector(c)) @ Matrix.Rotation(rotz, 4, 'Z') @ Matrix.Rotation(tilt[0], 4, 'X') @ \
        Matrix.Rotation(tilt[1], 4, 'Y')
    rows = []
    for t, s in ((0.0, 0.93), (0.07, 1.0), (0.5, 1.0), (0.93, 1.0), (1.0, 0.9)):
        row = []
        for k in range(n):
            th = H.TAU * k / n
            cc, ss = math.cos(th), math.sin(th)
            x = sx / 2 * math.copysign(abs(cc) ** (2 / e), cc) * s
            y = sy / 2 * math.copysign(abs(ss) ** (2 / e), ss) * s
            z = sz * t
            p = Vector((x, y, z))
            d = erode * min(sx, sy, sz) * (fbm(x * 2.5 + seed, y * 2.5, z * 2.5, 3) +
                                           (0.6 * max(0.0, fbm(x * 0.9, y * 0.9 + seed, z * 0.9, 2) - 0.2) if chip else 0))
            q = p - Vector((x, y, (z - sz / 2) * 0.5)).normalized() * d * 1.0
            row.append(mb.vert(rot @ q))
        rows.append(row)
    mb.grid(rows, closed=True, cap0=True, cap1=True)


def course(mb, x0, x1, y, z, h, depth, axis='x', skip=lambda p: False, rubble=None, jitter=0.04, out_sign=1):
    """A course of blocks along a wall line from x0 to x1 (axis x) or y0..y1 (axis y)."""
    p = x0
    while p < x1 - 0.2:
        ln = min(R.uniform(0.75, 1.35), x1 - p)
        cx = p + ln / 2
        loc = Vector((cx, y, z)) if axis == 'x' else Vector((y, cx, z))
        if skip(loc):
            if rubble is not None and R.random() < 0.5:
                rubble.append((loc, (ln, depth, h)))
        elif R.random() > 0.035:
            jo = Vector((R.uniform(-jitter, jitter), R.uniform(-jitter, jitter), 0))
            if axis == 'x':
                jo.y += out_sign * R.uniform(-0.02, 0.06)
                size = (ln - 0.03, depth, h - 0.02)
            else:
                jo.x += out_sign * R.uniform(-0.02, 0.06)
                size = (depth, ln - 0.03, h - 0.02)
            block(mb, loc + jo, size, R.uniform(-0.03, 0.03), (R.uniform(-0.025, 0.025), R.uniform(-0.025, 0.025)))
        p += ln


def pyramid():
    tx, ty = T.TEMPLE
    z0 = T.TEMPLE_Z - 0.35
    mb = H.MB()
    core = H.MB()
    rubble = []
    stair_hw = 1.75

    def collapsed(loc, k):
        lx, ly = loc.x - tx, loc.y - ty
        return k >= 1 and lx > 0.4 and ly < -1.4 and R.random() < 0.55 + 0.15 * k

    for k in range(TIERS):
        hx = 5.6 - 1.15 * k
        hy = 4.7 - 1.0 * k
        zb = z0 + k * TIER_H
        block(core, (tx, ty, zb), (2 * hx - 0.5, 2 * hy - 0.5, TIER_H + 0.02), erode=0.01, n=24, e=8.0, chip=False)
        for row in range(2):
            z = zb + row * TIER_H / 2
            inset = row * 0.06
            h = TIER_H / 2
            # front (+x) and back (-x) walls run along y; sides (+-y) along x
            for sgn in (1, -1):
                course(mb, tx - hx + 0.3, tx + hx - 0.3, ty + sgn * (hy - 0.3 - inset), z, h, 0.6, 'x',
                       skip=lambda p, k=k: collapsed(p, k), rubble=rubble, out_sign=sgn)
                course(mb, ty - hy, ty + hy, tx + sgn * (hx - 0.3 - inset), z, h, 0.6, 'y',
                       skip=(lambda p, k=k: abs(p.y - ty) < stair_hw + 0.1 or collapsed(p, k)) if sgn > 0 else
                       (lambda p, k=k: collapsed(p, k)), rubble=rubble, out_sign=sgn)
        # a projecting cornice band on top of each tier
        course(mb, ty - hy - 0.05, ty + hy + 0.05, tx + hx - 0.15, zb + TIER_H - 0.12, 0.16, 0.5, 'y',
               skip=lambda p, k=k: abs(p.y - ty) < stair_hw + 0.1 or collapsed(p, k))
    top_z = z0 + TIERS * TIER_H
    hx_top = 5.6 - 1.15 * (TIERS - 1)
    # stairway
    n_steps = 16
    x_top = tx + hx_top
    x_bot = tx + 5.6 + 2.3
    rise = (top_z - z0) / n_steps
    run = (x_bot - x_top) / n_steps
    for i in range(n_steps):
        xs = x_bot - (i + 1) * run
        zb = z0 + i * rise
        y = ty - stair_hw
        while y < ty + stair_hw - 0.2:
            w = min(R.uniform(0.8, 1.3), ty + stair_hw - y)
            if not (i in (5, 6, 11) and R.random() < 0.4):
                block(mb, (xs + run / 2 + R.uniform(-0.02, 0.02), y + w / 2, zb - 0.45),
                      (run + 0.12, w - 0.04, rise + 0.45), R.uniform(-0.03, 0.03), (R.uniform(-0.03, 0.03), R.uniform(-0.04, 0.0)))
            y += w
        # alfardas (balustrades) stepping beside the stairs
        for sg in (1, -1):
            block(mb, (xs + run / 2, ty + sg * (stair_hw + 0.3), zb - 0.5), (run + 0.1, 0.6, rise + 0.85), 0.0)
    # fill under the stairs
    for i in range(n_steps):
        xs = x_bot - (i + 1) * run
        block(core, (xs + run / 2, ty, z0 - 0.3), (run + 0.05, 2 * stair_hw + 1.1, (i + 1) * rise + 0.2), erode=0.0, n=12, e=10, chip=False)
    # rubble spilling from the collapsed corner & lost stair blocks
    for loc, size in rubble:
        out = Vector((R.uniform(0.5, 4.5), -R.uniform(1.5, 5.0), 0))
        p = Vector((loc.x, loc.y, 0)) + out
        gz = T.height(p.x, p.y) - 0.1
        s = (size[0] * R.uniform(0.6, 1.0), size[1] * R.uniform(0.6, 1.0), size[2] * R.uniform(0.6, 1.0))
        block(mb, (p.x, p.y, gz), s, R.uniform(0, 3.14), (R.uniform(-0.4, 0.4), R.uniform(-0.4, 0.4)), erode=0.08)
    for k in range(28):
        a = R.uniform(0, H.TAU)
        d = R.uniform(6.5, 11.0)
        p = Vector((tx + math.cos(a) * d * 1.1, ty + math.sin(a) * d * 0.9, 0))
        if abs(p.y - ty) < stair_hw + 1 and p.x > tx:
            continue
        s = (R.uniform(0.6, 1.3), R.uniform(0.4, 0.7), R.uniform(0.35, 0.6))
        block(mb, (p.x, p.y, T.height(p.x, p.y) - 0.15), s, R.uniform(0, 3.14), (R.uniform(-0.3, 0.3), R.uniform(-0.3, 0.3)), erode=0.09)
    mat = M.stone("TempleStone", "#6A665A", "#928C78", "#B2AA92", moss=1.35, scale=1.3)
    mb.build("Temple_Blocks", [mat], "Ruins", smooth=True)
    core.build("Temple_Core", [M.stone("TempleCore", "#4A473E", "#6A6556", "#827C68", moss=1.6, scale=1.0)], "Ruins")
    return Vector((tx, ty, top_z)), hx_top, 3.7 - 1.0 * 0


def shrine(top, hx, hy):
    """Corbel-vaulted shrine with a doorway facing the river and a pierced roof comb."""
    tx, ty, z = top
    mb = H.MB()
    wx, wy = hx - 0.45, 1.3
    th = 0.45
    for c in range(4):
        zc = z + c * 0.55
        for sg in (1, -1):
            course(mb, tx - wx, tx + wx, ty + sg * wy, zc, 0.55, th, 'x', out_sign=sg)
            course(mb, ty - wy + th / 2, ty + wy - th / 2, tx + sg * wx, zc, 0.55, th, 'y',
                   skip=(lambda p: abs(p.y - ty) < 0.55 and p.z < z + 1.6) if sg > 0 else (lambda p: False), out_sign=sg)
    block(mb, (tx + wx, ty, z + 1.65), (0.55, 1.6, 0.55), 0.0)          # lintel
    zr = z + 2.2
    for c in range(4):
        ins = 0.25 * (c + 1)
        for sg in (1, -1):
            course(mb, tx - wx + ins, tx + wx - ins, ty + sg * (wy - ins), zr + c * 0.4, 0.4, 0.5, 'x', out_sign=sg)
            course(mb, ty - wy + ins, ty + wy - ins, tx + sg * (wx - ins), zr + c * 0.4, 0.4, 0.5, 'y', out_sign=sg)
    block(mb, (tx, ty, zr + 1.6), (2 * wx - 0.6, 2 * wy - 0.8, 0.3), 0.0)
    # roof comb: two pierced courses
    for c in range(3):
        y = ty - 1.0
        while y < ty + 1.0:
            if not (c == 1 and int((y - ty) * 3) % 2 == 0):
                block(mb, (tx - 0.3, y + 0.17, zr + 1.9 + c * 0.42), (0.3, 0.3, 0.4), 0.0)
            y += 0.36
    mb.build("Temple_Shrine", [M.stone("ShrineStone", "#5E5A4E", "#8A8470", "#A49C86", moss=1.2, scale=1.6, carved=True)], "Ruins")
    return Vector((tx, ty, zr + 3.2))


def stela(mb, base, h, w, d, rotz, tilt):
    block(mb, base, (d, w, h), rotz, tilt, erode=0.03, n=24, e=5.0)
    block(mb, Vector(base) - Vector((0, 0, 0.3)), (d * 2.2, w * 1.6, 0.4), rotz, (0, 0), erode=0.06)


def colossal_head():
    """Olmec-style head: deformed sphere with brow, broad nose, full lips, ear flaps and a helmet band."""
    hx, hy = T.HEAD
    gz = T.height(hx, hy)
    face = Vector((0.55, -0.83, 0)).normalized()        # looks downstream-right, toward the hero camera
    side = Vector((-face.y, face.x, 0))
    mb = H.MB()
    rows = []
    nr, ns = 40, 64
    for i in range(1, nr):
        ph = math.pi * i / nr
        row = []
        for j in range(ns):
            th = H.TAU * j / ns
            n = Vector((math.sin(ph) * math.cos(th), math.sin(ph) * math.sin(th), math.cos(ph)))
            f, s, u = n.dot(face), n.dot(side), n.z
            r = 1.0
            r *= 1.0 + 0.08 * (1 - abs(u))                    # slightly squarish face
            g = lambda cf, cs, cu, w, a: a * math.exp(-((f - cf) ** 2 + (s - cs) ** 2 + (u - cu) ** 2) / (w * w))
            r += g(0.92, 0.0, -0.02, 0.17, 0.16)               # nose
            r += g(0.9, 0.12, -0.08, 0.1, 0.06) + g(0.9, -0.12, -0.08, 0.1, 0.06)   # nostrils
            r += g(0.85, 0.0, -0.33, 0.2, 0.12)                # lips
            r -= g(0.95, 0.0, -0.33, 0.05, 0.04)               # mouth line
            r += g(0.82, 0.28, 0.22, 0.16, 0.07) + g(0.82, -0.28, 0.22, 0.16, 0.07)  # brow
            r -= g(0.86, 0.26, 0.12, 0.1, 0.07) + g(0.86, -0.26, 0.12, 0.1, 0.07)    # eye sockets
            r += g(0.88, 0.26, 0.1, 0.05, 0.03) + g(0.88, -0.26, 0.1, 0.05, 0.03)    # eyeballs
            r += g(0.7, 0.42, -0.15, 0.2, 0.08) + g(0.7, -0.42, -0.15, 0.2, 0.08)    # cheeks
            r += g(0.0, 0.98, 0.0, 0.22, 0.1) + g(0.0, -0.98, 0.0, 0.22, 0.1)       # ear flaps
            if u > 0.42:                                        # helmet
                r += 0.07 + 0.03 * math.sin(th * 18) * (1 if f > 0.3 else 0.3)
            r += 0.015 * fbm(n.x * 4, n.y * 4, n.z * 4, 3)
            p = Vector((n.x * r * 1.6, n.y * r * 1.6, n.z * r * 1.9))
            row.append(mb.vert(p))
        rows.append(row)
    rows.reverse()
    mb.grid(rows, closed=True, cap0=True, cap1=True)
    ob = mb.build("ColossalHead", [M.stone("HeadStone", "#4E4C44", "#6E6A5E", "#8A8474", moss=1.5, scale=1.2)], "Ruins")
    ob.location = (hx, hy, gz + 0.85)
    ob.rotation_euler = (0.06, -0.08, 0.0)
    return ob


def build():
    top, hx, hy = pyramid()
    roof = shrine(top, hx, hy)
    tx, ty = T.TEMPLE
    mb = H.MB()
    sx = tx + 5.6 + 4.6
    stela(mb, (sx, ty + 3.4, T.height(sx, ty + 3.4) - 0.2), 2.7, 0.95, 0.38, 0.1, (0.0, 0.07))
    stela(mb, (sx + 0.2, ty - 3.6, T.height(sx, ty - 3.6) - 0.2), 2.3, 0.9, 0.36, -0.15, (0.12, -0.05))
    # a toppled stela lying in the ferns
    block(mb, (tx + 4.0, ty - 7.6, T.height(tx + 4.0, ty - 7.6) - 0.05), (2.4, 0.9, 0.35), 0.6, (0.05, 0.04), erode=0.05)
    mb.build("Stelae", [M.stone("StelaStone", "#5E5A4E", "#857F6C", "#A09884", moss=1.1, scale=2.0, carved=True)], "Ruins")
    head = colossal_head()
    return {"top": top, "roof": roof, "head": head.location.copy(), "stair_foot": Vector((tx + 5.6 + 2.3, ty, T.TEMPLE_Z))}
