"""Procedural Seuss-style materials: flat candy colours, stripes, polka dots, wavy checkers."""
import math
import bpy

_cache = {}

# --------------------------------------------------------------- palette (sRGB hex)
P = {
    "red": "#F03A3A", "orange": "#FF8A2A", "yellow": "#FFD23F", "lime": "#A5E63C", "green": "#2FBF71",
    "teal": "#1FC2B8", "sky": "#5DC8FF", "blue": "#3E6BFF", "purple": "#8E4FD6", "magenta": "#F1479C",
    "pink": "#FFA6D5", "cream": "#FFF4D6", "white": "#FDFBF5", "ink": "#2A1F3D", "plum": "#5B2A86",
    "coral": "#FF6B5B", "mint": "#9CF0D0", "lavender": "#CBB3FF", "peach": "#FFC48C", "sun": "#FFB703",
    "grey": "#B9B4C7", "brown": "#8B5A3C", "chocolate": "#5A3423", "tan": "#E8C39E",
}


def hexc(h, a=1.0):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) + (a,)


def srgb_to_linear(c):
    def f(x):
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return tuple(f(x) for x in c[:3]) + (c[3] if len(c) > 3 else 1.0,)


def col(h):
    """Palette key or hex -> linear RGBA."""
    return srgb_to_linear(hexc(P.get(h, h)))


