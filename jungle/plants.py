"""Plant library: every asset is generated from a seed so variants differ.

Assets are built at the origin into the excluded "Assets" collection and placed into the scene by
geometry-nodes point instancers (helpers.instancer), so thousands of plants cost almost nothing in memory.

  fern, palm, banana, elephant_ear, bromeliad, heliconia, seedling, sedge, litter_patch,
  leaf_cluster (+ canopy_tree that wears them), kapok (the hero tree, unique, with buttress roots)
"""
import math
import random
from mathutils import Vector, Quaternion, Matrix
import helpers as H
from helpers import lerp, clamp, fbm
import materials as M

UP = Vector((0, 0, 1))
ASSETS = "Assets"


def arc(base, d, length, droop, n, up=UP, curve_pow=1.0, wobble=0.0, seed=0.0):
    """Points along an arching stalk: the heading bends downward (about its side axis) as it goes."""
    side, d, nm = H.basis_from(d, up)
    p = Vector(base)
    out = [(p.copy(), d.copy(), side.copy(), nm.copy())]
    step = length / n
    for i in range(1, n + 1):
        t = i / n
        ang = droop / n * (curve_pow * t ** (curve_pow - 1) if curve_pow != 1 else 1.0)
        q = Quaternion(side, -ang)
        d = (q @ d).normalized()
        nm = (q @ nm).normalized()
        if wobble:
            q2 = Quaternion(nm, wobble * math.sin(t * 7 + seed))
            d = (q2 @ d).normalized()
            side = (q2 @ side).normalized()
        p = p + d * step
        out.append((p.copy(), d.copy(), side.copy(), nm.copy()))
    return out


def lanceolate(u):
    return math.sin(math.pi * clamp(u) ** 0.8) ** 0.9


def ovate(u):
    return math.sin(math.pi * clamp(u) ** 0.65) ** 0.7


def strap(u):
    return clamp((1 - u) * 6.0) ** 0.5 * clamp(u * 12.0) ** 0.5


def heart(u):
    # u in 0..1 over lobe+blade; widest a third of the way in, pointed tip
    return (math.sin(math.pi * clamp(u) ** 0.75) ** 0.6) * (1.0 - 0.15 * u)


def _finish(mb, name, mats):
    ob = mb.build(name, mats, ASSETS, smooth=True, recalc=False)
    return ob


# ------------------------------------------------------------------ ferns
def fern(seed, n_fronds=None, length=None):
    r = random.Random(seed)
    n_fronds = n_fronds or r.randint(12, 18)
    length = length or r.uniform(0.9, 1.6)
    mb = H.MB()
    stem = H.MB()
    for k in range(n_fronds):
        az = H.TAU * k / n_fronds + r.uniform(-0.25, 0.25)
        el = r.uniform(0.6, 1.25)
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        L = length * r.uniform(0.7, 1.1)
        sp = arc(Vector((0, 0, 0.03)), d, L, r.uniform(1.1, 2.0), 44, curve_pow=1.6)
        H.tube(stem, [s[0] for s in sp], [lerp(0.007, 0.002, i / 44) * L for i in range(45)], 4, cap1=False)
        rid = r.random()
        for i in range(3, 45):
            t = i / 44
            p, dd, sd, nm = sp[i]
            pl = L * 0.24 * math.sin(math.pi * min(1.0, t * 1.1)) ** 0.7 * (1.05 - 0.4 * t)
            if pl < 0.01:
                continue
            for sg in (1, -1):
                beta = math.radians(lerp(62, 40, t))
                pd = dd * math.cos(beta) + sd * sg * math.sin(beta)
                H.leaf(mb, p, pd, pl, pl * 0.2, lanceolate, nu=4, nv=1, droop=0.5, fold=0.25, side_up=nm, rid=rid,
                       ripple=0.25)
    mb.merge(stem, mat=1)
    return _finish(mb, f"Fern_{seed}", [M.leaf("fern", "fern"), M.stem("FernStem", "#3C5A1A", "#5E7A2A")])


