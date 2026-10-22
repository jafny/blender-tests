"""Lianas, hanging root curtains on the cliff, a strangler fig gripping the temple, and leafy climbers."""
import math
import random
from mathutils import Vector
import helpers as H
from helpers import lerp, fbm
import materials as M
import terrain as T
import ruins as RU
import plants as P

R = random.Random(303)
UP = Vector((0, 0, 1))


def hang(a, b, sag, n=40, wiggle=0.15, seed=0.0):
    """A sagging rope from a to b (catenary-ish), with some lateral wander."""
    a, b = Vector(a), Vector(b)
    pts = []
    for i in range(n + 1):
        t = i / n
        p = a.lerp(b, t)
        p.z -= sag * 4 * t * (1 - t)
        p += Vector((fbm(t * 3 + seed, 0.3, 0, 2), fbm(t * 3 + seed, 1.7, 0, 2), 0)) * wiggle
        pts.append(p)
    return pts


def leafy(leaves, pts, every=2, size=0.12, pal_rid=None):
    """Small heart-shaped leaves along a vine (philodendron/pothos look)."""
    for i in range(1, len(pts) - 1, every):
        if R.random() < 0.25:
            continue
        p = pts[i]
        d = (pts[i + 1] - pts[i - 1]).normalized()
        a = R.uniform(0, H.TAU)
        side = d.cross(UP)
        if side.length < 1e-3:
            side = Vector((1, 0, 0))
        side.normalize()
        out = (side * math.cos(a) + d.cross(side) * math.sin(a)).normalized()
        ld = (out + Vector((0, 0, -0.6))).normalized()
        L = size * R.uniform(0.7, 1.3)
        H.leaf(leaves, p + out * 0.02, ld, L, L * 0.75, P.heart, nu=5, nv=2, droop=0.4, fold=0.15, lobe=0.2, side_up=UP)


def lianas(kapok_tips, kapok_pts, anchors):
    mb = H.MB()
    leaves = H.MB()
    # from the kapok's limbs down to the ground / into the understory
    for k in range(22):
        p, d = kapok_tips[R.randrange(len(kapok_tips))]
        a = R.uniform(0, H.TAU)
        dist = R.uniform(2, 9)
        g = Vector((p.x + math.cos(a) * dist, p.y + math.sin(a) * dist, 0))
        g.z = T.height(g.x, g.y) - 0.2
        if T.water_dist(g.x, g.y) < 0:
            g.z = R.uniform(0.5, 4.0)          # dangles above the water
        pts = hang(p, g, R.uniform(0.5, 3.0), 50, 0.4, R.random() * 10)
        H.tube(mb, pts, [lerp(0.06, 0.035, i / 50) for i in range(51)], 6)
        if k % 3 == 0:
            leafy(leaves, pts, 2, 0.14)
    # short swags between neighbouring kapok limbs
    for k in range(8):
        p1, _ = kapok_tips[R.randrange(len(kapok_tips))]
        p2 = min((t for t, _ in kapok_tips if 2.0 < (t - p1).length < 7.0), key=lambda t: R.random(), default=None)
        if p2 is None:
            continue
        pts = hang(p1, p2, R.uniform(1.5, 3.5), 40, 0.3, R.random() * 10)
        H.tube(mb, pts, [0.05] * 41, 6)
        leafy(leaves, pts, 2, 0.15)
    # free-hanging strands from canopy anchors (tree crowns around the scene)
    for k, a in enumerate(anchors):
        for j in range(R.randint(1, 3)):
            top = a + Vector((R.uniform(-1.5, 1.5), R.uniform(-1.5, 1.5), 0))
            ln = R.uniform(4, top.z - 0.6)
            bot = top + Vector((R.uniform(-0.6, 0.6), R.uniform(-0.6, 0.6), -ln))
            pts = hang(top, bot, 0.3, 40, 0.2, R.random() * 10)
            H.tube(mb, pts, [lerp(0.035, 0.012, i / 40) for i in range(41)], 5)
            if R.random() < 0.5:
                leafy(leaves, pts, 2, 0.11)
    # a climber spiralling up the kapok bole
    base = kapok_pts[0]
    for j in range(3):
        pts = []
        ph = R.uniform(0, H.TAU)
        for i in range(160):
            t = i / 160
            z = base.z + 1.0 + t * 20
            rr = 1.25 - 0.012 * z + 0.08
            a = ph + t * 6.0 * (1 if j % 2 else -1)
            pts.append(Vector((base.x + math.cos(a) * rr, base.y + math.sin(a) * rr, z)))
        H.tube(mb, pts, [0.05] * 160, 6)
        leafy(leaves, pts, 3, 0.2)
    mb.build("Lianas", [M.liana()], "Vines", smooth=True, recalc=False)
    leaves.build("Liana_Leaves", [M.leaf("vine", "jungle")], "Vines", smooth=True, recalc=False)


