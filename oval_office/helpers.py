"""Geometry helpers for the Oval Office generator (bpy 4.2)."""
import math
import bpy
import bmesh
from mathutils import Vector, Matrix

# --- Room dimensions (metres). Real room: 35'10" x 29', 18'6" ceiling. ---
A = 5.46          # semi-major axis (north-south, +Y = north)
B = 4.42          # semi-minor axis (east-west,  +X = east)
H = 5.64          # ceiling height
WALL_T = 0.45     # wall thickness
TAU = math.tau

_collections = {}


def coll(name):
    """Get or create a collection linked to the scene."""
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


# ------------------------------------------------------------------ ellipse
def ell_pt(theta, inset=0.0, z=0.0, a=A, b=B):
    """Point on the room ellipse (x=b cos, y=a sin), moved `inset` toward the centre."""
    n = ell_normal(theta, a, b)
    return Vector((b * math.cos(theta) - n.x * inset, a * math.sin(theta) - n.y * inset, z))


def ell_normal(theta, a=A, b=B):
    n = Vector((a * math.cos(theta), b * math.sin(theta), 0.0))
    n.normalize()
    return n


def ell_speed(theta, a=A, b=B):
    return math.sqrt((b * math.sin(theta)) ** 2 + (a * math.cos(theta)) ** 2)


def dtheta(theta, width, a=A, b=B):
    """Angular half-width that spans `width` metres of arc around theta."""
    return 0.5 * width / ell_speed(theta, a, b)


def frame_at(theta, inset=0.0, z=0.0, a=A, b=B):
    """Matrix placing local +Y along the outward wall normal, +X tangent (viewer's right), origin on wall."""
    n = ell_normal(theta, a, b)
    rot = math.atan2(n.y, n.x) - math.pi / 2
    return Matrix.Translation(ell_pt(theta, inset, z, a, b)) @ Matrix.Rotation(rot, 4, 'Z')


# ------------------------------------------------------------------ mesh builder
class MB:
    """Accumulates verts/faces and builds a single mesh object."""

    def __init__(self):
        self.v = []
        self.f = []

    def add_poly(self, pts):
        i = len(self.v)
        self.v.extend([Vector(p) for p in pts])
        self.f.append(tuple(range(i, i + len(pts))))

    def add_quad(self, a, b, c, d):
        self.add_poly([a, b, c, d])

    def add_box(self, center, size, mat=None):
        """Axis aligned box; optional Matrix `mat` applied to the corners."""
        cx, cy, cz = center
        sx, sy, sz = size[0] / 2, size[1] / 2, size[2] / 2
        c = [Vector((cx + dx, cy + dy, cz + dz)) for dz in (-sz, sz) for dy in (-sy, sy) for dx in (-sx, sx)]
        if mat is not None:
            c = [mat @ p for p in c]
        i = len(self.v)
        self.v.extend(c)
        # bottom(0-3): 0:(-,-) 1:(+,-) 2:(-,+) 3:(+,+); top 4-7
        quads = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (1, 3, 7, 5), (3, 2, 6, 7), (2, 0, 4, 6)]
        self.f.extend([tuple(i + k for k in q) for q in quads])

    def add_cyl(self, center, radius, height, n=24, mat=None, r_top=None, closed=True):
        r_top = radius if r_top is None else r_top
        cx, cy, cz = center
        i = len(self.v)
        bot = [Vector((cx + radius * math.cos(TAU * k / n), cy + radius * math.sin(TAU * k / n), cz - height / 2)) for k in range(n)]
        top = [Vector((cx + r_top * math.cos(TAU * k / n), cy + r_top * math.sin(TAU * k / n), cz + height / 2)) for k in range(n)]
        pts = bot + top
        if mat is not None:
            pts = [mat @ p for p in pts]
        self.v.extend(pts)
        for k in range(n):
            k2 = (k + 1) % n
            self.f.append((i + k, i + k2, i + n + k2, i + n + k))
        if closed:
            self.f.append(tuple(i + k for k in reversed(range(n))))
            self.f.append(tuple(i + n + k for k in range(n)))

    def add_sphere(self, center, radius, seg=24, rings=12, mat=None, scale=(1, 1, 1)):
        cx, cy, cz = center
        i = len(self.v)
        for r in range(1, rings):
            phi = math.pi * r / rings
            for s in range(seg):
                th = TAU * s / seg
                p = Vector((cx + radius * scale[0] * math.sin(phi) * math.cos(th),
                            cy + radius * scale[1] * math.sin(phi) * math.sin(th),
                            cz + radius * scale[2] * math.cos(phi)))
                self.v.append(mat @ p if mat is not None else p)
        top = len(self.v)
        p = Vector((cx, cy, cz + radius * scale[2]))
        self.v.append(mat @ p if mat is not None else p)
        bot = len(self.v)
        p = Vector((cx, cy, cz - radius * scale[2]))
        self.v.append(mat @ p if mat is not None else p)
        for r in range(rings - 2):
            for s in range(seg):
                s2 = (s + 1) % seg
                a = i + r * seg + s
                b = i + r * seg + s2
                c = i + (r + 1) * seg + s2
                d = i + (r + 1) * seg + s
                self.f.append((a, b, c, d))
        for s in range(seg):
            s2 = (s + 1) % seg
            self.f.append((top, i + s2, i + s))
            base = i + (rings - 2) * seg
            self.f.append((bot, base + s, base + s2))

    def add_grid(self, fn, nu, nv, closed_u=False):
        """Parametric surface: fn(u,v)->Vector, u,v in [0,1]."""
        i = len(self.v)
        for iu in range(nu + (0 if closed_u else 1)):
            for iv in range(nv + 1):
                self.v.append(Vector(fn(iu / nu, iv / nv)))
        cols = nv + 1
        for iu in range(nu):
            iu2 = (iu + 1) % nu if closed_u else iu + 1
            for iv in range(nv):
                self.f.append((i + iu * cols + iv, i + iu2 * cols + iv, i + iu2 * cols + iv + 1, i + iu * cols + iv + 1))

    def build(self, name, mat=None, collection="Scene", smooth=False, recalc=True, bevel=None):
        me = bpy.data.meshes.new(name)
        me.from_pydata(self.v, [], self.f)
        me.validate()
        me.update()
        ob = bpy.data.objects.new(name, me)
        link(ob, collection)
        if mat is not None:
            me.materials.append(mat)
        if recalc:
            bm = bmesh.new()
            bm.from_mesh(me)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(me)
            bm.free()
        if smooth:
            for p in me.polygons:
                p.use_smooth = True
        if bevel:
            add_bevel(ob, bevel)
        return ob