# ------------------------------------------------------------------ palms
def palm_crown(mb, top, r, n_fronds, frond_len, mat_rachis=1):
    rach = H.MB()
    for k in range(n_fronds):
        az = H.TAU * k / n_fronds * 1.0 + r.uniform(-0.2, 0.2)
        el = r.uniform(-0.25, 0.9) if k % 3 else r.uniform(0.9, 1.3)
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        L = frond_len * r.uniform(0.8, 1.1)
        sp = arc(top, d, L, r.uniform(1.0, 1.9), 40, curve_pow=1.4)
        H.tube(rach, [s[0] for s in sp], [lerp(0.045, 0.006, i / 40) for i in range(41)], 5, cap1=False)
        rid = r.random()
        for i in range(5, 41):
            t = i / 40
            p, dd, sd, nm = sp[i]
            ll = L * 0.22 * math.sin(math.pi * lerp(0.15, 1.0, t)) ** 0.5
            for sg in (1, -1):
                beta = math.radians(lerp(55, 35, t))
                pd = (dd * math.cos(beta) + sd * sg * math.sin(beta) * 0.85 - nm * 0.45).normalized()
                H.leaf(mb, p, pd, ll, ll * 0.09, lanceolate, nu=5, nv=1, droop=0.9, fold=0.45, side_up=nm, rid=rid,
                       twist=0.3 * sg)
    mb.merge(rach, mat=mat_rachis)


def palm(seed, height=None):
    r = random.Random(seed)
    height = height or r.uniform(7.0, 12.0)
    mb = H.MB()
    trunk = H.MB()
    lean = Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0)).normalized() * height * r.uniform(0.08, 0.3)
    p0, p3 = Vector((0, 0, -0.3)), Vector((0, 0, height)) + lean
    pts = H.bezier_pts(p0, p0 + Vector((0, 0, height * 0.4)), p3 - lean * 0.3 - Vector((0, 0, height * 0.25)), p3, 40)
    radii = [lerp(0.24, 0.14, (i / 40) ** 0.6) + 0.12 * max(0.0, 0.08 - i / 40) * 10 for i in range(41)]

    def rings(i, th):
        return 1.0 + 0.05 * math.sin(i * 2.6) ** 8 + 0.015 * math.sin(th * 9 + i)
    H.tube(trunk, pts, radii, 14, cap0=True, cap1=True, rfn=rings)
    top = pts[-1]
    # crownshaft bulge + coconut cluster
    sh = H.MB()
    H.tube(sh, [top + Vector((0, 0, z)) for z in (-0.6, -0.2, 0.2, 0.45)], [0.16, 0.2, 0.16, 0.06], 12)
    nuts = H.MB()
    for k in range(r.randint(3, 7)):
        a = r.uniform(0, H.TAU)
        c = top + Vector((math.cos(a) * 0.24, math.sin(a) * 0.24, r.uniform(-0.45, -0.1)))
        rows = []
        for j in range(1, 8):
            ph = math.pi * j / 8
            rows.append([nuts.vert(c + Vector((math.sin(ph) * math.cos(H.TAU * q / 10) * 0.13,
                                               math.sin(ph) * math.sin(H.TAU * q / 10) * 0.13, math.cos(ph) * 0.15)))
                         for q in range(10)])
        nuts.grid(rows, closed=True, cap0=True, cap1=True)
    palm_crown(mb, top + Vector((0, 0, 0.35)), r, r.randint(12, 16), r.uniform(3.2, 4.4), mat_rachis=1)
    mb.merge(trunk, mat=2)
    mb.merge(sh, mat=1)
    mb.merge(nuts, mat=3)
    return _finish(mb, f"Palm_{seed}", [M.leaf("palm", "palm"), M.stem("PalmRachis", "#5A6E2A", "#8A9A44"),
                                        M.palm_trunk(), M.flat("Coconut", M.col("#5A6A22"), 0.4, coat=0.3)])


