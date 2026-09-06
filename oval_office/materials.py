"""Procedural PBR materials for the Oval Office (no external textures needed)."""
import math
import bpy

_cache = {}


def _new(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)
    return m, nt, out


def _node(nt, kind, loc=(0, 0), **props):
    n = nt.nodes.new(kind)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def _ramp(nt, stops, loc=(0, 0), interp='LINEAR'):
    r = nt.nodes.new("ShaderNodeValToRGB")
    r.location = loc
    r.color_ramp.interpolation = interp
    el = r.color_ramp.elements
    el[0].position, el[0].color = stops[0]
    el[1].position, el[1].color = stops[-1]
    for pos, col in stops[1:-1]:
        e = el.new(pos)
        e.color = col
    return r


def _principled(nt, loc=(300, 0), **inputs):
    p = nt.nodes.new("ShaderNodeBsdfPrincipled")
    p.location = loc
    for k, v in inputs.items():
        p.inputs[k].default_value = v
    return p


def _math(nt, op, a=None, b=None, loc=(0, 0), val_b=None, val_a=None, clamp=False):
    n = nt.nodes.new("ShaderNodeMath")
    n.operation = op
    n.location = loc
    n.use_clamp = clamp
    if a is not None:
        nt.links.new(a, n.inputs[0])
    if b is not None:
        nt.links.new(b, n.inputs[1])
    if val_a is not None:
        n.inputs[0].default_value = val_a
    if val_b is not None:
        n.inputs[1].default_value = val_b
    return n


def rgb(r, g, b, a=1.0):
    return (r, g, b, a)


def hexc(h, a=1.0):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)) + (a,)


def srgb_to_linear(c):
    def f(x):
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return tuple(f(x) for x in c[:3]) + (c[3] if len(c) > 3 else 1.0,)


def col(h):
    """Hex sRGB -> linear RGBA (Blender node inputs are linear)."""
    return srgb_to_linear(hexc(h))


