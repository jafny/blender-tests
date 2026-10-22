"""Terrain: a river valley with a pool and a waterfall dropping off a basalt cliff, water surfaces, boulders, a fallen log.

Layout (metres, +y = upstream / north):
  * the river meanders from the front (y=-30) toward the pool at POOL (y~19)
  * a ~9 m cliff runs across the valley at y~26; the upper river pours over its lip as a waterfall
  * the banks rise gently away from the river so the valley walls fill the background
"""
import math
from mathutils import Vector, Matrix, noise
import helpers as H
from helpers import fbm, smoothstep, clamp, lerp
import materials as M

WATER_Z = 0.0
UPPER_WATER_Z = 8.6
CLIFF_Y = 26.0          # mid-line of the cliff face
CLIFF_H = 9.6
POOL = (0.0, 19.0)
POOL_R = 6.8
X0, X1, Y0, Y1 = -46.0, 46.0, -34.0, 62.0
RES = 0.3


def river_x(y):
    """Centre line of the river."""
    return 2.4 * math.sin(0.11 * y + 0.6) + 1.1 * math.sin(0.27 * y + 1.3) - 1.0


def river_w(y):
    return 3.0 + 0.6 * math.sin(0.19 * y + 2.0)


LIP_X = river_x(CLIFF_Y + 2.0)
TEMPLE = (-14.0, 9.0)   # temple centre; it faces +x (the river)
TEMPLE_Z = 1.15
TEMPLE_HALF = (8.8, 6.6)   # flattened plaza (incl. the stairs)
HEAD = (-9.6, 15.2)
FALL_W = 2.6           # half width of the falls sheet


def cliff_y(x):
    """y of the cliff face midline: pushed back behind the falls into a plunge alcove."""
    alcove = 2.6 * math.exp(-((x - LIP_X) / 4.5) ** 2)
    bowl = -0.012 * (x - LIP_X) ** 2          # the cliff curves toward the viewer on both sides (amphitheatre)
    return CLIFF_Y + alcove + max(bowl, -9.0) + 1.6 * fbm(x * 0.09, 3.3, 0, 3)


def water_dist(x, y):
    """Signed distance to the water edge (negative = in the water), lower river + pool."""
    d_r = abs(x - river_x(y)) - river_w(y)
    d_p = math.hypot((x - POOL[0]) * 0.92, y - POOL[1]) - POOL_R
    d = min(d_r, d_p) if y < CLIFF_Y + 1.0 else d_p
    return d


def upper_dist(x, y):
    return abs(x - river_x(y)) - (2.0 + 0.3 * math.sin(y * 0.3))


def height(x, y):
    n = fbm(x * 0.06, y * 0.06, 0.0, 5)
    base = 0.95 + 0.55 * n + 0.25 * fbm(x * 0.4, y * 0.4, 2.0, 3)
    # lower valley
    d = water_dist(x, y)
    bank = smoothstep(-1.6, 1.4, d)
    h = lerp(-1.25 + 0.15 * fbm(x * 0.5, y * 0.5, 4.0, 2), base, bank)
    # valley walls rising away from the river
    side = abs(x - river_x(y)) - 9.0
    h += 0.018 * max(0.0, side) ** 1.6 * (0.8 + 0.4 * n)
    h += 3.0 * smoothstep(-12.0, -30.0, y) * bank   # banks rise behind the front cameras (frames the view)
    # temple plaza: flatten a rounded rectangle (stairs project toward the river)
    bx = abs(x - (TEMPLE[0] + 1.6)) - TEMPLE_HALF[0]
    by = abs(y - TEMPLE[1]) - TEMPLE_HALF[1]
    bd = math.hypot(max(bx, 0.0), max(by, 0.0)) + min(max(bx, by), 0.0)
    h = lerp(TEMPLE_Z + 0.15 * fbm(x * 0.5, y * 0.5, 3.0, 2), h, smoothstep(0.0, 4.0, bd))
    # cliff: a rocky step up to the upper plateau
    cy = cliff_y(x)
    rough = 0.8 * fbm(x * 0.35, y * 0.35, 7.0, 4)
    c = smoothstep(cy - 1.4, cy + 1.2, y + rough)
    top = CLIFF_H + 0.6 * fbm(x * 0.08, y * 0.08, 9.0, 3) + 0.03 * max(0.0, abs(x - LIP_X) - 8) ** 1.4
    h = lerp(h, top, c)
    # upper river channel carved into the plateau
    if y > cy - 0.2:
        ud = upper_dist(x, y)
        ch = 1.0 - smoothstep(-0.6, 1.2, ud)
        h = lerp(h, UPPER_WATER_Z - 0.9, ch * smoothstep(cy - 0.2, cy + 1.4, y))
    # terraces/ledges on the cliff face
    if 0.05 < c < 0.95:
        h += 0.35 * math.sin(h * 2.2 + fbm(x * 0.3, y * 0.3, 1.0, 2) * 2.0)
    return h