# ------------------------------------------------------------------ bananas & heliconias
def banana(seed, height=None, fruit=False):
    r = random.Random(seed)
    height = height or r.uniform(2.0, 3.2)
    mb = H.MB()
    st = H.MB()
    lean = Vector((r.uniform(-0.2, 0.2), r.uniform(-0.2, 0.2), 1)).normalized()
    pts = [lean * height * i / 10 for i in range(11)]
    H.tube(st, pts, [lerp(0.2, 0.12, i / 10) for i in range(11)], 14, cap0=True)
    n = r.randint(6, 9)
    for k in range(n):
        az = k * 2.4 + r.uniform(-0.3, 0.3)
        el = r.uniform(0.5, 1.3)
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        base = pts[-1] - lean * r.uniform(0.0, 0.5)
        pet = arc(base, d, 0.45, 0.2, 4)
        H.tube(st, [s[0] for s in pet], [0.03, 0.028, 0.025, 0.022, 0.02], 6)
        L = r.uniform(1.8, 2.6)
        tears = sorted(r.uniform(0.15, 0.95) for _ in range(r.randint(2, 9)))
        old = k < 2 and r.random() < 0.6
        H.leaf(mb, pet[-1][0], pet[-1][1], L, L * 0.36, lambda u: clamp(math.sin(math.pi * u) ** 0.35 * 1.05),
               nu=26, nv=3, droop=r.uniform(0.7, 1.5) + (1.2 if old else 0), fold=0.12, curl=-0.15,
               side_up=pet[-1][3], tears=tears, wave=0.04, ripple=0.03)
    mats = [M.leaf("banana", "banana", gloss=0.25), M.stem("BananaStem", "#5E7A2E", "#8EA448")]
    if fruit:
        # hanging bunch + purple bud
        fr = H.MB()
        top = pts[-1]
        sp = arc(top, Vector((0.6, 0, 0.3)), 1.4, 2.6, 16)
        H.tube(st, [s[0] for s in sp], [0.035] * 17, 6)
        for i in range(3, 10):
            p, dd, sd, nm = sp[i]
            for k in range(8):
                a = H.TAU * k / 8
                o = sd * math.cos(a) + nm * math.sin(a)
                bp = arc(p + o * 0.06, (o + UP * 0.8).normalized(), 0.18, 0.6, 5)
                H.tube(fr, [s[0] for s in bp], [0.018, 0.022, 0.024, 0.022, 0.016, 0.006], 6)
        bud = sp[-1][0]
        rows = []
        for j in range(1, 10):
            ph = math.pi * j / 10
            rr = 0.09 * math.sin(ph) * (1.4 - j / 10)
            rows.append([fr.vert(bud + Vector((math.cos(H.TAU * q / 12) * rr, math.sin(H.TAU * q / 12) * rr,
                                               math.cos(ph) * 0.2 - 0.12))) for q in range(12)])
        fr.grid(rows, closed=True, cap0=True, cap1=True)
        mb.merge(fr, mat=2)
        mats.append(M.flat("BananaFruit", M.col("#7A9A2A"), 0.45, coat=0.2))
    mb.merge(st, mat=1)
    return _finish(mb, f"Banana_{seed}", mats)