def _new(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (700, 0)
    return m, nt, out


def _node(nt, kind, loc=(0, 0), **props):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def _principled(nt, color=None, rough=0.35, coat=0.35, metallic=0.0, spec=0.5, sheen=0.0, loc=(400, 0)):
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.location = loc
    if color is not None:
        p.inputs["Base Color"].default_value = color
    p.inputs["Roughness"].default_value = rough
    p.inputs["Coat Weight"].default_value = coat
    p.inputs["Coat Roughness"].default_value = 0.15
    p.inputs["Metallic"].default_value = metallic
    p.inputs["Specular IOR Level"].default_value = spec
    p.inputs["Sheen Weight"].default_value = sheen
    return p


def _ramp(nt, stops, loc=(0, 0), interp='CONSTANT'):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.location = loc
    r.color_ramp.interpolation = interp
    el = r.color_ramp.elements
    el[0].position, el[0].color = stops[0]
    el[1].position, el[1].color = stops[-1]
    for pos, c in stops[1:-1]:
        e = el.new(pos)
        e.color = c
    return r


def _math(nt, op, a=None, b=None, va=None, vb=None, loc=(0, 0)):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.location = loc
    if a is not None:
        nt.links.new(a, n.inputs[0])
    if b is not None:
        nt.links.new(b, n.inputs[1])
    if va is not None:
        n.inputs[0].default_value = va
    if vb is not None:
        n.inputs[1].default_value = vb
    return n


def _coords(nt, scale=(1, 1, 1), rot=(0, 0, 0), loc=(0, 0, 0), wobble=0.0, wfreq=1.0, source='Object'):
    """Object-space coords with optional noise warp (for hand-drawn wobbliness). Returns the vector socket."""
    tc = _node(nt, "ShaderNodeTexCoord", (-1400, 0))
    mp = _node(nt, "ShaderNodeMapping", (-1200, 0))
    mp.inputs["Scale"].default_value = scale
    mp.inputs["Rotation"].default_value = rot
    mp.inputs["Location"].default_value = loc
    nt.links.new(tc.outputs[source], mp.inputs["Vector"])
    v = mp.outputs["Vector"]
    if wobble:
        nz = _node(nt, "ShaderNodeTexNoise", (-1000, -300))
        nz.inputs["Scale"].default_value = wfreq
        nz.inputs["Detail"].default_value = 1.0
        nz.inputs["Roughness"].default_value = 0.4
        nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
        sub = _node(nt, "ShaderNodeVectorMath", (-800, -300), operation='SUBTRACT')
        nt.links.new(nz.outputs["Color"], sub.inputs[0])
        sub.inputs[1].default_value = (0.5, 0.5, 0.5)
        sc = _node(nt, "ShaderNodeVectorMath", (-650, -300), operation='SCALE')
        nt.links.new(sub.outputs[0], sc.inputs[0])
        sc.inputs["Scale"].default_value = wobble
        add = _node(nt, "ShaderNodeVectorMath", (-500, 0), operation='ADD')
        nt.links.new(v, add.inputs[0])
        nt.links.new(sc.outputs[0], add.inputs[1])
        v = add.outputs[0]
    return v


def _finish(nt, out, p, name, m):
    nt.links.new(p.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


# --------------------------------------------------------------- cut-outs via alpha
def _holes_alpha(nt, holes, loc=(-2000, -800)):
    """Build an alpha socket that is 0 inside any of the given wobbly-ellipse holes.

    Each hole: dict(axis_u='x'|'y', axis_side=('y'|'x', +1|-1), u0, z0, ru, rz, tilt, wob, freq, phase)
    Holes are expressed in object space: u along the wall (x or y), z vertical; axis_side says which half-space
    of the other horizontal axis the hole belongs to (so front/back walls don't share holes).
    When axis_u == 'xy' the hole is horizontal (u=x, v=y) - used for the sink cut-out in the counter.
    """
    tc = _node(nt, "ShaderNodeTexCoord", (loc[0], loc[1]))
    sep = _node(nt, "ShaderNodeSeparateXYZ", (loc[0] + 200, loc[1]))
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    X, Y, Z = sep.outputs[0], sep.outputs[1], sep.outputs[2]
    acc = None
    for i, h in enumerate(holes):
        y0 = loc[1] - 250 * i
        if h.get("axis_u") == 'xy':
            U, V = X, Y
        else:
            U = X if h["axis_u"] == 'x' else Y
            V = Z
        du = _math(nt, 'SUBTRACT', U, vb=h["u0"], loc=(loc[0] + 400, y0))
        dv = _math(nt, 'SUBTRACT', V, vb=h["z0"], loc=(loc[0] + 400, y0 - 60))
        tilt = h.get("tilt", 0.0)
        if tilt:
            c, s_ = math.cos(tilt), math.sin(tilt)
            a1 = _math(nt, 'MULTIPLY', du.outputs[0], vb=c, loc=(loc[0] + 550, y0))
            a2 = _math(nt, 'MULTIPLY', dv.outputs[0], vb=s_, loc=(loc[0] + 550, y0 - 40))
            b1 = _math(nt, 'MULTIPLY', du.outputs[0], vb=-s_, loc=(loc[0] + 550, y0 - 80))
            b2 = _math(nt, 'MULTIPLY', dv.outputs[0], vb=c, loc=(loc[0] + 550, y0 - 120))
            du = _math(nt, 'ADD', a1.outputs[0], a2.outputs[0], loc=(loc[0] + 700, y0))
            dv = _math(nt, 'ADD', b1.outputs[0], b2.outputs[0], loc=(loc[0] + 700, y0 - 60))
        nu = _math(nt, 'DIVIDE', du.outputs[0], vb=h["ru"], loc=(loc[0] + 850, y0))
        nv = _math(nt, 'DIVIDE', dv.outputs[0], vb=h["rz"], loc=(loc[0] + 850, y0 - 60))
        ang = _math(nt, 'ARCTAN2', nv.outputs[0], nu.outputs[0], loc=(loc[0] + 1000, y0))
        wf = _math(nt, 'MULTIPLY', ang.outputs[0], vb=h.get("freq", 3), loc=(loc[0] + 1150, y0))
        wf = _math(nt, 'ADD', wf.outputs[0], vb=h.get("phase", 0.0), loc=(loc[0] + 1300, y0))
        wf = _math(nt, 'SINE', wf.outputs[0], loc=(loc[0] + 1450, y0))
        wf = _math(nt, 'MULTIPLY', wf.outputs[0], vb=h.get("wob", 0.0), loc=(loc[0] + 1600, y0))
        w = _math(nt, 'ADD', wf.outputs[0], vb=1.0, loc=(loc[0] + 1750, y0))
        # inside if nu^2 + nv^2 < w^2
        r2 = _math(nt, 'MULTIPLY', nu.outputs[0], nu.outputs[0], loc=(loc[0] + 1000, y0 - 120))
        v2 = _math(nt, 'MULTIPLY', nv.outputs[0], nv.outputs[0], loc=(loc[0] + 1150, y0 - 120))
        r2 = _math(nt, 'ADD', r2.outputs[0], v2.outputs[0], loc=(loc[0] + 1300, y0 - 120))
        r = _math(nt, 'SQRT', r2.outputs[0], loc=(loc[0] + 1450, y0 - 120))
        inside = _math(nt, 'LESS_THAN', r.outputs[0], w.outputs[0], loc=(loc[0] + 1900, y0))
        side = h.get("axis_side")
        if side:
            S = X if side[0] == 'x' else Y
            ok = _math(nt, 'GREATER_THAN' if side[1] > 0 else 'LESS_THAN', S, vb=0.0, loc=(loc[0] + 1900, y0 - 80))
            inside = _math(nt, 'MULTIPLY', inside.outputs[0], ok.outputs[0], loc=(loc[0] + 2050, y0))
        acc = inside if acc is None else _math(nt, 'MAXIMUM', acc.outputs[0], inside.outputs[0], loc=(loc[0] + 2200, y0))
    alpha = _math(nt, 'SUBTRACT', va=1.0, b=acc.outputs[0], loc=(loc[0] + 2400, loc[1]))
    return alpha.outputs[0]


# --------------------------------------------------------------- basic
def candy(name, color, rough=0.32, coat=0.4, metallic=0.0, sheen=0.0):
    """Glossy painted / plastic colour."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    p = _principled(nt, col(color), rough, coat, metallic, sheen=sheen)
    return _finish(nt, out, p, name, m)


def matte(name, color, rough=0.7):
    return candy(name, color, rough=rough, coat=0.0)


def metal(name, color="#EDEDF2", rough=0.22):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    p = _principled(nt, col(color), rough, 0.0, 1.0)
    return _finish(nt, out, p, name, m)


def glass(name="Glass", tint="#E8FBFF"):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    p = _principled(nt, col(tint), 0.05, 0.0)
    p.inputs["Transmission Weight"].default_value = 1.0
    p.inputs["IOR"].default_value = 1.2
    return _finish(nt, out, p, name, m)


def emission(name, color, strength=5.0):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    e = _node(nt, "ShaderNodeEmission", (400, 0))
    e.inputs["Color"].default_value = col(color)
    e.inputs["Strength"].default_value = strength
    return _finish(nt, out, e, name, m)


def glow_paint(name, color, strength=1.5, rough=0.35):
    """Colour that also glows softly (lampshades, bulbs)."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    p = _principled(nt, col(color), rough, 0.2)
    p.inputs["Emission Color"].default_value = col(color)
    p.inputs["Emission Strength"].default_value = strength
    return _finish(nt, out, p, name, m)


# --------------------------------------------------------------- patterns
def stripes(name, colors, width=0.12, axis='z', tilt=0.0, wobble=0.15, rough=0.32, coat=0.4, wfreq=0.8, offset=0.0):
    """Candy stripes perpendicular to `axis` (in object/world metres), optionally tilted (radians) and wobbly."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    rot = {'x': (0, 0, tilt), 'y': (0, 0, tilt), 'z': (tilt, 0, 0)}[axis]
    v = _coords(nt, rot=rot, wobble=wobble, wfreq=wfreq, loc=(offset, offset, offset))
    sep = _node(nt, "ShaderNodeSeparateXYZ", (-300, 0))
    nt.links.new(v, sep.inputs[0])
    comp = sep.outputs[{'x': 0, 'y': 1, 'z': 2}[axis]]
    n = len(colors)
    d = _math(nt, 'DIVIDE', comp, vb=width * n, loc=(-150, 0))
    f = _math(nt, 'FRACT', d.outputs[0], loc=(0, 0))
    ramp = _ramp(nt, [(i / n, col(c)) for i, c in enumerate(colors)], (150, 0))
    nt.links.new(f.outputs[0], ramp.inputs[0])
    p = _principled(nt, None, rough, coat)
    nt.links.new(ramp.outputs[0], p.inputs["Base Color"])
    return _finish(nt, out, p, name, m)


def dots(name, base, dot, spacing=0.14, size=0.38, rough=0.32, coat=0.4, jitter=0.5, second=None):
    """Polka dots: voronoi cells of `spacing`, dot radius = size * spacing."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    v = _coords(nt, wobble=0.0)
    vo = _node(nt, "ShaderNodeTexVoronoi", (-300, 0))
    vo.voronoi_dimensions = '3D'
    vo.feature = 'F1'
    vo.distance = 'EUCLIDEAN'
    vo.inputs["Scale"].default_value = 1.0 / spacing
    vo.inputs["Randomness"].default_value = jitter
    nt.links.new(v, vo.inputs["Vector"])
    lt = _math(nt, 'LESS_THAN', vo.outputs["Distance"], vb=size, loc=(-100, 0))
    mix = _node(nt, "ShaderNodeMix", (100, 0), data_type='RGBA')
    nt.links.new(lt.outputs[0], mix.inputs["Factor"])
    mix.inputs[6].default_value = col(base)
    if second:
        # alternate dot colours by cell
        r2 = _ramp(nt, [(0.0, col(dot)), (0.5, col(second))], (-100, -300))
        nt.links.new(vo.outputs["Color"], r2.inputs[0])
        nt.links.new(r2.outputs[0], mix.inputs[7])
    else:
        mix.inputs[7].default_value = col(dot)
    p = _principled(nt, None, rough, coat)
    nt.links.new(mix.outputs[2], p.inputs["Base Color"])
    return _finish(nt, out, p, name, m)


def checker(name, c1, c2, size=0.5, warp=0.25, wfreq=0.5, rough=0.25, coat=0.5, rot=0.0):
    """Wavy checkerboard (floor). warp = how much the tiles wobble."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    v = _coords(nt, rot=(0, 0, rot), wobble=warp, wfreq=wfreq)
    ch = _node(nt, "ShaderNodeTexChecker", (-200, 0))
    ch.inputs["Scale"].default_value = 1.0 / size
    ch.inputs["Color1"].default_value = col(c1)
    ch.inputs["Color2"].default_value = col(c2)
    nt.links.new(v, ch.inputs["Vector"])
    p = _principled(nt, None, rough, coat)
    nt.links.new(ch.outputs["Color"], p.inputs["Base Color"])
    # subtle grout lines through a bump from the checker edges is overkill; keep it clean & cartoony
    return _finish(nt, out, p, name, m)


def wall(name, lower, upper, rail, rail_z=1.15, rail_h=0.09, wave_amp=0.10, wave_freq=1.3, stripe=None, stripe_w=0.35,
         holes=None):
    """Wainscot wall: `lower` colour below a wavy rail, `upper` (optionally soft stripes) above."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-1400, 0))
    sep = _node(nt, "ShaderNodeSeparateXYZ", (-1200, 0))
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    # rail height varies with x and y: rail_z + amp*sin(f*x) + 0.6*amp*sin(1.7*f*y)
    sx = _math(nt, 'MULTIPLY', sep.outputs[0], vb=wave_freq, loc=(-1000, 100))
    sx = _math(nt, 'SINE', sx.outputs[0], loc=(-850, 100))
    sx = _math(nt, 'MULTIPLY', sx.outputs[0], vb=wave_amp, loc=(-700, 100))
    sy = _math(nt, 'MULTIPLY', sep.outputs[1], vb=wave_freq * 1.7, loc=(-1000, -100))
    sy = _math(nt, 'SINE', sy.outputs[0], loc=(-850, -100))
    sy = _math(nt, 'MULTIPLY', sy.outputs[0], vb=wave_amp * 0.6, loc=(-700, -100))
    zr = _math(nt, 'ADD', sx.outputs[0], sy.outputs[0], loc=(-550, 0))
    zr = _math(nt, 'ADD', zr.outputs[0], vb=rail_z, loc=(-400, 0))
    dz = _math(nt, 'SUBTRACT', sep.outputs[2], zr.outputs[0], loc=(-250, 0))   # z - rail
    below = _math(nt, 'LESS_THAN', dz.outputs[0], vb=0.0, loc=(-100, 100))
    on_rail = _math(nt, 'ABSOLUTE', dz.outputs[0], loc=(-100, -100))
    on_rail = _math(nt, 'LESS_THAN', on_rail.outputs[0], vb=rail_h / 2, loc=(50, -100))
    # upper colour with soft vertical stripes
    if stripe:
        v = _coords(nt, wobble=0.12, wfreq=0.6)
        sep2 = _node(nt, "ShaderNodeSeparateXYZ", (-300, 400))
        nt.links.new(v, sep2.inputs[0])
        # stripes run along whichever wall: use x+y so both wall directions get bands
        s = _math(nt, 'ADD', sep2.outputs[0], sep2.outputs[1], loc=(-150, 400))
        s = _math(nt, 'DIVIDE', s.outputs[0], vb=stripe_w * 2, loc=(0, 400))
        s = _math(nt, 'FRACT', s.outputs[0], loc=(150, 400))
        r = _ramp(nt, [(0.0, col(upper)), (0.5, col(stripe))], (300, 400))
        nt.links.new(s.outputs[0], r.inputs[0])
        up = r.outputs[0]
    else:
        rgb = _node(nt, "ShaderNodeRGB", (300, 400))
        rgb.outputs[0].default_value = col(upper)
        up = rgb.outputs[0]
    mix1 = _node(nt, "ShaderNodeMix", (200, 0), data_type='RGBA')
    nt.links.new(below.outputs[0], mix1.inputs["Factor"])
    nt.links.new(up, mix1.inputs[6])
    mix1.inputs[7].default_value = col(lower)
    mix2 = _node(nt, "ShaderNodeMix", (350, 0), data_type='RGBA')
    nt.links.new(on_rail.outputs[0], mix2.inputs["Factor"])
    nt.links.new(mix1.outputs[2], mix2.inputs[6])
    mix2.inputs[7].default_value = col(rail)
    p = _principled(nt, None, 0.55, 0.05)
    nt.links.new(mix2.outputs[2], p.inputs["Base Color"])
    if holes:
        nt.links.new(_holes_alpha(nt, holes), p.inputs["Alpha"])
    return _finish(nt, out, p, name, m)


def gradient(name, c_bottom, c_top, z0=0.0, z1=1.0, rough=0.4, coat=0.2):
    """Colour blending from c_bottom at z0 to c_top at z1 (object space)."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-800, 0))
    sep = _node(nt, "ShaderNodeSeparateXYZ", (-600, 0))
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    mr = _node(nt, "ShaderNodeMapRange", (-400, 0))
    mr.inputs["From Min"].default_value = z0
    mr.inputs["From Max"].default_value = z1
    nt.links.new(sep.outputs[2], mr.inputs["Value"])
    r = _ramp(nt, [(0.0, col(c_bottom)), (1.0, col(c_top))], (-200, 0), interp='EASE')
    nt.links.new(mr.outputs[0], r.inputs[0])
    p = _principled(nt, None, rough, coat)
    nt.links.new(r.outputs[0], p.inputs["Base Color"])
    return _finish(nt, out, p, name, m)


def swirl(name, c1, c2, scale=3.0, rough=0.3, coat=0.4, holes=None):
    """Marbled two-colour swirl (for the table top / fruit)."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    v = _coords(nt, wobble=0.8, wfreq=scale * 0.4)
    wv = _node(nt, "ShaderNodeTexWave", (-200, 0))
    wv.wave_type = 'RINGS'
    wv.inputs["Scale"].default_value = scale
    wv.inputs["Distortion"].default_value = 3.0
    wv.inputs["Detail"].default_value = 2.0
    nt.links.new(v, wv.inputs["Vector"])
    r = _ramp(nt, [(0.35, col(c1)), (0.65, col(c2))], (0, 0), interp='LINEAR')
    nt.links.new(wv.outputs["Fac"], r.inputs[0])
    p = _principled(nt, None, rough, coat)
    nt.links.new(r.outputs[0], p.inputs["Base Color"])
    if holes:
        nt.links.new(_holes_alpha(nt, holes), p.inputs["Alpha"])
    return _finish(nt, out, p, name, m)


def fuzz(name, color, rough=0.9):
    """Soft matte with sheen for truffula pom-poms / rug."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    p = _principled(nt, col(color), rough, 0.0, sheen=0.8)
    p.inputs["Sheen Tint"].default_value = col(color)
    return _finish(nt, out, p, name, m)