def ground_mesh():
    nx = int((X1 - X0) / RES)
    ny = int((Y1 - Y0) / RES)
    mb = H.MB()
    rows = []
    for j in range(ny + 1):
        y = Y0 + j * RES
        row = []
        for i in range(nx + 1):
            x = X0 + i * RES
            z = height(x, y)
            row.append(mb.vert((x, y, z)))
        rows.append(row)
    mb.grid(rows)
    ob = mb.build("Ground", [M.ground()], "Terrain", smooth=True, recalc=False)
    me = ob.data
    if me.polygons[0].normal.z < 0:
        me.flip_normals()
    # push steep (cliff) vertices around a little so the heightfield reads as broken rock
    for v in me.vertices:
        if v.normal.z < 0.6:
            p = v.co
            k = (0.6 - v.normal.z) * 2.2 * smoothstep(FALL_W + 0.5, FALL_W + 3.0, abs(p.x - LIP_X))
            off = Vector((fbm(p.x * 0.7, p.y * 0.7, p.z * 0.7, 3), fbm(p.x * 0.7 + 5, p.y * 0.7, p.z * 0.7, 3),
                          0.4 * fbm(p.x * 0.7, p.y * 0.7 + 9, p.z * 0.7, 3)))
            v.co = p + off * k
    me.update()
    return ob


def water():
    mat = M.water()
    mb = H.MB()
    # lower water: rectangle covering the valley floor (terrain hides it outside the channel)
    rows = []
    for j in range(2):
        y = lerp(Y0, CLIFF_Y + 3.0, j)
        rows.append([mb.vert((lerp(-16, 16, i / 8), y, WATER_Z)) for i in range(9)])
    mb.grid(rows)
    lower = mb.build("Water_River", [mat], "Water", smooth=True)
    mb = H.MB()
    rows = []
    y0 = cliff_y(LIP_X) + 0.5
    for j in range(41):
        y = lerp(y0, Y1, j / 40)
        rows.append([mb.vert((river_x(y) + lerp(-3.4, 3.4, i / 4), y, UPPER_WATER_Z)) for i in range(5)])
    mb.grid(rows)
    upper = mb.build("Water_Upper", [mat], "Water", smooth=True)
    for ob in (lower, upper):
        ob.visible_shadow = True
    return lower, upper


def _sheet(name, xc, half_w, lip_y, throw, spread, v_off, nu=48, nv=28, z_top=UPPER_WATER_Z - 0.05, wob=0.3):
    """One curtain of falling water: leaves the lip horizontally, accelerates down (parabola) and fans out."""
    mb = H.MB()
    rows = []
    for j in range(nv + 1):
        s = j / nv
        row = []
        for i in range(nu + 1):
            u = i / nu * 2 - 1
            x = xc + u * half_w * (1.0 + spread * s) + wob * math.sin(s * 5 + u * 3 + xc)
            fwd = throw * math.sqrt(s) + 0.15 * fbm(u * 2.0 + xc, s * 3.0, 1.0, 2)
            y = lip_y + 0.4 - fwd - 0.4 * (u * u) * s
            z = z_top - (z_top + 0.3) * s ** 1.15
            if s < 0.06:          # roll over the lip
                y += 0.5 * (0.06 - s) / 0.06
                z = z_top + 0.02
            row.append(mb.vert((x, y, z), luv=(u, s + v_off, xc)))
        rows.append(row)
    mb.grid(rows)
    ob = mb.build(name, [M.falls()], "Water", smooth=True)
    ob.visible_shadow = False
    return ob