def heliconia(seed):
    r = random.Random(seed)
    mb = H.MB()
    st = H.MB()
    br = H.MB()
    for k in range(r.randint(3, 5)):
        az = r.uniform(0, H.TAU)
        h = r.uniform(1.2, 2.0)
        base = Vector((math.cos(az) * 0.15, math.sin(az) * 0.15, 0))
        top = base + Vector((r.uniform(-0.2, 0.2), r.uniform(-0.2, 0.2), h))
        H.tube(st, [base.lerp(top, i / 6) for i in range(7)], [0.022 - 0.002 * i for i in range(7)], 6)
        for j in range(r.randint(2, 3)):
            a2 = az + j * 2.6 + r.uniform(-0.3, 0.3)
            d = Vector((math.cos(a2), math.sin(a2), r.uniform(0.9, 1.8))).normalized()
            H.leaf(mb, base.lerp(top, r.uniform(0.45, 0.9)), d, r.uniform(0.9, 1.3), 0.32,
                   lambda u: math.sin(math.pi * u) ** 0.5, nu=14, nv=2, droop=r.uniform(0.6, 1.4), fold=0.15, side_up=UP)
        if k == 0 or r.random() < 0.5:
            # lobster-claw inflorescence: alternating boat-shaped bracts on a zig-zag rachis
            p = top + Vector((0, 0, 0.05))
            dirn = Vector((math.cos(az + 2), math.sin(az + 2), 0.0))
            sp = arc(p, (dirn * 0.3 + UP).normalized(), 0.55, -0.2, 8)
            H.tube(st, [s[0] for s in sp], [0.012] * 9, 5)
            for i in range(1, 9):
                q, dd, sd, nm = sp[i]
                sg = 1 if i % 2 else -1
                bd = (sd * sg * 0.9 + UP * 0.6).normalized()
                H.leaf(br, q, bd, 0.17 * (1.1 - i / 12), 0.05, lambda u: math.sin(math.pi * u ** 0.7) ** 0.5,
                       nu=6, nv=2, droop=-0.6, fold=0.9, curl=0.6, side_up=UP)
    mb.merge(st, mat=1)
    mb.merge(br, mat=2)
    return _finish(mb, f"Heliconia_{seed}", [M.leaf("banana", "banana", gloss=0.25), M.stem("HeliStem", "#4E6E22", "#6E8E32"),
                                             M.bract()])


# ------------------------------------------------------------------ understory
def elephant_ear(seed):
    r = random.Random(seed)
    mb = H.MB()
    st = H.MB()
    nl = r.randint(5, 8)
    for k in range(nl):
        az = H.TAU * k / nl + r.uniform(-0.3, 0.3)
        el = r.uniform(1.05, 1.4)
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        L = r.uniform(0.8, 1.5)
        sp = arc(Vector((0, 0, 0)), d, L, r.uniform(0.4, 0.9), 10)
        H.tube(st, [s[0] for s in sp], [lerp(0.03, 0.014, i / 10) for i in range(11)], 6)
        tip, dd, sd, nm = sp[-1]
        bd = Vector((math.cos(az), math.sin(az), -r.uniform(0.5, 1.1))).normalized()
        ll = r.uniform(0.7, 1.1)
        H.leaf(mb, tip, bd, ll, ll * 0.85, heart, nu=14, nv=4, droop=0.35, fold=0.18, curl=-0.1, lobe=0.3,
               side_up=UP, wave=0.02)
    mb.merge(st, mat=1)
    return _finish(mb, f"ElephantEar_{seed}", [M.leaf("elephant", "elephant", gloss=0.2), M.stem("EarStem", "#4A6A26", "#6C8A3A")])


def bromeliad(seed, size=None):
    r = random.Random(seed)
    size = size or r.uniform(0.3, 0.55)
    mb = H.MB()
    n = r.randint(16, 24)
    for k in range(n):
        az = k * 2.39996 + r.uniform(-0.1, 0.1)
        layer = k / n
        el = lerp(1.35, 0.35, layer)
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        L = size * lerp(0.6, 1.0, layer) * r.uniform(0.85, 1.1)
        H.leaf(mb, Vector((math.cos(az), math.sin(az), 0)) * 0.02, d, L, L * 0.18, strap, nu=10, nv=3,
               droop=r.uniform(0.8, 1.6), fold=0.3, curl=0.35, side_up=UP, rid=r.random())
    spike = H.MB()
    if r.random() < 0.7:
        sp = arc(Vector((0, 0, 0)), Vector((0.05, 0, 1)), size * 0.7, 0.1, 6)
        H.tube(spike, [s[0] for s in sp], [0.012 * (1 - i / 8) for i in range(7)], 5)
        for i in range(1, 7):
            q, dd, sd, nm = sp[i]
            a = i * 2.2
            H.leaf(spike, q, (sd * math.cos(a) + nm * math.sin(a) + UP * 0.8).normalized(), size * 0.18 * (1.2 - i / 8),
                   size * 0.05, lanceolate, nu=4, nv=1, droop=-0.2, fold=0.6, side_up=UP)
    mb.merge(spike, mat=1)
    return _finish(mb, f"Bromeliad_{seed}", [M.leaf("brom", "brom", red_base=True, gloss=0.2), M.bract()])