def add_bevel(ob, width=0.006, segments=2):
    m = ob.modifiers.new("Bevel", 'BEVEL')
    m.width = width
    m.segments = segments
    m.limit_method = 'ANGLE'
    m.angle_limit = math.radians(40)
    m.harden_normals = False
    return m


def add_subsurf(ob, levels=2):
    m = ob.modifiers.new("Subd", 'SUBSURF')
    m.levels = levels
    m.render_levels = levels
    return m


def box(name, center, size, mat, collection="Scene", bevel=None, mat4=None, smooth=False):
    mb = MB()
    mb.add_box(center, size, mat4)
    return mb.build(name, mat, collection, bevel=bevel, smooth=smooth)


def cyl(name, center, radius, height, mat, n=32, collection="Scene", r_top=None, mat4=None, smooth=True):
    mb = MB()
    mb.add_cyl(center, radius, height, n, mat4, r_top)
    return mb.build(name, mat, collection, smooth=smooth)


def empty(name, matrix=None, collection="Scene"):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.2
    link(e, collection)
    if matrix is not None:
        e.matrix_world = matrix
    return e


def parent(child, par):
    child.parent = par
    child.matrix_parent_inverse = Matrix.Identity(4)


def set_xform(ob, loc=None, rot_z=None, scale=None):
    if loc is not None:
        ob.location = loc
    if rot_z is not None:
        ob.rotation_euler = (0, 0, rot_z)
    if scale is not None:
        ob.scale = scale
    return ob


def shade_smooth(ob, on=True):
    for p in ob.data.polygons:
        p.use_smooth = on


def cushion(name, center, size, mat, collection="Scene", levels=2, round_frac=0.42):
    """A soft, rounded box (heavily bevelled cube) for cushions/pillows."""
    ob = box(name, center, size, mat, collection)
    m = ob.modifiers.new("Round", 'BEVEL')
    m.width = min(size) * round_frac
    m.segments = 6
    m.limit_method = 'NONE'
    shade_smooth(ob)
    return ob


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras, bpy.data.curves, bpy.data.images):
        for x in list(block):
            if x.users == 0:
                block.remove(x)