def cliff_curtain():
    """Roots and vines spilling over the cliff edge and hanging down the face, with leaves (avoids the falls)."""
    mb = H.MB()
    leaves = H.MB()

    def face_y(x, z, y0):
        """First y (scanning upstream from y0) where the terrain rises above z."""
        y = y0
        for _ in range(60):
            if T.height(x, y) >= z:
                return y
            y += 0.2
        return y

    for k in range(240):
        x = T.LIP_X + R.uniform(-26, 26)
        if abs(x - T.LIP_X) < T.FALL_W + 1.0:
            continue
        y0 = T.cliff_y(x) - 6.0
        top_z = T.height(x, T.cliff_y(x) + 2.5) - 0.3
        ln = R.uniform(2.0, top_z - 0.3)
        pts = []
        for i in range(25):
            t = i / 24
            z = top_z - ln * t
            pts.append(Vector((x + 0.12 * math.sin(t * 6 + k), face_y(x, z, y0) - 0.35 - 0.2 * math.sin(t * math.pi), z)))
        pts.insert(0, pts[0] + Vector((0, 0.8, 0.15)))
        H.tube(mb, pts, [0.03 if k % 4 else 0.05] * len(pts), 5)
        if k % 3 != 2:
            leafy(leaves, pts, 1, 0.2)
    mb.build("CliffRoots", [M.liana()], "Vines", smooth=True, recalc=False)
    leaves.build("CliffRoots_Leaves", [M.leaf("vine", "jungle")], "Vines", smooth=True, recalc=False)


def pyramid_surface(x, y):
    tx, ty = T.TEMPLE
    z0 = T.TEMPLE_Z - 0.35
    z = None
    for k in range(RU.TIERS):
        hx = 5.6 - 1.15 * k
        hy = 4.7 - 1.0 * k
        if abs(x - tx) < hx and abs(y - ty) < hy:
            z = z0 + (k + 1) * RU.TIER_H
    return z if z is not None else T.height(x, y)


def strangler_fig(clusters):
    """A fig that germinated on the temple: braided trunk on the tier-2 ledge, roots poured over the steps."""
    tx, ty = T.TEMPLE
    base = Vector((tx - 1.0, ty - 2.15, 0))
    base.z = pyramid_surface(base.x, base.y)
    mb = H.MB()
    # roots: march outward/downhill following the stepped surface
    for k in range(16):
        a = R.uniform(-math.pi * 0.95, -math.pi * 0.05) if k % 5 else R.uniform(0, H.TAU)
        d = Vector((math.cos(a), math.sin(a), 0))
        p = base + Vector((R.uniform(-0.3, 0.3), R.uniform(-0.3, 0.3), 0.2))
        pts = [p.copy()]
        r0 = R.uniform(0.08, 0.17)
        for i in range(70):
            d = (d + Vector((R.uniform(-0.25, 0.25), R.uniform(-0.25, 0.25), 0))).normalized()
            q = pts[-1] + d * 0.18
            s = pyramid_surface(q.x, q.y)
            if s < pts[-1].z - r0 - 0.05:
                # drop over a tier edge: hug the riser
                pts.append(Vector((q.x, q.y, pts[-1].z)))
                pts.append(Vector((q.x + d.x * 0.05, q.y + d.y * 0.05, s + r0 * 0.7)))
                continue
            q.z = s + r0 * 0.6
            pts.append(q)
            if s <= T.height(q.x, q.y) + 0.05 and i > 20:
                break
        pts.append(pts[-1] + d * 0.4 - Vector((0, 0, 0.4)))
        n = len(pts)
        H.tube(mb, pts, [r0 * lerp(1.0, 0.35, i / n) for i in range(n)], 8)
    # braided trunk
    top = base + Vector((0.4, 0.2, 7.5))
    for j in range(6):
        ph = H.TAU * j / 6
        pts = []
        for i in range(40):
            t = i / 39
            rr = lerp(0.55, 0.15, t)
            a = ph + t * 2.2
            pts.append(base.lerp(top, t) + Vector((math.cos(a) * rr, math.sin(a) * rr, 0)))
        H.tube(mb, pts, [lerp(0.2, 0.1, i / 39) for i in range(40)], 8)
    tips = []
    for k in range(5):
        a = H.TAU * k / 5 + R.uniform(-0.3, 0.3)
        P.branch_tree(mb, top, Vector((math.cos(a), math.sin(a), 0.9)).normalized(), R.uniform(4, 6), 0.2, 2, R, tips)
    mb.build("StranglerFig", [M.bark("FigBark", "#5A5446", "#8A8470", "#A8AA96", moss=0.9, ridge_scale=1.5)], "Ruins")
    items = {i: [] for i in range(len(clusters))}
    for p, d in tips:
        for _ in range(3):
            q = p + Vector((R.uniform(-0.6, 0.6), R.uniform(-0.6, 0.6), R.uniform(-0.2, 0.5)))
            items[R.randrange(len(clusters))].append((q, (R.uniform(-0.3, 0.3), R.uniform(-0.3, 0.3), R.uniform(0, H.TAU)), R.uniform(1.2, 2.0)))
    for i, cl in enumerate(clusters):
        H.instancer(f"FigLeaves_{i}", cl, items[i], "Ruins")
    return top