def seedling(seed):
    r = random.Random(seed)
    mb = H.MB()
    st = H.MB()
    h = r.uniform(0.15, 0.6)
    lean = Vector((r.uniform(-0.2, 0.2), r.uniform(-0.2, 0.2), 1)).normalized()
    pts = [lean * h * i / 6 for i in range(7)]
    H.tube(st, pts, [0.006] * 7, 4)
    for k in range(r.randint(3, 8)):
        t = r.uniform(0.3, 1.0)
        az = k * 2.4
        d = Vector((math.cos(az), math.sin(az), r.uniform(0.0, 0.6))).normalized()
        L = r.uniform(0.08, 0.22)
        H.leaf(mb, lean * h * t, d, L, L * r.uniform(0.35, 0.55), ovate, nu=6, nv=2, droop=0.6, fold=0.2, side_up=UP)
    mb.merge(st, mat=1)
    return _finish(mb, f"Seedling_{seed}", [M.leaf("seedling", "seedling"), M.stem("SeedStem", "#4E6E22", "#7A9A3A")])


def sedge(seed):
    r = random.Random(seed)
    mb = H.MB()
    for k in range(r.randint(25, 45)):
        az = r.uniform(0, H.TAU)
        el = r.uniform(0.9, 1.45)
        d = Vector((math.cos(az) * math.cos(el), math.sin(az) * math.cos(el), math.sin(el)))
        L = r.uniform(0.35, 0.9)
        H.leaf(mb, Vector((math.cos(az), math.sin(az), 0)) * 0.03, d, L, 0.016, strap, nu=8, nv=1,
               droop=r.uniform(0.6, 2.0), fold=0.4, side_up=UP)
    return _finish(mb, f"Sedge_{seed}", [M.leaf("seedling", "seedling")])


def litter_patch(seed, size=1.6, n=70):
    """A patch of fallen leaves lying (slightly curled) on the ground."""
    r = random.Random(seed)
    mb = H.MB()
    for k in range(n):
        x, y = r.uniform(-size / 2, size / 2), r.uniform(-size / 2, size / 2)
        az = r.uniform(0, H.TAU)
        L = r.uniform(0.07, 0.2)
        d = Vector((math.cos(az), math.sin(az), r.uniform(-0.05, 0.12))).normalized()
        H.leaf(mb, Vector((x, y, 0.012 + r.uniform(0, 0.02))), d, L, L * r.uniform(0.3, 0.55), ovate, nu=7, nv=2,
               droop=r.uniform(-0.3, 0.2), fold=r.uniform(-0.15, 0.2), curl=r.uniform(0, 0.3), side_up=UP)
    return _finish(mb, f"Litter_{seed}", [M.leaf("litter", "litter", gloss=0.5)])


