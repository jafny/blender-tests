"""Geometry helpers for the procedural jungle (bpy 4.2).

  * MB          - mesh builder with per-vertex attributes (leaf UVs, random ids) and per-face materials
  * tube()      - lofted tube along a 3D path with parallel-transport frames (trunks, branches, petioles, vines)
  * leaf()      - a bent, drooping, folded leaf blade written straight into an MB
  * instancer() - a point cloud + geometry-nodes modifier that instances one asset object per point
  * fbm()       - fractal noise used for terrain, rocks, bark displacement
"""
import math
import random
import bpy
import bmesh
from mathutils import Vector, Matrix, Quaternion, noise

TAU = math.tau
rng = random.Random(11)

_collections = {}


def coll(name, parent=None):
    if name in _collections:
        return _collections[name]
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    _collections[name] = c
    return c


def exclude(name):
    """Exclude a collection from the view layer (asset library: only rendered through instancers)."""
    def walk(lc):
        if lc.collection.name == name:
            lc.exclude = True
            return True
        return any(walk(ch) for ch in lc.children)
    walk(bpy.context.view_layer.layer_collection)


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


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def smoothstep(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0)) if e1 != e0 else (1.0 if x >= e1 else 0.0)
    return t * t * (3 - 2 * t)


def interp(keys, t):
    """Piecewise-linear interpolation of [(t, value), ...] (sorted by t)."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return lerp(v0, v1, (t - t0) / (t1 - t0) if t1 > t0 else 0.0)
    return keys[-1][1]


def fbm(x, y, z=0.0, octaves=4, lac=2.0, gain=0.5, basis='PERLIN_NEW'):
    s, a, f = 0.0, 1.0, 1.0
    for _ in range(octaves):
        s += a * noise.noise(Vector((x * f, y * f, z * f)), noise_basis=basis)
        a *= gain
        f *= lac
    return s


def basis_from(d, up=Vector((0, 0, 1))):
    """Orthonormal (side, d, normal) with d forward; normal as close to `up` as possible."""
    d = Vector(d).normalized()
    side = d.cross(up)
    if side.length < 1e-5:
        side = d.cross(Vector((0, 1, 0)))
    side.normalize()
    nrm = side.cross(d).normalized()
    return side, d, nrm


# ------------------------------------------------------------------ mesh builder
class MB:
    def __init__(self):
        self.v = []
        self.f = []
        self.fm = []           # per-face material slot
        self.ff = []           # per-face flat-shading flag
        self.attr = {}         # name -> per-vertex list of 3-tuples (FLOAT_VECTOR)
        self.mat = 0

    def _pad(self):
        for name, lst in self.attr.items():
            while len(lst) < len(self.v):
                lst.append((0.0, 0.0, 0.0))

    def set_attr(self, name, idx, val):
        lst = self.attr.setdefault(name, [])
        while len(lst) < len(self.v):
            lst.append((0.0, 0.0, 0.0))
        lst[idx] = tuple(val)

    def vert(self, p, **attrs):
        self.v.append(Vector(p))
        i = len(self.v) - 1
        for k, val in attrs.items():
            self.set_attr(k, i, val)
        return i

    def face(self, idx, flat=False):
        self.f.append(tuple(idx))
        self.fm.append(self.mat)
        self.ff.append(flat)

    def grid(self, rows, closed=False, cap0=False, cap1=False):
        """rows: list of lists of vertex indices (equal length). Connect consecutive rows with quads."""
        n = len(rows[0])
        for a, b in zip(rows, rows[1:]):
            for k in range(n if closed else n - 1):
                k2 = (k + 1) % n
                self.face((a[k], a[k2], b[k2], b[k]))
        if cap0:
            self.face(list(reversed(rows[0])), flat=True)
        if cap1:
            self.face(rows[-1], flat=True)

    def merge(self, other, mat=None):
        off = len(self.v)
        self._pad()
        other._pad()
        self.v.extend(other.v)
        for name in set(self.attr) | set(other.attr):
            a = self.attr.setdefault(name, [(0.0, 0.0, 0.0)] * off)
            while len(a) < off:
                a.append((0.0, 0.0, 0.0))
            a.extend(other.attr.get(name, [(0.0, 0.0, 0.0)] * len(other.v)))
        for f, m, fl in zip(other.f, other.fm, other.ff):
            self.f.append(tuple(i + off for i in f))
            self.fm.append(m if mat is None else mat)
            self.ff.append(fl)

    def transform(self, mat):
        self.v = [mat @ p for p in self.v]

    def build(self, name, mats=(), collection="Scene", smooth=True, subsurf=0, recalc=True, auto_smooth=None):
        self._pad()
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(p) for p in self.v], [], self.f)
        me.validate(clean_customdata=False)
        for m in mats:
            me.materials.append(m)
        if self.fm and len(me.polygons) == len(self.fm):
            me.polygons.foreach_set("material_index", self.fm)
        for aname, vals in self.attr.items():
            a = me.attributes.new(aname, 'FLOAT_VECTOR', 'POINT')
            flat = [c for v in vals[:len(me.vertices)] for c in v]
            a.data.foreach_set("vector", flat)
        if recalc:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(me)
            bm.free()
        if len(self.ff) == len(me.polygons):
            me.polygons.foreach_set("use_smooth", [smooth and not fl for fl in self.ff])
        else:
            me.polygons.foreach_set("use_smooth", [smooth] * len(me.polygons))
        me.update()
        ob = bpy.data.objects.new(name, me)
        link(ob, collection)
        if subsurf:
            m = ob.modifiers.new("Subd", 'SUBSURF')
            m.levels = m.render_levels = subsurf
        return ob


# ------------------------------------------------------------------ tubes
def path_frames(pts):
    """Parallel-transport frames along a polyline: list of (tangent, normal, binormal)."""
    pts = [Vector(p) for p in pts]
    tans = []
    for i in range(len(pts)):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        tans.append((b - a).normalized())
    t0 = tans[0]
    ref = Vector((0, 0, 1)) if abs(t0.z) < 0.9 else Vector((1, 0, 0))
    n = t0.cross(ref).normalized()
    frames = []
    for i, t in enumerate(tans):
        if i > 0:
            q = tans[i - 1].rotation_difference(t)
            n = (q @ n)
            n = (n - t * n.dot(t)).normalized()
        frames.append((t, n, t.cross(n).normalized()))
    return frames


def tube(mb, pts, radii, sides=8, cap0=False, cap1=True, rfn=None, vscale=1.0, rid=0.0):
    """Loft a tube along pts. rfn(i, theta) -> radius multiplier (bark ridges, buttresses)."""
    frames = path_frames(pts)
    rows = []
    length = 0.0
    for i, (p, r, (t, n, b)) in enumerate(zip(pts, radii, frames)):
        if i > 0:
            length += (Vector(p) - Vector(pts[i - 1])).length
        row = []
        for k in range(sides):
            th = TAU * k / sides
            rr = r * (rfn(i, th) if rfn else 1.0)
            off = n * math.cos(th) * rr + b * math.sin(th) * rr
            row.append(mb.vert(Vector(p) + off, luv=(k / sides, length * vscale, rid)))
        rows.append(row)
    mb.grid(rows, closed=True, cap0=cap0, cap1=cap1)
    return rows


def bezier_pts(p0, p1, p2, p3, n):
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append(Vector(p0) * u ** 3 + Vector(p1) * 3 * u * u * t + Vector(p2) * 3 * u * t * t + Vector(p3) * t ** 3)
    return out


# ------------------------------------------------------------------ leaves
def leaf(mb, base, direction, length, width, shape=None, nu=8, nv=2, droop=0.6, fold=0.25, twist=0.0,
         curl=0.0, side_up=None, rid=None, lobe=0.0, wave=0.0, ripple=0.0, tears=None):
    """Write a leaf blade into mb.

    base/direction: attachment point and initial heading. droop: total downward bend (rad) along the blade.
    fold: V-fold depth relative to width. lobe: fraction of length extending *behind* the attachment (heart leaves).
    tears: list of u-positions where the blade is split from the edge to the midrib (banana leaves).
    Attribute luv = (u along blade 0..1, v across -1..1, per-leaf random).
    """
    if shape is None:
        def shape(u):
            return math.sin(math.pi * clamp(u)) ** 0.8
    rid = rng.random() if rid is None else rid
    side, fwd, nrm = basis_from(direction, side_up or Vector((0, 0, 1)))
    # spine integration: heading rotates downward around `side`
    us = [lerp(-lobe, 1.0, i / nu) for i in range(nu + 1)]
    spine = []
    p = Vector(base) - fwd * (lobe * length)
    d = fwd.copy()
    sd, nm = side.copy(), nrm.copy()
    prev_u = us[0]
    for u in us:
        du = (u - prev_u) * length
        if du > 0:
            ang = droop * du / length * (0.3 + 1.4 * clamp(u))
            q = Quaternion(sd, -ang)
            d = (q @ d).normalized()
            nm = (q @ nm).normalized()
            if twist:
                qt = Quaternion(d, twist * du / length)
                sd = (qt @ sd).normalized()
                nm = (qt @ nm).normalized()
            p = p + d * du
        spine.append((u, p.copy(), sd.copy(), nm.copy()))
        prev_u = u
    tears = sorted(tears or [])

    def write_half(sgn):
        # split blade into segments at tears (each segment = separate grid -> visible gaps)
        cuts = [t for t in tears]
        segs = []
        cur = []
        for i, s in enumerate(spine):
            cur.append(i)
            if any(abs(s[0] - c) < 0.5 / nu for c in cuts) and 0 < i < len(spine) - 1:
                segs.append(cur)
                cur = [i]
        segs.append(cur)
        for si, seg in enumerate(segs):
            if len(seg) < 2:
                continue
            rows = []
            for i in seg:
                u, sp, sd_, nm_ = spine[i]
                w = width * 0.5 * shape(clamp((u + lobe) / (1 + lobe)) if lobe else u)
                if lobe and u < 0:
                    w *= 1.0
                row = []
                for j in range(nv + 1):
                    v = j / nv
                    vv = v * sgn
                    gap = 0.05 * width * (v - 0.2) if (si > 0 and i == seg[0] and v > 0.2) else 0.0
                    lift = fold * w * v + curl * w * v * v + wave * w * math.sin(u * 20 + rid * 9) * v
                    lift += ripple * w * math.sin(v * 9 + u * 31) * v
                    pos = sp + sd_ * (vv * w) + nm_ * lift - sd_.cross(nm_) * gap   # (side x normal = -heading)
                    row.append(mb.vert(pos, luv=(clamp(u), vv, rid)))
                rows.append(row)
            if sgn > 0:
                mb.grid(rows)
            else:
                mb.grid([list(r) for r in rows])
    write_half(1.0)
    write_half(-1.0)
    return spine


# ------------------------------------------------------------------ instancing
_inst_groups = {}


def _instancer_group(kind='Object'):
    """GN group: instance an Object (or a whole Collection) on every point, using the rot/scl point attributes."""
    g = _inst_groups.get(kind)
    if g is not None and g.name in bpy.data.node_groups:
        return g
    g = bpy.data.node_groups.new("PointInstancer" + ("" if kind == 'Object' else "_" + kind), 'GeometryNodeTree')
    g.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
    g.interface.new_socket(kind, in_out='INPUT', socket_type='NodeSocket' + kind)
    g.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = g.nodes
    gi = N.new("NodeGroupInput")
    go = N.new("NodeGroupOutput")
    if kind == 'Object':
        oi = N.new("GeometryNodeObjectInfo")
        oi.transform_space = 'ORIGINAL'
        oi.inputs["As Instance"].default_value = True
    else:
        oi = N.new("GeometryNodeCollectionInfo")
        oi.transform_space = 'ORIGINAL'
        oi.inputs["Separate Children"].default_value = False
    iop = N.new("GeometryNodeInstanceOnPoints")
    rot = N.new("GeometryNodeInputNamedAttribute")
    rot.data_type = 'FLOAT_VECTOR'
    rot.inputs["Name"].default_value = "rot"
    scl = N.new("GeometryNodeInputNamedAttribute")
    scl.data_type = 'FLOAT_VECTOR'
    scl.inputs["Name"].default_value = "scl"
    L = g.links
    L.new(gi.outputs[0], iop.inputs["Points"])
    L.new(gi.outputs[1], oi.inputs[kind])
    L.new(oi.outputs["Geometry" if kind == 'Object' else "Instances"], iop.inputs["Instance"])
    try:
        e2r = N.new("FunctionNodeEulerToRotation")
        L.new(rot.outputs["Attribute"], e2r.inputs[0])
        L.new(e2r.outputs[0], iop.inputs["Rotation"])
    except RuntimeError:
        L.new(rot.outputs["Attribute"], iop.inputs["Rotation"])
    L.new(scl.outputs["Attribute"], iop.inputs["Scale"])
    L.new(iop.outputs["Instances"], go.inputs[0])
    _inst_groups[kind] = g
    return g


def instancer(name, asset, items, collection="Scene"):
    """items: list of (location, euler_xyz, scale or (sx,sy,sz)). Returns the instancer object."""
    if not items:
        return None
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(it[0]) for it in items], [], [])
    a_r = me.attributes.new("rot", 'FLOAT_VECTOR', 'POINT')
    a_r.data.foreach_set("vector", [c for it in items for c in it[1]])
    a_s = me.attributes.new("scl", 'FLOAT_VECTOR', 'POINT')
    sc = []
    for it in items:
        s = it[2]
        sc.extend((s, s, s) if isinstance(s, (int, float)) else s)
    a_s.data.foreach_set("vector", sc)
    ob = bpy.data.objects.new(name, me)
    link(ob, collection)
    mod = ob.modifiers.new("Instances", 'NODES')
    kind = 'Collection' if isinstance(asset, bpy.types.Collection) else 'Object'
    g = _instancer_group(kind)
    mod.node_group = g
    ident = [it.identifier for it in g.interface.items_tree
             if getattr(it, "in_out", "") == 'INPUT' and it.socket_type == 'NodeSocket' + kind][0]
    mod[ident] = asset
    return ob


def scatter(fn_ok, area, n, seed=0, min_dist=0.0, tries=30):
    """Random (dart-throwing) points in area=(x0,x1,y0,y1) satisfying fn_ok(x, y)."""
    r = random.Random(seed)
    out = []
    cell = max(min_dist, 1e-3)
    grid = {}
    for _ in range(n * tries):
        if len(out) >= n:
            break
        x = r.uniform(area[0], area[1])
        y = r.uniform(area[2], area[3])
        if not fn_ok(x, y):
            continue
        if min_dist > 0:
            gx, gy = int(x // cell), int(y // cell)
            bad = False
            for ix in range(gx - 1, gx + 2):
                for iy in range(gy - 1, gy + 2):
                    for (px, py) in grid.get((ix, iy), ()):
                        if (px - x) ** 2 + (py - y) ** 2 < min_dist ** 2:
                            bad = True
                            break
                    if bad:
                        break
                if bad:
                    break
            if bad:
                continue
            grid.setdefault((gx, gy), []).append((x, y))
        out.append((x, y))
    return out