def falls():
    """Main curtain of water (two layers for depth) plus thin side strands, foam and spray."""
    lip_y = cliff_y(LIP_X) + 0.6
    ob = _sheet("Waterfall", LIP_X, FALL_W, lip_y, 2.4, 0.35, 0.0)
    _sheet("Waterfall_Front", LIP_X + 0.3, FALL_W * 0.75, lip_y - 0.15, 2.9, 0.5, 0.37, nu=32)
    for k, (dx, w) in enumerate(((-FALL_W - 1.3, 0.35), (FALL_W + 1.0, 0.25), (FALL_W + 2.3, 0.18))):
        x = LIP_X + dx
        ly = cliff_y(x) + 0.6
        for _ in range(10):
            ly += 0.3 if height(x, ly) < UPPER_WATER_Z - 0.4 else -0.3
        _sheet(f"Waterfall_Strand_{k}", x, w, ly - 0.6, 1.0, 1.2, 0.2 * k + 0.1, nu=8, nv=24, z_top=height(x, ly) + 0.05, wob=0.1)
    foot = Vector((LIP_X, lip_y - 2.2, WATER_Z))
    # foam discs on the pool and rapids at the lip
    for name, c, r, sx in (("Foam_Pool", foot + Vector((0, -0.6, 0.02)), 4.2, 1.2),
                           ("Foam_Ring", foot + Vector((0.4, -2.8, 0.015)), 6.5, 1.0),
                           ("Foam_Lip", Vector((LIP_X, lip_y + 1.2, UPPER_WATER_Z + 0.02)), 3.0, 0.9)):
        mb3 = H.MB()
        rows = []
        for k in range(1, 9):
            rr = r * k / 8
            rows.append([mb3.vert((rr * sx * math.cos(H.TAU * a / 48), rr * math.sin(H.TAU * a / 48), 0.0)) for a in range(48)])
        mb3.grid(rows, closed=True)
        ctr = mb3.vert((0, 0, 0))
        for a in range(48):
            mb3.face((ctr, rows[0][a], rows[0][(a + 1) % 48]))
        fo = mb3.build(name, [M.foam()], "Water")
        fo.data.transform(Matrix.Diagonal((1 / r, 1 / r, 1, 1)))   # unit disc: object coords drive the falloff
        fo.location = c
        fo.scale = (r, r, 1)
        fo.visible_shadow = False
    # spray mist (volume) at the foot
    mb4 = H.MB()
    rows = []
    for k in range(1, 12):
        ph = math.pi * k / 12
        rows.append([mb4.vert((math.sin(ph) * math.cos(H.TAU * a / 24), math.sin(ph) * math.sin(H.TAU * a / 24), math.cos(ph))) for a in range(24)])
    mb4.grid(rows, closed=True, cap0=True, cap1=True)
    mi = mb4.build("Spray", [M.mist()], "Water")
    mi.location = foot + Vector((0, -0.5, 0.8))
    mi.scale = (5.0, 4.0, 3.2)
    mi.visible_shadow = False
    return ob, foot


def rock_mesh(seed, size=(1, 1, 1), detail=3, rough=0.35, flat_bottom=True):
    """Displaced UV sphere boulder (normalised to unit size, scaled by `size`)."""
    mb = H.MB()
    rows = []
    nr, ns = 14, 28
    for k in range(1, nr):
        ph = math.pi * k / nr
        row = []
        for a in range(ns):
            th = H.TAU * a / ns
            p = Vector((math.sin(ph) * math.cos(th), math.sin(ph) * math.sin(th), math.cos(ph)))
            d = 1.0 + rough * fbm(p.x * 1.2 + seed, p.y * 1.2, p.z * 1.2, detail)
            # faceted, blocky feel
            d += 0.12 * noise.noise(p * 3.0 + Vector((seed, 0, 0)), noise_basis='VORONOI_F2F1')
            q = Vector((p.x * size[0], p.y * size[1], p.z * size[2])) * d
            if flat_bottom and q.z < -0.2 * size[2]:
                q.z = -0.2 * size[2] + (q.z + 0.2 * size[2]) * 0.3
            row.append(mb.vert(q))
        rows.append(row)
    rows.reverse()
    mb.grid(rows, closed=True, cap0=True, cap1=True)
    return mb