# ------------------------------------------------------------------ simple
def simple(name, color, rough=0.5, metallic=0.0, sheen=0.0, coat=0.0, spec=0.5, emission=None, emit_str=0.0, alpha=1.0):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    p = _principled(nt, **{"Base Color": color, "Roughness": rough, "Metallic": metallic,
                           "Sheen Weight": sheen, "Coat Weight": coat, "Specular IOR Level": spec, "Alpha": alpha})
    if emission is not None:
        p.inputs["Emission Color"].default_value = emission
        p.inputs["Emission Strength"].default_value = emit_str
    nt.links.new(p.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


def emission(name, color, strength):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    e = _node(nt, "ShaderNodeEmission", (300, 0))
    e.inputs["Color"].default_value = color
    e.inputs["Strength"].default_value = strength
    nt.links.new(e.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


# ------------------------------------------------------------------ wood
def wood(name, light, dark, scale=3.0, stretch=(1.0, 12.0, 1.0), rough=0.35, coat=0.15, bump=0.15, detail=6.0):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-900, 0))
    mp = _node(nt, "ShaderNodeMapping", (-700, 0))
    mp.inputs["Scale"].default_value = (scale * stretch[0], scale * stretch[1], scale * stretch[2])
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = _node(nt, "ShaderNodeTexNoise", (-500, 0))
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = detail
    nz.inputs["Roughness"].default_value = 0.6
    nt.links.new(mp.outputs[0], nz.inputs["Vector"])
    # fine grain lines
    wave = _node(nt, "ShaderNodeTexWave", (-500, -300))
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'Y'
    wave.inputs["Scale"].default_value = 10.0
    wave.inputs["Distortion"].default_value = 3.0
    wave.inputs["Detail"].default_value = 3.0
    wave.inputs["Detail Scale"].default_value = 2.0
    nt.links.new(mp.outputs[0], wave.inputs["Vector"])
    mix = _node(nt, "ShaderNodeMix", (-300, 0), data_type='FLOAT')
    mix.inputs[0].default_value = 0.65
    nt.links.new(nz.outputs["Fac"], mix.inputs[2])
    nt.links.new(wave.outputs["Fac"], mix.inputs[3])
    ramp = _ramp(nt, [(0.25, dark), (0.75, light)], (-100, 0), 'EASE')
    nt.links.new(mix.outputs[0], ramp.inputs[0])
    p = _principled(nt, **{"Roughness": rough, "Coat Weight": coat, "Coat Roughness": 0.2})
    nt.links.new(ramp.outputs[0], p.inputs["Base Color"])
    bmp = _node(nt, "ShaderNodeBump", (100, -300))
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.005
    nt.links.new(mix.outputs[0], bmp.inputs["Height"])
    nt.links.new(bmp.outputs[0], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


# ------------------------------------------------------------------ parquet sunburst floor
def parquet(name="Parquet"):
    """Oak/walnut sunburst parquet radiating from the room centre with walnut rings."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-1400, 0))
    sep = _node(nt, "ShaderNodeSeparateXYZ", (-1200, 0))
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    # stretch coords so the pattern is elliptical like the room
    xs = _math(nt, 'MULTIPLY', sep.outputs["X"], val_b=1.0, loc=(-1050, 100))
    ys = _math(nt, 'MULTIPLY', sep.outputs["Y"], val_b=0.81, loc=(-1050, -100))
    ang = _math(nt, 'ARCTAN2', ys.outputs[0], xs.outputs[0], loc=(-900, 100))
    r2 = _math(nt, 'MULTIPLY', xs.outputs[0], xs.outputs[0], loc=(-900, -200))
    r2b = _math(nt, 'MULTIPLY', ys.outputs[0], ys.outputs[0], loc=(-900, -350))
    rsum = _math(nt, 'ADD', r2.outputs[0], r2b.outputs[0], loc=(-750, -250))
    rad = _math(nt, 'SQRT', rsum.outputs[0], loc=(-600, -250))
    # wedges
    n_wedges = 40
    w = _math(nt, 'MULTIPLY', ang.outputs[0], val_b=n_wedges / math.tau, loc=(-750, 100))
    wid = _math(nt, 'FLOOR', w.outputs[0], loc=(-600, 200))
    par = _math(nt, 'MODULO', wid.outputs[0], val_b=2.0, loc=(-450, 200))
    wf = _math(nt, 'FRACT', w.outputs[0], loc=(-600, 50))
    seam = _math(nt, 'SUBTRACT', wf.outputs[0], val_b=0.5, loc=(-450, 50))
    seam_abs = _math(nt, 'ABSOLUTE', seam.outputs[0], loc=(-300, 50))
    seam_line = _math(nt, 'GREATER_THAN', seam_abs.outputs[0], val_b=0.485, loc=(-150, 50))
    # radial boards: plank breaks along the radius
    rr = _math(nt, 'MULTIPLY', rad.outputs[0], val_b=1 / 0.55, loc=(-450, -250))
    rf = _math(nt, 'FRACT', rr.outputs[0], loc=(-300, -250))
    ring_line = _math(nt, 'LESS_THAN', rf.outputs[0], val_b=0.03, loc=(-150, -250))
    # walnut border rings every 1.1m (thin), plus a wide outer walnut band
    rb = _math(nt, 'MULTIPLY', rad.outputs[0], val_b=1 / 1.1, loc=(-450, -450))
    rbf = _math(nt, 'FRACT', rb.outputs[0], loc=(-300, -450))
    border = _math(nt, 'LESS_THAN', rbf.outputs[0], val_b=0.08, loc=(-150, -450))
    # grain noise in polar coords (radial grain)
    comb = _node(nt, "ShaderNodeCombineXYZ", (-450, -600))
    nt.links.new(rad.outputs[0], comb.inputs[0])
    a2 = _math(nt, 'MULTIPLY', ang.outputs[0], val_b=6.0, loc=(-600, -650))
    nt.links.new(a2.outputs[0], comb.inputs[1])
    nz = _node(nt, "ShaderNodeTexNoise", (-300, -600))
    nz.inputs["Scale"].default_value = 9.0
    nz.inputs["Detail"].default_value = 8.0
    nz.inputs["Roughness"].default_value = 0.7
    nt.links.new(comb.outputs[0], nz.inputs["Vector"])
    mpn = _node(nt, "ShaderNodeMapping", (-450, -800))
    mpn.inputs["Scale"].default_value = (1.0, 40.0, 1.0)
    nt.links.new(comb.outputs[0], mpn.inputs["Vector"])
    nz2 = _node(nt, "ShaderNodeTexNoise", (-300, -800))
    nz2.inputs["Scale"].default_value = 1.5
    nz2.inputs["Detail"].default_value = 4.0
    nt.links.new(mpn.outputs[0], nz2.inputs["Vector"])
    gmix = _node(nt, "ShaderNodeMix", (-100, -700), data_type='FLOAT')
    gmix.inputs[0].default_value = 0.5
    nt.links.new(nz.outputs["Fac"], gmix.inputs[2])
    nt.links.new(nz2.outputs["Fac"], gmix.inputs[3])
    oak = _ramp(nt, [(0.3, col("#9a6a38")), (0.55, col("#c49a5c")), (0.8, col("#d9b57a"))], (100, -500))
    oak2 = _ramp(nt, [(0.3, col("#8a5a2c")), (0.55, col("#b5864a")), (0.8, col("#caa063"))], (100, -750))
    wal = _ramp(nt, [(0.3, col("#3a2414")), (0.6, col("#5a3a22")), (0.85, col("#6d4a2c"))], (100, -1000))
    for r in (oak, oak2, wal):
        nt.links.new(gmix.outputs[0], r.inputs[0])
    m1 = _node(nt, "ShaderNodeMix", (350, -500), data_type='RGBA')
    nt.links.new(par.outputs[0], m1.inputs[0])
    nt.links.new(oak.outputs[0], m1.inputs[6])
    nt.links.new(oak2.outputs[0], m1.inputs[7])
    m2 = _node(nt, "ShaderNodeMix", (500, -500), data_type='RGBA')
    nt.links.new(border.outputs[0], m2.inputs[0])
    nt.links.new(m1.outputs[2], m2.inputs[6])
    nt.links.new(wal.outputs[0], m2.inputs[7])
    lines = _math(nt, 'MAXIMUM', seam_line.outputs[0], ring_line.outputs[0], loc=(100, 100))
    m3 = _node(nt, "ShaderNodeMix", (650, -500), data_type='RGBA')
    nt.links.new(lines.outputs[0], m3.inputs[0])
    nt.links.new(m2.outputs[2], m3.inputs[6])
    m3.inputs[7].default_value = col("#2a1a0e")
    p = _principled(nt, (850, 0), **{"Roughness": 0.28, "Coat Weight": 0.5, "Coat Roughness": 0.12})
    nt.links.new(m3.outputs[2], p.inputs["Base Color"])
    bmp = _node(nt, "ShaderNodeBump", (650, -100))
    bmp.inputs["Strength"].default_value = 0.25
    bmp.inputs["Distance"].default_value = 0.01
    hmix = _math(nt, 'SUBTRACT', gmix.outputs[0], lines.outputs[0], loc=(450, -100))
    nt.links.new(hmix.outputs[0], bmp.inputs["Height"])
    nt.links.new(bmp.outputs[0], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    out.location = (1100, 0)
    _cache[name] = m
    return m


# ------------------------------------------------------------------ rug (Reagan sunbeam rug)
def rug(name="Rug"):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-1200, 0))
    sep = _node(nt, "ShaderNodeSeparateXYZ", (-1000, 0))
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    ang = _math(nt, 'ARCTAN2', sep.outputs["Y"], sep.outputs["X"], loc=(-800, 100))
    x2 = _math(nt, 'MULTIPLY', sep.outputs["X"], sep.outputs["X"], loc=(-800, -100))
    y2 = _math(nt, 'MULTIPLY', sep.outputs["Y"], sep.outputs["Y"], loc=(-800, -250))
    rad = _math(nt, 'SQRT', _math(nt, 'ADD', x2.outputs[0], y2.outputs[0], loc=(-650, -150)).outputs[0], loc=(-500, -150))
    yb = _math(nt, 'MULTIPLY', sep.outputs["Y"], val_b=3.5 / 4.5, loc=(-800, -1000))
    yb2 = _math(nt, 'MULTIPLY', yb.outputs[0], yb.outputs[0], loc=(-650, -1000))
    radb = _math(nt, 'SQRT', _math(nt, 'ADD', x2.outputs[0], yb2.outputs[0], loc=(-500, -1000)).outputs[0], loc=(-350, -1000))
    # sun rays: soft alternating wedges
    w = _math(nt, 'MULTIPLY', ang.outputs[0], val_b=36 / math.tau, loc=(-650, 100))
    wf = _math(nt, 'FRACT', w.outputs[0], loc=(-500, 100))
    tri = _math(nt, 'ABSOLUTE', _math(nt, 'SUBTRACT', wf.outputs[0], val_b=0.5, loc=(-350, 100)).outputs[0], loc=(-200, 100))
    # fade rays with radius (stronger toward edge)
    fade = _math(nt, 'MULTIPLY', radb.outputs[0], val_b=0.35, loc=(-350, -150), clamp=True)
    rays = _math(nt, 'MULTIPLY', tri.outputs[0], fade.outputs[0], loc=(-50, 0))
    cream = _ramp(nt, [(0.0, col("#e8dcc0")), (0.5, col("#d9c39a"))], (100, 100))
    nt.links.new(rays.outputs[0], cream.inputs[0])
    # centre medallion field (blue) + gold ring
    inner = _math(nt, 'LESS_THAN', rad.outputs[0], val_b=0.95, loc=(-200, -300))
    ring = _math(nt, 'LESS_THAN', rad.outputs[0], val_b=1.05, loc=(-200, -400))
    ring_only = _math(nt, 'SUBTRACT', ring.outputs[0], inner.outputs[0], loc=(-50, -400))
    # star ring at r~0.8
    sang = _math(nt, 'MULTIPLY', ang.outputs[0], val_b=50 / math.tau, loc=(-650, -600))
    sf = _math(nt, 'SUBTRACT', _math(nt, 'FRACT', sang.outputs[0], loc=(-500, -600)).outputs[0], val_b=0.5, loc=(-350, -600))
    sd = _math(nt, 'MULTIPLY', sf.outputs[0], val_b=0.1, loc=(-200, -600))
    rd = _math(nt, 'SUBTRACT', rad.outputs[0], val_b=0.82, loc=(-200, -700))
    d2 = _math(nt, 'ADD', _math(nt, 'MULTIPLY', sd.outputs[0], sd.outputs[0], loc=(-50, -600)).outputs[0],
               _math(nt, 'MULTIPLY', rd.outputs[0], rd.outputs[0], loc=(-50, -700)).outputs[0], loc=(100, -650))
    star = _math(nt, 'LESS_THAN', d2.outputs[0], val_b=0.0009, loc=(250, -650))
    # outer border band
    border = _math(nt, 'GREATER_THAN', radb.outputs[0], val_b=3.22, loc=(-200, -800))
    # weave bump
    nz = _node(nt, "ShaderNodeTexNoise", (100, -900))
    nz.inputs["Scale"].default_value = 400.0
    nz.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    mixb = _node(nt, "ShaderNodeMix", (300, 100), data_type='RGBA')
    nt.links.new(inner.outputs[0], mixb.inputs[0])
    nt.links.new(cream.outputs[0], mixb.inputs[6])
    mixb.inputs[7].default_value = col("#1e2f5e")
    mixr = _node(nt, "ShaderNodeMix", (450, 100), data_type='RGBA')
    nt.links.new(ring_only.outputs[0], mixr.inputs[0])
    nt.links.new(mixb.outputs[2], mixr.inputs[6])
    mixr.inputs[7].default_value = col("#c9a44a")
    mixs = _node(nt, "ShaderNodeMix", (600, 100), data_type='RGBA')
    nt.links.new(star.outputs[0], mixs.inputs[0])
    nt.links.new(mixr.outputs[2], mixs.inputs[6])
    mixs.inputs[7].default_value = col("#f4f0e6")
    mixo = _node(nt, "ShaderNodeMix", (750, 100), data_type='RGBA')
    nt.links.new(border.outputs[0], mixo.inputs[0])
    nt.links.new(mixs.outputs[2], mixo.inputs[6])
    mixo.inputs[7].default_value = col("#b89a5e")
    p = _principled(nt, (950, 0), **{"Roughness": 0.9, "Sheen Weight": 0.6, "Specular IOR Level": 0.2})
    nt.links.new(mixo.outputs[2], p.inputs["Base Color"])
    bmp = _node(nt, "ShaderNodeBump", (750, -300))
    bmp.inputs["Strength"].default_value = 0.3
    bmp.inputs["Distance"].default_value = 0.002
    nt.links.new(nz.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs[0], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    out.location = (1200, 0)
    _cache[name] = m
    return m


# ------------------------------------------------------------------ marble / plaster / paint
def marble(name="Marble", base="#f2efe8", vein="#8d8a86", rough=0.12):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-900, 0))
    mp = _node(nt, "ShaderNodeMapping", (-700, 0))
    mp.inputs["Scale"].default_value = (1.0, 2.5, 1.0)
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nz = _node(nt, "ShaderNodeTexNoise", (-500, 0))
    nz.inputs["Scale"].default_value = 2.2
    nz.inputs["Detail"].default_value = 10.0
    nz.inputs["Roughness"].default_value = 0.75
    nz.inputs["Distortion"].default_value = 0.6
    nt.links.new(mp.outputs[0], nz.inputs["Vector"])
    wave = _node(nt, "ShaderNodeTexWave", (-500, -300))
    wave.inputs["Scale"].default_value = 1.4
    wave.inputs["Distortion"].default_value = 12.0
    wave.inputs["Detail"].default_value = 3.0
    nt.links.new(mp.outputs[0], wave.inputs["Vector"])
    mix = _node(nt, "ShaderNodeMix", (-300, 0), data_type='FLOAT')
    mix.inputs[0].default_value = 0.6
    nt.links.new(nz.outputs["Fac"], mix.inputs[2])
    nt.links.new(wave.outputs["Fac"], mix.inputs[3])
    ramp = _ramp(nt, [(0.42, col(base)), (0.5, col(vein)), (0.56, col(base))], (-100, 0))
    nt.links.new(mix.outputs[0], ramp.inputs[0])
    p = _principled(nt, **{"Roughness": rough, "Coat Weight": 0.3, "Specular IOR Level": 0.6})
    nt.links.new(ramp.outputs[0], p.inputs["Base Color"])
    nt.links.new(p.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


def paint(name, color, rough=0.55, bump=0.03, spec=0.4):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-600, -300))
    nz = _node(nt, "ShaderNodeTexNoise", (-400, -300))
    nz.inputs["Scale"].default_value = 120.0
    nz.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    bmp = _node(nt, "ShaderNodeBump", (0, -300))
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = 0.005
    nt.links.new(nz.outputs["Fac"], bmp.inputs["Height"])
    p = _principled(nt, **{"Base Color": color, "Roughness": rough, "Specular IOR Level": spec})
    nt.links.new(bmp.outputs[0], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


def fabric(name, color, stripe=None, stripe_scale=30.0, rough=0.85, sheen=0.5):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-900, 0))
    nz = _node(nt, "ShaderNodeTexNoise", (-600, -300))
    nz.inputs["Scale"].default_value = 300.0
    nz.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    p = _principled(nt, **{"Base Color": color, "Roughness": rough, "Sheen Weight": sheen, "Specular IOR Level": 0.3})
    if stripe is not None:
        wave = _node(nt, "ShaderNodeTexWave", (-600, 0))
        wave.wave_type = 'BANDS'
        wave.bands_direction = 'X'
        wave.wave_profile = 'SAW'
        wave.inputs["Scale"].default_value = stripe_scale
        nt.links.new(tc.outputs["Object"], wave.inputs["Vector"])
        ramp = _ramp(nt, [(0.0, color), (0.45, color), (0.5, stripe), (0.75, stripe), (0.8, color)], (-300, 0), 'CONSTANT')
        nt.links.new(wave.outputs["Fac"], ramp.inputs[0])
        nt.links.new(ramp.outputs[0], p.inputs["Base Color"])
    bmp = _node(nt, "ShaderNodeBump", (0, -300))
    bmp.inputs["Strength"].default_value = 0.25
    bmp.inputs["Distance"].default_value = 0.002
    nt.links.new(nz.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs[0], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


def leather(name="Leather", color=None, rough=0.42):
    color = color or col("#3b2416")
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-900, 0))
    vor = _node(nt, "ShaderNodeTexVoronoi", (-600, -300))
    vor.inputs["Scale"].default_value = 180.0
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    nz = _node(nt, "ShaderNodeTexNoise", (-600, -600))
    nz.inputs["Scale"].default_value = 20.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = _ramp(nt, [(0.35, tuple(c * 0.7 for c in color[:3]) + (1,)), (0.65, color)], (-300, 0))
    nt.links.new(nz.outputs["Fac"], ramp.inputs[0])
    p = _principled(nt, **{"Roughness": rough, "Coat Weight": 0.25, "Coat Roughness": 0.3, "Specular IOR Level": 0.5})
    nt.links.new(ramp.outputs[0], p.inputs["Base Color"])
    bmp = _node(nt, "ShaderNodeBump", (0, -300))
    bmp.inputs["Strength"].default_value = 0.12
    bmp.inputs["Distance"].default_value = 0.002
    nt.links.new(vor.outputs["Distance"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs[0], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


def glass(name="Glass", tint=(1, 1, 1, 1), rough=0.0):
    """Window glass: transparent to shadow rays so sunlight enters cleanly."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    g = _node(nt, "ShaderNodeBsdfGlass", (0, 0))
    g.inputs["Color"].default_value = tint
    g.inputs["Roughness"].default_value = rough
    g.inputs["IOR"].default_value = 1.5
    tr = _node(nt, "ShaderNodeBsdfTransparent", (0, -200))
    lp = _node(nt, "ShaderNodeLightPath", (0, 300))
    mix = _node(nt, "ShaderNodeMixShader", (300, 0))
    nt.links.new(lp.outputs["Is Shadow Ray"], mix.inputs[0])
    nt.links.new(g.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


def lampshade(name="LampShade", color=None):
    color = color or col("#f3e9d2")
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    d = _node(nt, "ShaderNodeBsdfDiffuse", (0, 100))
    d.inputs["Color"].default_value = color
    t = _node(nt, "ShaderNodeBsdfTranslucent", (0, -100))
    t.inputs["Color"].default_value = color
    mix = _node(nt, "ShaderNodeMixShader", (300, 0))
    mix.inputs[0].default_value = 0.55
    nt.links.new(d.outputs[0], mix.inputs[1])
    nt.links.new(t.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


def fire(name="Fire"):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-600, 0))
    nz = _node(nt, "ShaderNodeTexNoise", (-400, 0))
    nz.inputs["Scale"].default_value = 6.0
    nz.inputs["Detail"].default_value = 4.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = _ramp(nt, [(0.3, (1.0, 0.15, 0.0, 1)), (0.55, (1.0, 0.45, 0.05, 1)), (0.75, (1.0, 0.85, 0.4, 1))], (-200, 0))
    nt.links.new(nz.outputs["Fac"], ramp.inputs[0])
    e = _node(nt, "ShaderNodeEmission", (100, 0))
    e.inputs["Strength"].default_value = 25.0
    nt.links.new(ramp.outputs[0], e.inputs["Color"])
    tr = _node(nt, "ShaderNodeBsdfTransparent", (100, -200))
    mix = _node(nt, "ShaderNodeMixShader", (350, 0))
    # transparent toward the top of the flame (generated Z)
    sep = _node(nt, "ShaderNodeSeparateXYZ", (-400, -300))
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    fz = _math(nt, 'MULTIPLY', sep.outputs["Z"], nz.outputs["Fac"], loc=(-100, -300))
    fz2 = _math(nt, 'MULTIPLY', fz.outputs[0], val_b=1.6, loc=(50, -300), clamp=True)
    nt.links.new(fz2.outputs[0], mix.inputs[0])
    nt.links.new(e.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


# ------------------------------------------------------------------ flags
def us_flag(name="USFlag"):
    """Stars and stripes from Generated coordinates: X across width (hoist at x=0), Z up."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-1000, 0))
    sep = _node(nt, "ShaderNodeSeparateXYZ", (-800, 0))
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    st = _math(nt, 'MULTIPLY', sep.outputs["Z"], val_b=13.0, loc=(-600, 200))
    stf = _math(nt, 'FLOOR', st.outputs[0], loc=(-450, 200))
    par = _math(nt, 'MODULO', stf.outputs[0], val_b=2.0, loc=(-300, 200))
    # canton: x < 0.4 and z > 6/13 (top)
    cx = _math(nt, 'LESS_THAN', sep.outputs["X"], val_b=0.4, loc=(-600, 0))
    cz = _math(nt, 'GREATER_THAN', sep.outputs["Z"], val_b=7 / 13, loc=(-600, -100))
    canton = _math(nt, 'MULTIPLY', cx.outputs[0], cz.outputs[0], loc=(-450, -50))
    # stars grid inside canton
    gx = _math(nt, 'FRACT', _math(nt, 'MULTIPLY', sep.outputs["X"], val_b=11 / 0.4, loc=(-600, -300)).outputs[0], loc=(-450, -300))
    gz = _math(nt, 'FRACT', _math(nt, 'MULTIPLY', sep.outputs["Z"], val_b=9 / (6 / 13), loc=(-600, -450)).outputs[0], loc=(-450, -450))
    dx = _math(nt, 'SUBTRACT', gx.outputs[0], val_b=0.5, loc=(-300, -300))
    dz = _math(nt, 'SUBTRACT', gz.outputs[0], val_b=0.5, loc=(-300, -450))
    d2 = _math(nt, 'ADD', _math(nt, 'MULTIPLY', dx.outputs[0], dx.outputs[0], loc=(-150, -300)).outputs[0],
               _math(nt, 'MULTIPLY', dz.outputs[0], dz.outputs[0], loc=(-150, -450)).outputs[0], loc=(0, -350))
    star = _math(nt, 'LESS_THAN', d2.outputs[0], val_b=0.06, loc=(150, -350))
    starc = _math(nt, 'MULTIPLY', star.outputs[0], canton.outputs[0], loc=(300, -350))
    stripes = _node(nt, "ShaderNodeMix", (-100, 200), data_type='RGBA')
    nt.links.new(par.outputs[0], stripes.inputs[0])
    stripes.inputs[6].default_value = col("#f5f5f5")   # bottom stripe red? index0 -> even -> white; fine
    stripes.inputs[7].default_value = col("#b22234")
    mc = _node(nt, "ShaderNodeMix", (150, 100), data_type='RGBA')
    nt.links.new(canton.outputs[0], mc.inputs[0])
    nt.links.new(stripes.outputs[2], mc.inputs[6])
    mc.inputs[7].default_value = col("#3c3b6e")
    ms = _node(nt, "ShaderNodeMix", (400, 100), data_type='RGBA')
    nt.links.new(starc.outputs[0], ms.inputs[0])
    nt.links.new(mc.outputs[2], ms.inputs[6])
    ms.inputs[7].default_value = col("#ffffff")
    p = _principled(nt, (650, 0), **{"Roughness": 0.7, "Sheen Weight": 0.4, "Specular IOR Level": 0.3})
    nt.links.new(ms.outputs[2], p.inputs["Base Color"])
    nt.links.new(p.outputs[0], out.inputs[0])
    out.location = (900, 0)
    _cache[name] = m
    return m


def pres_flag(name="PresFlag"):
    """Presidential flag: dark blue field, central seal ring with white stars, gold emblem."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-1000, 0))
    sep = _node(nt, "ShaderNodeSeparateXYZ", (-800, 0))
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    dx = _math(nt, 'SUBTRACT', sep.outputs["X"], val_b=0.5, loc=(-600, 100))
    dz = _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', sep.outputs["Z"], val_b=0.5, loc=(-600, -100)).outputs[0], val_b=1.35, loc=(-450, -100))
    r = _math(nt, 'SQRT', _math(nt, 'ADD', _math(nt, 'MULTIPLY', dx.outputs[0], dx.outputs[0], loc=(-450, 100)).outputs[0],
                                 _math(nt, 'MULTIPLY', dz.outputs[0], dz.outputs[0], loc=(-450, 0)).outputs[0], loc=(-300, 50)).outputs[0], loc=(-150, 50))
    ring = _math(nt, 'SUBTRACT', _math(nt, 'LESS_THAN', r.outputs[0], val_b=0.36, loc=(0, 100)).outputs[0],
                 _math(nt, 'LESS_THAN', r.outputs[0], val_b=0.34, loc=(0, 0)).outputs[0], loc=(150, 50))
    ang = _math(nt, 'ARCTAN2', dz.outputs[0], dx.outputs[0], loc=(-300, -300))
    sf = _math(nt, 'SUBTRACT', _math(nt, 'FRACT', _math(nt, 'MULTIPLY', ang.outputs[0], val_b=50 / math.tau, loc=(-150, -300)).outputs[0], loc=(0, -300)).outputs[0], val_b=0.5, loc=(150, -300))
    sd = _math(nt, 'MULTIPLY', sf.outputs[0], val_b=0.045, loc=(300, -300))
    rd = _math(nt, 'SUBTRACT', r.outputs[0], val_b=0.30, loc=(300, -400))
    d2 = _math(nt, 'ADD', _math(nt, 'MULTIPLY', sd.outputs[0], sd.outputs[0], loc=(450, -300)).outputs[0],
               _math(nt, 'MULTIPLY', rd.outputs[0], rd.outputs[0], loc=(450, -400)).outputs[0], loc=(600, -350))
    star = _math(nt, 'LESS_THAN', d2.outputs[0], val_b=0.00016, loc=(750, -350))
    emblem = _math(nt, 'LESS_THAN', r.outputs[0], val_b=0.2, loc=(0, -600))
    nz = _node(nt, "ShaderNodeTexNoise", (0, -800))
    nz.inputs["Scale"].default_value = 30.0
    nt.links.new(tc.outputs["Generated"], nz.inputs["Vector"])
    emb2 = _math(nt, 'MULTIPLY', emblem.outputs[0], _math(nt, 'GREATER_THAN', nz.outputs["Fac"], val_b=0.5, loc=(200, -800)).outputs[0], loc=(400, -650))
    base = _node(nt, "ShaderNodeMix", (300, 100), data_type='RGBA')
    nt.links.new(ring.outputs[0], base.inputs[0])
    base.inputs[6].default_value = col("#1b2a5c")
    base.inputs[7].default_value = col("#e6c15a")
    m2 = _node(nt, "ShaderNodeMix", (500, 100), data_type='RGBA')
    nt.links.new(star.outputs[0], m2.inputs[0])
    nt.links.new(base.outputs[2], m2.inputs[6])
    m2.inputs[7].default_value = col("#ffffff")
    m3 = _node(nt, "ShaderNodeMix", (700, 100), data_type='RGBA')
    nt.links.new(emb2.outputs[0], m3.inputs[0])
    nt.links.new(m2.outputs[2], m3.inputs[6])
    m3.inputs[7].default_value = col("#e6c15a")
    p = _principled(nt, (900, 0), **{"Roughness": 0.7, "Sheen Weight": 0.4, "Specular IOR Level": 0.3})
    nt.links.new(m3.outputs[2], p.inputs["Base Color"])
    nt.links.new(p.outputs[0], out.inputs[0])
    out.location = (1150, 0)
    _cache[name] = m
    return m


# ------------------------------------------------------------------ paintings
def painting(name, kind="portrait", seed=1, palette=None):
    """Impressionistic procedural canvas: portrait (dark bg, figure) or landscape (sky/land bands)."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-1200, 0))
    sep = _node(nt, "ShaderNodeSeparateXYZ", (-1000, 0))
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nz = _node(nt, "ShaderNodeTexNoise", (-1000, -400))
    nz.inputs["Scale"].default_value = 12.0 + seed
    nz.inputs["Detail"].default_value = 6.0
    nz.inputs["Distortion"].default_value = 1.5
    nz.noise_dimensions = '4D'
    nz.inputs["W"].default_value = seed * 3.1
    nt.links.new(tc.outputs["Generated"], nz.inputs["Vector"])
    brush = _node(nt, "ShaderNodeTexNoise", (-1000, -700))
    brush.inputs["Scale"].default_value = 90.0
    brush.inputs["Detail"].default_value = 2.0
    nt.links.new(tc.outputs["Generated"], brush.inputs["Vector"])
    if kind == "portrait":
        pal = palette or [col("#1a1410"), col("#3a2a1c"), col("#5b4630"), col("#8a6a48")]
        bg = _ramp(nt, [(0.3, pal[0]), (0.5, pal[1]), (0.7, pal[2])], (-700, 0))
        nt.links.new(nz.outputs["Fac"], bg.inputs[0])
        # head ellipse
        hx = _math(nt, 'SUBTRACT', sep.outputs["X"], val_b=0.5, loc=(-800, 300))
        hz = _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', sep.outputs["Z"], val_b=0.68, loc=(-800, 400)).outputs[0], val_b=0.8, loc=(-650, 400))
        hd = _math(nt, 'ADD', _math(nt, 'MULTIPLY', hx.outputs[0], hx.outputs[0], loc=(-500, 300)).outputs[0],
                   _math(nt, 'MULTIPLY', hz.outputs[0], hz.outputs[0], loc=(-500, 400)).outputs[0], loc=(-350, 350))
        head = _math(nt, 'LESS_THAN', hd.outputs[0], val_b=0.0075, loc=(-200, 350))
        hair_z = _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', sep.outputs["Z"], val_b=0.71, loc=(-800, 1200)).outputs[0], val_b=0.9, loc=(-650, 1200))
        hair_d = _math(nt, 'ADD', _math(nt, 'MULTIPLY', hx.outputs[0], hx.outputs[0], loc=(-500, 1150)).outputs[0],
                       _math(nt, 'MULTIPLY', hair_z.outputs[0], hair_z.outputs[0], loc=(-500, 1250)).outputs[0], loc=(-350, 1200))
        hair = _math(nt, 'MULTIPLY', _math(nt, 'LESS_THAN', hair_d.outputs[0], val_b=0.012, loc=(-200, 1200)).outputs[0],
                     _math(nt, 'GREATER_THAN', sep.outputs["Z"], val_b=0.69, loc=(-200, 1300)).outputs[0], loc=(-50, 1200))
        # torso: below head, wide
        tx = _math(nt, 'ABSOLUTE', hx.outputs[0], loc=(-800, 600))
        tz = _math(nt, 'LESS_THAN', sep.outputs["Z"], val_b=0.56, loc=(-800, 700))
        tw = _math(nt, 'LESS_THAN', tx.outputs[0], _math(nt, 'MULTIPLY', _math(nt, 'SUBTRACT', val_a=0.62, b=sep.outputs["Z"], loc=(-800, 800)).outputs[0], val_b=0.7, loc=(-650, 800)).outputs[0], loc=(-500, 700))
        torso = _math(nt, 'MULTIPLY', tz.outputs[0], tw.outputs[0], loc=(-350, 700))
        # cravat
        cx = _math(nt, 'LESS_THAN', tx.outputs[0], val_b=0.07, loc=(-500, 900))
        cz = _math(nt, 'MULTIPLY', _math(nt, 'LESS_THAN', sep.outputs["Z"], val_b=0.58, loc=(-650, 950)).outputs[0],
                   _math(nt, 'GREATER_THAN', sep.outputs["Z"], val_b=0.46, loc=(-650, 1050)).outputs[0], loc=(-500, 1000))
        cravat = _math(nt, 'MULTIPLY', cx.outputs[0], cz.outputs[0], loc=(-350, 950))
        m1 = _node(nt, "ShaderNodeMix", (-100, 0), data_type='RGBA')
        nt.links.new(torso.outputs[0], m1.inputs[0])
        nt.links.new(bg.outputs[0], m1.inputs[6])
        m1.inputs[7].default_value = col("#1c1714")
        m2 = _node(nt, "ShaderNodeMix", (100, 0), data_type='RGBA')
        nt.links.new(cravat.outputs[0], m2.inputs[0])
        nt.links.new(m1.outputs[2], m2.inputs[6])
        m2.inputs[7].default_value = col("#e9e2d2")
        skin = _ramp(nt, [(0.3, col("#8a6448")), (0.7, col("#c9a07e"))], (-100, -300))
        shade_x = _math(nt, 'ADD', _math(nt, 'MULTIPLY', hx.outputs[0], val_b=3.0, loc=(-300, -500)).outputs[0], val_b=0.55, loc=(-150, -500), clamp=True)
        sk = _math(nt, 'MULTIPLY', brush.outputs["Fac"], shade_x.outputs[0], loc=(-250, -300))
        nt.links.new(sk.outputs[0], skin.inputs[0])
        mh = _node(nt, "ShaderNodeMix", (200, 0), data_type='RGBA')
        nt.links.new(hair.outputs[0], mh.inputs[0])
        nt.links.new(m2.outputs[2], mh.inputs[6])
        mh.inputs[7].default_value = col("#b9b3a8")
        m3 = _node(nt, "ShaderNodeMix", (350, 0), data_type='RGBA')
        nt.links.new(head.outputs[0], m3.inputs[0])
        nt.links.new(mh.outputs[2], m3.inputs[6])
        nt.links.new(skin.outputs[0], m3.inputs[7])
        color_out = m3.outputs[2]
    else:
        pal = palette or [col("#c9d6e3"), col("#8fa7c2"), col("#6e7f5a"), col("#3f4a2e")]
        # horizon band from Z, perturbed by noise
        zz = _math(nt, 'ADD', sep.outputs["Z"], _math(nt, 'MULTIPLY', nz.outputs["Fac"], val_b=0.25, loc=(-800, -200)).outputs[0], loc=(-650, 0))
        ramp = _ramp(nt, [(0.35, pal[3]), (0.55, pal[2]), (0.62, pal[1]), (0.8, pal[0])], (-450, 0))
        nt.links.new(zz.outputs[0], ramp.inputs[0])
        color_out = ramp.outputs[0]
    # brushstroke darkening
    mixb = _node(nt, "ShaderNodeMix", (500, 0), data_type='RGBA', blend_type='MULTIPLY')
    mixb.inputs[0].default_value = 0.25
    nt.links.new(color_out, mixb.inputs[6])
    bramp = _ramp(nt, [(0.3, (0.6, 0.6, 0.6, 1)), (0.7, (1, 1, 1, 1))], (300, -400))
    nt.links.new(brush.outputs["Fac"], bramp.inputs[0])
    nt.links.new(bramp.outputs[0], mixb.inputs[7])
    p = _principled(nt, (750, 0), **{"Roughness": 0.45, "Coat Weight": 0.4, "Coat Roughness": 0.25})
    nt.links.new(mixb.outputs[2], p.inputs["Base Color"])
    bmp = _node(nt, "ShaderNodeBump", (550, -300))
    bmp.inputs["Strength"].default_value = 0.3
    bmp.inputs["Distance"].default_value = 0.003
    nt.links.new(brush.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs[0], p.inputs["Normal"])
    nt.links.new(p.outputs[0], out.inputs[0])
    out.location = (1000, 0)
    _cache[name] = m
    return m


def books(name="Books"):
    """Random per-object book colours via Object Info > Random."""
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-1000, 0))
    sep = _node(nt, "ShaderNodeSeparateXYZ", (-800, 0))
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    sx = _math(nt, 'SNAP', sep.outputs["X"], val_b=0.033, loc=(-650, 100))
    sz = _math(nt, 'SNAP', sep.outputs["Z"], val_b=0.38, loc=(-650, -100))
    comb = _node(nt, "ShaderNodeCombineXYZ", (-500, 0))
    nt.links.new(sx.outputs[0], comb.inputs[0])
    nt.links.new(sz.outputs[0], comb.inputs[2])
    wn = _node(nt, "ShaderNodeTexWhiteNoise", (-350, 0))
    wn.noise_dimensions = '3D'
    nt.links.new(comb.outputs[0], wn.inputs["Vector"])
    ramp = _ramp(nt, [(0.0, col("#6a2222")), (0.15, col("#22345a")), (0.3, col("#2e5a30")), (0.45, col("#5a3c22")),
                      (0.6, col("#8a2e2e")), (0.72, col("#1c1c1c")), (0.85, col("#a08a5a")), (1.0, col("#3a2a5a"))], (-200, 0), 'CONSTANT')
    nt.links.new(wn.outputs["Value"], ramp.inputs[0])
    p = _principled(nt, **{"Roughness": 0.6})
    nt.links.new(ramp.outputs[0], p.inputs["Base Color"])
    nt.links.new(p.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


def foliage(name="Foliage"):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-600, 0))
    nz = _node(nt, "ShaderNodeTexNoise", (-400, 0))
    nz.inputs["Scale"].default_value = 3.0
    nz.inputs["Detail"].default_value = 8.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = _ramp(nt, [(0.3, col("#2e5a1c")), (0.6, col("#5a8a34")), (0.8, col("#8fb654"))], (-200, 0))
    nt.links.new(nz.outputs["Fac"], ramp.inputs[0])
    p = _principled(nt, **{"Roughness": 0.7})
    nt.links.new(ramp.outputs[0], p.inputs["Base Color"])
    bmp = _node(nt, "ShaderNodeBump", (0, -300))
    bmp.inputs["Strength"].default_value = 0.6
    nt.links.new(nz.outputs["Fac"], bmp.inputs["Height"])
    nt.links.new(bmp.outputs[0], p.inputs["Normal"])
    tr = _node(nt, "ShaderNodeBsdfTranslucent", (300, -200))
    tr.inputs["Color"].default_value = col("#9fcf5a")
    mix = _node(nt, "ShaderNodeMixShader", (500, 0))
    mix.inputs[0].default_value = 0.4
    nt.links.new(p.outputs[0], mix.inputs[1])
    nt.links.new(tr.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    out.location = (750, 0)
    _cache[name] = m
    return m


def lawn(name="Lawn"):
    if name in _cache:
        return _cache[name]
    m, nt, out = _new(name)
    tc = _node(nt, "ShaderNodeTexCoord", (-600, 0))
    nz = _node(nt, "ShaderNodeTexNoise", (-400, 0))
    nz.inputs["Scale"].default_value = 0.8
    nz.inputs["Detail"].default_value = 10.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = _ramp(nt, [(0.35, col("#3e6a25")), (0.65, col("#6d9a3c"))], (-200, 0))
    nt.links.new(nz.outputs["Fac"], ramp.inputs[0])
    p = _principled(nt, **{"Roughness": 0.85})
    nt.links.new(ramp.outputs[0], p.inputs["Base Color"])
    nt.links.new(p.outputs[0], out.inputs[0])
    _cache[name] = m
    return m


# ------------------------------------------------------------------ palette
def lib():
    """Build the shared material library."""
    L = {}
    L["wall"] = paint("WallPaint", col("#f0e9dc"), rough=0.6, bump=0.04)
    L["trim"] = paint("TrimWhite", col("#f7f4ec"), rough=0.3, bump=0.01, spec=0.5)
    L["ceiling"] = paint("Ceiling", col("#f6f2ea"), rough=0.7, bump=0.02)
    L["plaster"] = paint("Plaster", col("#f4f0e6"), rough=0.5, bump=0.02)
    L["parquet"] = parquet()
    L["rug"] = rug()
    L["oak"] = wood("Oak", col("#b07a3c"), col("#6a4220"), scale=2.5)
    L["oak_dark"] = wood("OakDark", col("#6e4420"), col("#472a12"), scale=6.0, stretch=(1.0, 6.0, 1.0), rough=0.3, coat=0.35)
    L["mahogany"] = wood("Mahogany", col("#5a2a16"), col("#2e140a"), scale=3.0, rough=0.25, coat=0.4)
    L["walnut"] = wood("Walnut", col("#5e3a22"), col("#2b1a0e"), scale=3.0, rough=0.3, coat=0.3)
    L["marble"] = marble()
    L["marble_dark"] = marble("MarbleDark", "#c8c2b8", "#6b645c", 0.15)
    L["brass"] = simple("Brass", col("#b8893a"), rough=0.3, metallic=1.0)
    L["gold"] = simple("Gold", col("#e3b04b"), rough=0.3, metallic=1.0)
    L["bronze"] = simple("Bronze", col("#5c4a2c"), rough=0.35, metallic=1.0)
    L["black_metal"] = simple("BlackMetal", col("#141414"), rough=0.35, metallic=0.8)
    L["glass"] = glass()
    L["sofa"] = fabric("SofaFabric", col("#e2d3b1"), stripe=col("#d3bf95"), stripe_scale=28.0)
    L["armchair"] = fabric("ArmchairFabric", col("#d9c9a6"))
    L["drape"] = fabric("Drape", col("#c99a34"), rough=0.5, sheen=0.9)
    L["leather"] = leather()
    L["leather_black"] = leather("LeatherBlack", col("#141212"), 0.35)
    L["shade"] = lampshade()
    L["fire"] = fire()
    L["us_flag"] = us_flag()
    L["pres_flag"] = pres_flag()
    L["books"] = books()
    L["foliage"] = foliage()
    L["lawn"] = lawn()
    L["soot"] = simple("Soot", col("#0b0b0b"), rough=0.9)
    L["paper"] = simple("Paper", col("#f8f5ee"), rough=0.7)
    L["porcelain"] = simple("Porcelain", col("#f3f1ea"), rough=0.1, coat=0.6)
    L["cove_light"] = emission("CoveLight", (1.0, 0.92, 0.80, 1.0), 8.0)
    L["exterior"] = paint("Exterior", col("#f2eee6"), rough=0.7)
    L["terracotta"] = simple("Terracotta", col("#9a5a3a"), rough=0.8)
    L["stone_dark"] = simple("StoneDark", col("#2a2622"), rough=0.7)
    L["red_apple"] = simple("Apple", col("#b3222c"), rough=0.3, coat=0.5)
    L["green"] = simple("PlantGreen", col("#2f5a24"), rough=0.6)
    L["photo"] = simple("PhotoGloss", col("#8a8a86"), rough=0.15)
    return L