# ------------------------------------------------------------------ trees
def leaf_cluster(seed, pal="canopy", size=1.0, n=None):
    """A leafy twig spray: leaves spiral around a short arching twig, pointing outward/down."""
    r = random.Random(seed)
    mb = H.MB()
    tw = H.MB()
    n = n or r.randint(40, 60)
    for b in range(4):
        d = Vector((r.uniform(-1, 1), r.uniform(-1, 1), r.uniform(0.2, 1.0))).normalized()
        sp = arc(Vector((0, 0, 0)), d, size * r.uniform(0.6, 1.0), r.uniform(0.3, 0.9), 8)
        H.tube(tw, [s[0] for s in sp], [0.012 * size] * 9, 4)
        for k in range(n // 3):
            t = r.uniform(0.15, 1.0)
            i = int(t * 8)
            p, dd, sd, nm = sp[i]
            a = k * 2.4
            ld = (dd * 0.6 + sd * math.cos(a) + nm * math.sin(a) * 0.6 + UP * 0.35).normalized()
            L = size * r.uniform(0.2, 0.34)
            H.leaf(mb, p, ld, L, L * r.uniform(0.35, 0.5), ovate, nu=5, nv=1, droop=r.uniform(0.3, 0.9), fold=0.25,
                   side_up=UP, rid=r.random())
    mb.merge(tw, mat=1)
    return _finish(mb, f"Cluster_{pal}_{seed}", [M.leaf(pal, pal), M.bark("TwigBark", "#3E3428", "#5E5442", moss=0.0)])


def branch_tree(mb, root, d, length, radius, depth, r, tips, kind="canopy"):
    """Recursive branches as tubes; leaf-cluster anchor points collected into tips."""
    n = max(4, int(length * 1.5))
    sp = arc(root, d, length, r.uniform(-0.25, 0.35), n, wobble=0.12, seed=r.random() * 9)
    pts = [s[0] for s in sp]
    radii = [radius * lerp(1.0, 0.45, i / n) for i in range(n + 1)]
    H.tube(mb, pts, radii, max(5, int(10 * min(1.0, radius * 4) + 4)), cap1=True)
    if depth == 0 or length < 1.0:
        for i in range(max(1, n // 2), n + 1):
            tips.append((pts[i], sp[i][1]))
        return
    for k in range(r.randint(2, 3)):
        t = r.uniform(0.45, 0.95)
        i = int(t * n)
        p, dd, sd, nm = sp[i]
        a = r.uniform(0, H.TAU)
        nd = (dd * 0.7 + (sd * math.cos(a) + nm * math.sin(a)) * 0.7 + UP * 0.35).normalized()
        branch_tree(mb, p, nd, length * r.uniform(0.5, 0.7), radii[i] * 0.7, depth - 1, r, tips, kind)
    tips.append((pts[-1], sp[-1][1]))


def canopy_tree(seed, height=None, clusters=None, pal="canopy", bark=None):
    """A rainforest emergent/canopy tree: tall clean bole, root flare, a spreading crown of leaf sprays.

    Returns a collection (trunk mesh + cluster instancers) to instance as a unit."""
    import bpy
    r = random.Random(seed)
    height = height or r.uniform(16, 26)
    cname = f"Tree_{seed}"
    c = H.coll(cname, H.coll(ASSETS))
    mb = H.MB()
    lean = Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0)) * height * 0.04
    bole_h = height * r.uniform(0.55, 0.7)
    R = 0.18 + height * 0.022
    pts = H.bezier_pts(Vector((0, 0, -0.5)), Vector((0, 0, bole_h * 0.3)), Vector((0, 0, bole_h * 0.7)) + lean * 0.5,
                       Vector((0, 0, bole_h)) + lean, 24)
    fins = r.randint(3, 6)
    ph = r.uniform(0, H.TAU)

    def flare(i, th):
        z = pts[i].z
        f = max(0.0, 1.0 - z / 2.2) ** 2
        fin = max(0.0, math.cos(fins * (th + ph))) ** 6
        return 1.0 + f * (0.6 + 1.6 * fin) + 0.03 * math.sin(th * 13 + i)
    radii = [R * lerp(1.0, 0.65, i / 24) for i in range(25)]
    H.tube(mb, pts, radii, 28, cap0=True, rfn=flare)
    tips = []
    top = pts[-1]
    for k in range(r.randint(4, 6)):
        a = H.TAU * k / 5 + r.uniform(-0.4, 0.4)
        d = Vector((math.cos(a), math.sin(a), r.uniform(0.6, 1.3))).normalized()
        start = top - Vector((0, 0, r.uniform(0, bole_h * 0.12)))
        branch_tree(mb, start, d, (height - bole_h) * r.uniform(0.9, 1.3), radii[-1] * 0.7, 2, r, tips)
    trunk = mb.build(f"TreeTrunk_{seed}", [bark or M.bark()], cname, smooth=True, recalc=True)
    # leaf sprays at tips (several cluster variants)
    clusters = clusters or []
    items = {i: [] for i in range(len(clusters))}
    for p, d in tips:
        for _ in range(3):
            q = p + Vector((r.uniform(-0.8, 0.8), r.uniform(-0.8, 0.8), r.uniform(-0.3, 0.6)))
            rot = (r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3), r.uniform(0, H.TAU))
            s = r.uniform(1.4, 2.4)
            items[r.randrange(len(clusters))].append((q, rot, s))
    for i, cl in enumerate(clusters):
        H.instancer(f"TreeLeaves_{seed}_{i}", cl, items[i], cname)
    return c