def rocks():
    """Boulders in the river, at the cliff foot and along the banks (each one unique)."""
    mat = M.stone("RiverStone", "#3E3C34", "#625E50", "#7E786A", moss=0.9, wet_z=WATER_Z + 0.15)
    r = H.rng
    placed = []
    # river boulders
    for i, y in enumerate([-14, -9, -6, -2.5, 3, 6.5, 9, 12.5, -18, -22]):
        x = river_x(y) + r.uniform(-1, 1) * river_w(y) * 0.8
        placed.append(((x, y, -0.5), (r.uniform(0.5, 1.4),) * 3))
    # cliff foot / pool rim
    for k in range(18):
        a = r.uniform(-0.4, 1.0) * math.pi
        x = POOL[0] + math.cos(a) * POOL_R * r.uniform(0.9, 1.25)
        y = POOL[1] + math.sin(a) * POOL_R * r.uniform(0.85, 1.2)
        placed.append(((x, y, height(x, y) - 0.4), (r.uniform(0.8, 2.2),) * 3))
    for k in range(10):
        x = LIP_X + r.uniform(-9, 9)
        y = cliff_y(x) - r.uniform(1.2, 2.8)
        if abs(x - LIP_X) < FALL_W + 0.5:
            continue
        placed.append(((x, y, height(x, y) - 0.3), (r.uniform(1.2, 2.6),) * 3))
    # bank stones
    for k in range(26):
        y = r.uniform(-26, 16)
        s = r.choice((-1, 1))
        x = river_x(y) + s * (river_w(y) + r.uniform(0.0, 1.5))
        placed.append(((x, y, height(x, y) - 0.15), (r.uniform(0.3, 0.9),) * 3))
    # outcrops jutting from the cliff face (break up the heightfield wall)
    for k in range(80):
        x = LIP_X + r.uniform(-28, 28)
        if abs(x - LIP_X) < FALL_W + 1.6:
            continue
        z = r.uniform(0.3, CLIFF_H - 0.5)
        y = cliff_y(x)
        for _ in range(12):             # find where the face passes this height
            y += 0.4 if height(x, y) < z else -0.4
        placed.append(((x, y - 0.6, z - 1.2), (r.uniform(1.8, 3.8),) * 3))
    obs = []
    for i, (loc, sc) in enumerate(placed):
        mb = rock_mesh(i * 3.7, (sc[0] * r.uniform(0.8, 1.3), sc[1] * r.uniform(0.7, 1.1), sc[2] * r.uniform(0.45, 0.8)))
        ob = mb.build(f"Boulder_{i:02d}", [mat], "Rocks", subsurf=1)
        ob.location = loc
        ob.rotation_euler = (r.uniform(-0.15, 0.15), r.uniform(-0.15, 0.15), r.uniform(0, H.TAU))
        obs.append(ob)
    return placed


LOG_Y = 4.0


def fallen_log():
    """A mossy fallen trunk bridging the river, roots splayed on the east bank."""
    mat = M.bark("LogBark", "#3A2E22", "#5E5040", "#8E9278", moss=1.4)
    x0, x1 = river_x(LOG_Y) - river_w(LOG_Y) - 3.0, river_x(LOG_Y) + river_w(LOG_Y) + 2.2
    pts = []
    radii = []
    n = 40
    for i in range(n + 1):
        t = i / n
        x = lerp(x0, x1, t)
        y = LOG_Y + 1.2 * math.sin(t * 2.1) - 0.6
        zg = max(height(x, y), WATER_Z - 0.4)
        z = lerp(height(x0, LOG_Y) + 0.35, height(x1, LOG_Y) + 0.6, t) + 0.25 * math.sin(t * math.pi)
        pts.append(Vector((x, y, max(z, zg + 0.3))))
        radii.append(lerp(0.42, 0.62, t))

    def rfn(i, th):
        return 1.0 + 0.06 * math.sin(th * 7 + i * 0.4) + 0.05 * fbm(i * 0.3, th, 0, 2)
    mb = H.MB()
    H.tube(mb, pts, radii, 24, cap0=True, cap1=True, rfn=rfn)
    log = mb.build("FallenLog", [mat], "Rocks", subsurf=1)
    # root plate on the east end
    rmat = M.bark("RootBark", "#3A2C1E", "#5A4A38", "#7E8070", moss=0.8)
    mb = H.MB()
    end = pts[-1]
    for k in range(9):
        a = H.TAU * k / 9 + 0.3
        d = Vector((0.6, math.cos(a), math.sin(a))).normalized()
        rp = H.bezier_pts(end, end + d * 0.9, end + d * 1.8 + Vector((0.4, 0, 0.2)),
                          end + d * 2.6 + Vector((0.6, 0, -0.6 - 0.5 * math.sin(a))), 10)
        H.tube(mb, rp, [lerp(0.2, 0.02, i / 10) for i in range(11)], 7)
    mb.build("FallenLog_Roots", [rmat], "Rocks", subsurf=1)
    return pts, log


def build():
    g = ground_mesh()
    water()
    falls()
    rocks()
    logpts, _ = fallen_log()
    return g, logpts
