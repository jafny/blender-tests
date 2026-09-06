"""Geometry helpers for the Dr. Seuss kitchen generator (bpy 4.2).

Everything Seussian is built from a handful of tools:
  * loft()       - connect a list of rings (each a list of Vectors) into a closed mesh
  * sring()      - superellipse ring with wobble, so cabinets/fridges/pots can bulge, lean and taper
  * blob()       - a "box" lofted from superellipse rings + subsurf -> pillowy, rounded, leaning
  * lathe()      - surface of revolution from an (r, z) profile with optional wobble
  * slab()       - a wavy outline extruded between two heights (countertops, shelves, table tops)
  * tube()       - a NURBS curve with bevel and per-point radius (faucets, curls, wires, pipes)
"""
import math
import random
import bpy
import bmesh
from mathutils import Vector, Matrix

TAU = math.tau
rng = random.Random(7)

_collections = {}


def coll(name):
    if name in _collections:
        return _collections[name]
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    _collections[name] = c
    return c


def link(ob, collection="Scene"):
    coll(collection).objects.link(ob)
    return ob


def empty(name, loc=(0, 0, 0), collection="Scene"):
    ob = bpy.data.objects.new(name, None)
    ob.location = loc
    link(ob, collection)
    return ob


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def interp(keys, t):
    """Piecewise-linear interpolation of [(t, value), ...] (sorted by t)."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return lerp(v0, v1, (t - t0) / (t1 - t0) if t1 > t0 else 0.0)
    return keys[-1][1]


# ------------------------------------------------------------------ rings
def sring(cx, cy, z, a, b, e=2.5, n=48, rot=0.0, wob=0.0, wob_freq=3, phase=0.0, zfn=None):
    """Superellipse ring. e=2 circle/ellipse, e>2 rounded rectangle. wob = radial wobble amplitude."""
    pts = []
    for k in range(n):
        t = TAU * k / n
        c, s = math.cos(t), math.sin(t)
        x = a * math.copysign(abs(c) ** (2.0 / e), c)
        y = b * math.copysign(abs(s) ** (2.0 / e), s)
        w = 1.0 + wob * math.sin(wob_freq * t + phase)
        x *= w
        y *= w
        xr = x * math.cos(rot) - y * math.sin(rot)
        yr = x * math.sin(rot) + y * math.cos(rot)
        zz = z if zfn is None else z + zfn(t, cx + xr, cy + yr)
        pts.append(Vector((cx + xr, cy + yr, zz)))
    return pts


def cring(cx, cy, z, r, n=48, wob=0.0, wob_freq=3, phase=0.0):
    return sring(cx, cy, z, r, r, 2.0, n, 0.0, wob, wob_freq, phase)


def transform_pts(pts, mat):
    return [mat @ p for p in pts]


# ------------------------------------------------------------------ mesh builder
class MB:
    def __init__(self):
        self.v = []
        self.f = []

    def add_poly(self, pts):
        i = len(self.v)
        self.v.extend([Vector(p) for p in pts])
        self.f.append(tuple(range(i, i + len(pts))))

    def add_loft(self, rings, cap_bottom=True, cap_top=True, closed_v=False):
        """rings: list of rings (equal length) ordered bottom->top; each ring CCW seen from above."""
        n = len(rings[0])
        i = len(self.v)
        for r in rings:
            assert len(r) == n
            self.v.extend(r)
        m = len(rings)
        for j in range(m if closed_v else m - 1):
            j2 = (j + 1) % m
            for k in range(n):
                k2 = (k + 1) % n
                self.f.append((i + j * n + k, i + j * n + k2, i + j2 * n + k2, i + j2 * n + k))
        if not closed_v:
            if cap_bottom:
                self.f.append(tuple(i + k for k in reversed(range(n))))
            if cap_top:
                self.f.append(tuple(i + (m - 1) * n + k for k in range(n)))

    def add_grid(self, fn, nu, nv, closed_u=False, closed_v=False):
        i = len(self.v)
        nu_pts = nu if closed_u else nu + 1
        nv_pts = nv if closed_v else nv + 1
        for iu in range(nu_pts):
            for iv in range(nv_pts):
                self.v.append(Vector(fn(iu / nu, iv / nv)))
        for iu in range(nu):
            iu2 = (iu + 1) % nu_pts
            for iv in range(nv):
                iv2 = (iv + 1) % nv_pts
                self.f.append((i + iu * nv_pts + iv, i + iu2 * nv_pts + iv, i + iu2 * nv_pts + iv2, i + iu * nv_pts + iv2))

    def add_sphere(self, center, radius, seg=24, rings=12, scale=(1, 1, 1)):
        rr = []
        for r in range(1, rings):
            phi = math.pi * r / rings
            rr.append([Vector((center[0] + radius * scale[0] * math.sin(phi) * math.cos(TAU * s / seg),
                               center[1] + radius * scale[1] * math.sin(phi) * math.sin(TAU * s / seg),
                               center[2] + radius * scale[2] * math.cos(phi))) for s in range(seg)])
        # bottom to top ordering
        rr.reverse()
        self.add_loft(rr)

    def build(self, name, mat=None, collection="Scene", smooth=True, subsurf=0, bevel=None, merge=True):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.validate()
        me.update()
        ob = bpy.data.objects.new(name, me)
        link(ob, collection)
        if mat is not None:
            me.materials.append(mat)
        bm = bmesh.new()
        bm.from_mesh(me)
        if merge:
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
        if smooth:
            me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        if bevel:
            add_bevel(ob, bevel)
        if subsurf:
            add_subsurf(ob, subsurf)
        return ob


def add_bevel(ob, width=0.01, segments=3):
    m = ob.modifiers.new("Bevel", 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(35)
    return m


def add_subsurf(ob, levels=2):
    m = ob.modifiers.new("Subd", 'SUBSURF')
    m.levels = levels
    m.render_levels = levels
    return m


# ------------------------------------------------------------------ primitives
def loft(name, rings, mat=None, collection="Scene", subsurf=0, smooth=True, caps=True, bevel=None):
    mb = MB()
    mb.add_loft(rings, cap_bottom=caps, cap_top=caps)
    return mb.build(name, mat, collection, smooth=smooth, subsurf=subsurf, bevel=bevel)


def blob(name, center, size, mat=None, e=4.0, n=40, zrings=None, bulge=0.0, lean=(0.0, 0.0), taper=(1.0, 1.0),
         wob=0.0, wob_freq=3, phase=0.0, twist=0.0, rot=0.0, subsurf=2, collection="Scene", top_zfn=None,
         edge=0.04, mat4=None, bevel=None, profile=None):
    """Rounded 'box' centred at `center` (x, y, z_bottom) of size (w, d, h).

    bulge: mid-height radial swell (fraction). lean: top offset (dx, dy). taper: (sx, sy) scale at top.
    twist: total rotation (rad) from bottom to top. edge: extra rings near the ends to keep edges crisp-ish.
    """
    cx, cy, z0 = center
    w, d, h = size
    a, b = w / 2, d / 2
    if profile is not None:
        zs = [t for t, _ in profile]
    elif zrings is None:
        zs = [0.0, edge, 0.25, 0.5, 0.75, 1.0 - edge, 1.0]
    else:
        zs = zrings
    rings = []
    for t in zs:
        s = 1.0 + bulge * math.sin(math.pi * t)
        if profile is not None:
            s *= interp(profile, t)
        sx = lerp(1.0, taper[0], t) * s
        sy = lerp(1.0, taper[1], t) * s
        ox, oy = lean[0] * smoothstep(t), lean[1] * smoothstep(t)
        r = sring(cx + ox, cy + oy, z0 + h * t, a * sx, b * sy, e, n, rot + twist * t, wob, wob_freq, phase + t * 2.0,
                  zfn=(top_zfn if (top_zfn and t >= 1.0 - edge) else None))
        rings.append(r)
    if mat4 is not None:
        rings = [transform_pts(r, mat4) for r in rings]
    return loft(name, rings, mat, collection, subsurf=subsurf, bevel=bevel)


def lathe(name, profile, center=(0, 0, 0), n=40, mat=None, wob=0.0, wob_freq=3, phase=0.0, subsurf=1,
          collection="Scene", scale=(1.0, 1.0), lean=(0.0, 0.0), rot=0.0, e=2.0, mat4=None, caps=True):
    """profile: list of (r, z) from bottom to top. Rings with r<=0 are dropped (the cap closes the end)."""
    cx, cy, cz = center
    rings = []
    zmin, zmax = profile[0][1], profile[-1][1]
    for r, z in profile:
        if r <= 0.0:
            continue
        t = (z - zmin) / (zmax - zmin) if zmax > zmin else 0.0
        rr = r
        ox, oy = lean[0] * t, lean[1] * t
        rings.append(sring(cx + ox, cy + oy, cz + z, rr * scale[0], rr * scale[1], e, n, rot, wob, wob_freq, phase + t))
    if mat4 is not None:
        rings = [transform_pts(r, mat4) for r in rings]
    return loft(name, rings, mat, collection, subsurf=subsurf, caps=caps)


def slab(name, outline, z0, z1, mat=None, subsurf=1, collection="Scene", bevel=None, zfn_bottom=None, zfn_top=None):
    """Extrude a closed 2D outline (list of (x, y), CCW) between z0 and z1."""
    bot = [Vector((x, y, z0 + (zfn_bottom(x, y) if zfn_bottom else 0.0))) for x, y in outline]
    top = [Vector((x, y, z1 + (zfn_top(x, y) if zfn_top else 0.0))) for x, y in outline]
    if subsurf:
        # extra rings near the faces so subsurf keeps the slab flat but rounds the rim
        h = z1 - z0
        mid1 = [Vector((p.x, p.y, p.z + h * 0.15)) for p in bot]
        mid2 = [Vector((p.x, p.y, p.z - h * 0.15)) for p in top]
        rings = [bot, mid1, mid2, top]
    else:
        rings = [bot, top]
    return loft(name, rings, mat, collection, subsurf=subsurf, bevel=bevel)


def rounded_rect(cx, cy, w, h, r=0.1, n=64, wave=None):
    """CCW outline of a rounded rectangle; `wave(x, y, nx, ny)` returns an outward offset for wobbly edges."""
    pts = sring(cx, cy, 0.0, w / 2, h / 2, e=2.0 + 6.0 * max(0.0, 1.0 - 2 * r / min(w, h)), n=n)
    out = []
    for p in pts:
        if wave:
            nx, ny = p.x - cx, p.y - cy
            l = math.hypot(nx, ny) or 1.0
            o = wave(p.x, p.y, nx / l, ny / l)
            out.append((p.x + nx / l * o, p.y + ny / l * o))
        else:
            out.append((p.x, p.y))
    return out


def sphere(name, center, radius, mat=None, seg=24, rings=12, scale=(1, 1, 1), subsurf=1, collection="Scene"):
    mb = MB()
    mb.add_sphere(center, radius, seg, rings, scale)
    return mb.build(name, mat, collection, smooth=True, subsurf=subsurf)


def cylinder(name, center, radius, height, mat=None, n=32, r_top=None, subsurf=0, collection="Scene", mat4=None, wob=0.0):
    cx, cy, cz = center
    rt = radius if r_top is None else r_top
    rings = [cring(cx, cy, cz, radius, n, wob), cring(cx, cy, cz + height, rt, n, wob)]
    if mat4 is not None:
        rings = [transform_pts(r, mat4) for r in rings]
    return loft(name, rings, mat, collection, subsurf=subsurf)


def torus(name, center, R, r, mat=None, nu=48, nv=16, wob=0.0, wob_freq=3, scale=(1.0, 1.0), collection="Scene", mat4=None):
    cx, cy, cz = center

    def fn(u, v):
        th = TAU * u
        ph = TAU * v
        Rw = R * (1 + wob * math.sin(wob_freq * th))
        x = (Rw + r * math.cos(ph)) * math.cos(th) * scale[0]
        y = (Rw + r * math.cos(ph)) * math.sin(th) * scale[1]
        z = r * math.sin(ph)
        p = Vector((cx + x, cy + y, cz + z))
        return mat4 @ p if mat4 is not None else p

    mb = MB()
    mb.add_grid(fn, nu, nv, closed_u=True, closed_v=True)
    return mb.build(name, mat, collection, smooth=True)


# ------------------------------------------------------------------ curves / tubes
def tube(name, points, radius=0.02, mat=None, radii=None, cyclic=False, res=12, bevel_res=6, collection="Scene",
         order=4, caps=True, kind='NURBS'):
    """Smooth NURBS tube through `points` (list of xyz). `radii` scales the bevel per point."""
    cu = bpy.data.curves.new(name, 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = radius
    cu.bevel_resolution = bevel_res
    cu.resolution_u = res
    cu.use_fill_caps = caps
    sp = cu.splines.new(kind)
    sp.points.add(len(points) - 1)
    for i, p in enumerate(points):
        sp.points[i].co = (p[0], p[1], p[2], 1.0)
        if radii is not None:
            sp.points[i].radius = radii[i]
    if kind == 'NURBS':
        sp.order_u = min(order, len(points))
        sp.use_endpoint_u = True
    sp.use_cyclic_u = cyclic
    sp.use_smooth = True
    ob = bpy.data.objects.new(name, cu)
    if mat is not None:
        cu.materials.append(mat)
    link(ob, collection)
    return ob


def helix(center, r0, r1, z0, z1, turns, n=60, lean=(0, 0)):
    """Points on a helix that goes from radius r0 at z0 to r1 at z1."""
    cx, cy = center
    pts = []
    for i in range(n + 1):
        t = i / n
        r = lerp(r0, r1, t)
        th = TAU * turns * t
        pts.append((cx + r * math.cos(th) + lean[0] * t, cy + r * math.sin(th) + lean[1] * t, lerp(z0, z1, t)))
    return pts


def spiral2d(center, r0, r1, turns, n=60, plane='XZ', tilt=0.0):
    """Flat spiral (a curl) in a vertical plane. center=(x,y,z)."""
    cx, cy, cz = center
    pts = []
    for i in range(n + 1):
        t = i / n
        r = lerp(r0, r1, t)
        th = TAU * turns * t
        u, v = r * math.cos(th), r * math.sin(th)
        if plane == 'XZ':
            p = (cx + u * math.cos(tilt), cy + u * math.sin(tilt), cz + v)
        else:
            p = (cx - u * math.sin(tilt), cy + u * math.cos(tilt), cz + v)
        pts.append(p)
    return pts


def curl_top(base, height, curl_r, turns=1.25, n=40, dir_xy=(1.0, 0.0), bend=0.0):
    """A stalk rising from `base`, then curling over. Returns points (+ radii that taper)."""
    bx, by, bz = base
    dx, dy = dir_xy
    pts = []
    radii = []
    m = 12
    for i in range(m):
        t = i / m
        pts.append((bx + bend * dx * t * t, by + bend * dy * t * t, bz + height * t))
        radii.append(1.0)
    cx, cy, cz = pts[-1][0] - curl_r * dx, pts[-1][1] - curl_r * dy, pts[-1][2]
    for i in range(1, n + 1):
        t = i / n
        th = TAU * turns * t
        r = curl_r * (1.0 - 0.55 * t)
        pts.append((cx + r * math.cos(th) * dx, cy + r * math.cos(th) * dy, cz + r * math.sin(th)))
        radii.append(1.0 - 0.75 * t)
    return pts, radii


# ------------------------------------------------------------------ misc
def set_origin(ob, loc):
    """Move object origin to world `loc` without moving the geometry."""
    d = Vector(loc) - ob.location
    ob.data.transform(Matrix.Translation(-d))
    ob.location = Vector(loc)


def parent(children, par):
    for c in children:
        c.parent = par
        c.matrix_parent_inverse = par.matrix_world.inverted()


def rotate_about(ob, pivot, axis, angle):
    """Rotate object around a world pivot."""
    R = Matrix.Rotation(angle, 4, axis)
    T = Matrix.Translation(Vector(pivot))
    ob.matrix_world = T @ R @ T.inverted() @ ob.matrix_world


def apply_matrix(obs, mat4):
    for o in obs:
        o.matrix_world = mat4 @ o.matrix_world