def kapok(loc, height=34.0, clusters=(), epiphytes=()):
    """The hero ceiba: huge plank buttresses, a straight pale bole and broad horizontal limbs."""
    r = random.Random(4242)
    mb = H.MB()
    base = Vector(loc)
    pts = [base + Vector((0.15 * math.sin(i * 0.4), 0.1 * math.cos(i * 0.3), z)) for i, z in
           enumerate([-1.0, -0.3, 0.3, 0.9, 1.6, 2.4, 3.3, 4.4, 5.6, 7.0, 8.6, 10.5, 12.6, 15, 17.5, 20, 22.5, 25, 27])]
    fins = [(a, r.uniform(2.6, 4.6)) for a in (0.2, 1.25, 2.1, 3.0, 3.9, 4.75, 5.6)]

    def buttress(i, th):
        z = pts[i].z - base.z
        val = 1.0
        for a, ln in fins:
            dth = math.atan2(math.sin(th - a), math.cos(th - a))
            hz = max(0.0, 1.0 - z / (ln * 1.6)) ** 1.5
            wid = 0.07 + 0.08 * (1 - hz)
            val += hz * ln / 0.85 * math.exp(-(dth / wid) ** 2)
        return val + 0.04 * fbm(th * 2, z * 0.3, 0, 2)
    radii = [1.15 - 0.012 * (p.z - base.z) for p in pts]
    H.tube(mb, pts, radii, 180, cap0=True, rfn=buttress)
    tips = []
    top = pts[-1]
    # tiered horizontal limbs (the ceiba's umbrella crown)
    for k in range(7):
        a = H.TAU * k / 7 + r.uniform(-0.3, 0.3)
        z = top.z - r.uniform(0, 7)
        start = base + Vector((0, 0, z - base.z))
        d = Vector((math.cos(a), math.sin(a), r.uniform(0.25, 0.6))).normalized()
        branch_tree(mb, start, d, r.uniform(9, 13), 0.55, 2, r, tips)
    ob = mb.build("Kapok", [M.bark("KapokBark", "#3E3A30", "#6A6454", "#8E8E7A", moss=1.3, ridge_scale=0.8)],
                  "Trees", smooth=True, recalc=True)
    items = {i: [] for i in range(len(clusters))}
    for p, d in tips:
        for _ in range(4):
            q = p + Vector((r.uniform(-1.0, 1.0), r.uniform(-1.0, 1.0), r.uniform(-0.3, 0.8)))
            items[r.randrange(len(clusters))].append((q, (r.uniform(-0.3, 0.3), r.uniform(-0.3, 0.3), r.uniform(0, H.TAU)),
                                                      r.uniform(1.6, 2.6)))
    for i, cl in enumerate(clusters):
        H.instancer(f"KapokLeaves_{i}", cl, items[i], "Trees")
    # epiphytes sitting in the forks and on the buttress tops
    ep = []
    for k in range(26):
        if k < 10:
            a = fins[k % len(fins)][0] + r.uniform(-0.05, 0.05)
            z = r.uniform(2.0, 5.0)
            rr = radii[0] * buttress(min(len(pts) - 1, int(z * 1.0) + 2), a) * 0.5 + 0.2
            p = base + Vector((math.cos(a) * rr, math.sin(a) * rr, z))
        else:
            p, d = tips[r.randrange(len(tips))] if r.random() < 0.3 else (top - Vector((0, 0, r.uniform(0, 12))), None)
            if d is None:
                a = r.uniform(0, H.TAU)
                p = Vector((base.x + math.cos(a) * 1.1, base.y + math.sin(a) * 1.1, p.z))
        ep.append((p, (0, 0, r.uniform(0, H.TAU)), r.uniform(0.8, 1.6)))
    for i, e in enumerate(epiphytes):
        H.instancer(f"KapokEpiphytes_{i}", e, ep[i::len(epiphytes)], "Trees")
    return ob, pts, tips
