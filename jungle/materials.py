"""Procedural jungle materials (all node graphs, no image textures).

Leaves read the per-vertex `luv` attribute written by helpers.leaf() (u along the blade, v across, random id)
to draw a midrib, lateral veins, yellowed edges and per-leaf colour variation; Object Info > Random adds
per-instance variation on top. Stone, bark and ground use 3D (object / world space) textures so nothing
needs UVs, and grow moss on upward-facing surfaces.
"""
import bpy

_cache = {}


def hexc(h):
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c) + (1.0,)


col = hexc


class G:
    """Tiny node-graph builder."""

    def __init__(self, nt):
        self.nt = nt
        self.x = 0

    def n(self, kind, inputs=None, **props):
        nd = self.nt.nodes.new(kind)
        nd.location = (self.x, 0)
        self.x += 40
        for k, v in props.items():
            setattr(nd, k, v)
        for k, v in (inputs or {}).items():
            self.set(nd.inputs[k], v)
        return nd

    def set(self, sock, v):
        if hasattr(v, "is_linked") or hasattr(v, "links"):
            self.nt.links.new(v, sock)
        elif isinstance(v, str):
            sock.default_value = hexc(v) if len(sock.default_value) == 4 else hexc(v)[:3]
        else:
            sock.default_value = v

    def link(self, a, b):
        self.nt.links.new(a, b)

    def math(self, op, a, b=0.0, clamp=False):
        nd = self.n("ShaderNodeMath", operation=op, use_clamp=clamp)
        self.set(nd.inputs[0], a)
        self.set(nd.inputs[1], b)
        return nd.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        nd = self.n("ShaderNodeVectorMath", operation=op)
        self.set(nd.inputs[0], a)
        if b is not None:
            self.set(nd.inputs[1], b)
        if scale is not None:
            self.set(nd.inputs["Scale"], scale)
        return nd.outputs[0] if op not in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else nd.outputs["Value"]

    def mix(self, fac, a, b, blend='MIX'):
        nd = self.n("ShaderNodeMix", data_type='RGBA', blend_type=blend)
        self.set(nd.inputs[0], fac)
        self.set(nd.inputs[6], a)
        self.set(nd.inputs[7], b)
        return nd.outputs[2]

    def mixf(self, fac, a, b):
        nd = self.n("ShaderNodeMix", data_type='FLOAT')
        self.set(nd.inputs[0], fac)
        self.set(nd.inputs[2], a)
        self.set(nd.inputs[3], b)
        return nd.outputs[0]

    def ramp(self, fac, stops, interp='LINEAR'):
        r = self.n("ShaderNodeValToRGB")
        r.color_ramp.interpolation = interp
        el = r.color_ramp.elements
        el[0].position, el[0].color = stops[0][0], hexc(stops[0][1]) if isinstance(stops[0][1], str) else stops[0][1]
        el[1].position, el[1].color = stops[-1][0], hexc(stops[-1][1]) if isinstance(stops[-1][1], str) else stops[-1][1]
        for pos, c in stops[1:-1]:
            e = el.new(pos)
            e.color = hexc(c) if isinstance(c, str) else c
        self.set(r.inputs[0], fac)
        return r.outputs[0]

    def maprange(self, v, a0, a1, b0=0.0, b1=1.0, clamp=True, interp='LINEAR'):
        nd = self.n("ShaderNodeMapRange", interpolation_type=interp, clamp=clamp)
        self.set(nd.inputs["Value"], v)
        nd.inputs["From Min"].default_value = a0
        nd.inputs["From Max"].default_value = a1
        nd.inputs["To Min"].default_value = b0
        nd.inputs["To Max"].default_value = b1
        return nd.outputs[0]

    def noise(self, vec, scale, detail=4.0, rough=0.55, dist=0.0, dims='3D', w=None):
        nd = self.n("ShaderNodeTexNoise", noise_dimensions=dims)
        if vec is not None:
            self.set(nd.inputs["Vector"], vec)
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Detail"].default_value = detail
        nd.inputs["Roughness"].default_value = rough
        nd.inputs["Distortion"].default_value = dist
        if w is not None:
            self.set(nd.inputs["W"], w)
        return nd

    def voronoi(self, vec, scale, feature='F1', rand=1.0, metric='EUCLIDEAN'):
        nd = self.n("ShaderNodeTexVoronoi", feature=feature, distance=metric)
        if vec is not None:
            self.set(nd.inputs["Vector"], vec)
        nd.inputs["Scale"].default_value = scale
        nd.inputs["Randomness"].default_value = rand
        return nd

    def attr(self, name, kind='GEOMETRY'):
        return self.n("ShaderNodeAttribute", attribute_name=name, attribute_type=kind)

    def sep(self, v):
        nd = self.n("ShaderNodeSeparateXYZ")
        self.set(nd.inputs[0], v)
        return nd.outputs

    def bump(self, h, strength=0.3, dist=0.05, normal=None):
        nd = self.n("ShaderNodeBump", inputs={"Strength": strength, "Distance": dist})
        self.set(nd.inputs["Height"], h)
        if normal is not None:
            self.set(nd.inputs["Normal"], normal)
        return nd.outputs[0]

    def principled(self, **kw):
        p = self.n("ShaderNodeBsdfPrincipled")
        names = {"color": "Base Color", "rough": "Roughness", "spec": "Specular IOR Level", "normal": "Normal",
                 "metal": "Metallic", "trans": "Transmission Weight", "ior": "IOR", "sss": "Subsurface Weight",
                 "sss_radius": "Subsurface Radius", "coat": "Coat Weight", "alpha": "Alpha", "emit": "Emission Color",
                 "emit_s": "Emission Strength", "sheen": "Sheen Weight", "aniso": "Anisotropic"}
        for k, v in kw.items():
            self.set(p.inputs[names[k]], v)
        return p.outputs[0]


def _new(name):
    if name in _cache:
        return None, None, None
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    _cache[name] = m
    return m, G(nt), out


def _moss(g, base_col, nrm_z, strength=1.0, scale=3.0, coord=None, thresh=(0.35, 0.75)):
    """Return (color, factor) mixing moss onto upward faces with a noisy edge."""
    nz = g.noise(coord, scale, 5.0, 0.6)
    up = g.maprange(g.math('ADD', nrm_z, g.math('MULTIPLY', g.math('SUBTRACT', nz.outputs[0], 0.5), 0.9)),
                    thresh[0], thresh[1], 0.0, strength)
    mcol = g.ramp(g.noise(coord, scale * 6, 6.0, 0.7).outputs[0], [(0.3, "#2F4A12"), (0.55, "#58772A"), (0.8, "#7C9636")])
    return g.mix(up, base_col, mcol), up


# ------------------------------------------------------------------ foliage
LEAF_PALETTES = {
    # name: (dark, mid, light, edge/yellow, translucency, vein contrast)
    "jungle":   ("#173F0E", "#2E6B1A", "#4E8C24", "#9AA83A", "#8FC23A", 0.25),
    "fern":     ("#1E4A10", "#3C7A1E", "#64A030", "#A8B048", "#A6D44A", 0.15),
    "banana":   ("#2F6A1C", "#4C8E2A", "#79B23E", "#B9A246", "#B8E05A", 0.35),
    "palm":     ("#28561A", "#3F7A24", "#6A9A34", "#B0A040", "#A8D04A", 0.2),
    "elephant": ("#123A10", "#215A18", "#3C7A26", "#6E8C30", "#7FB83C", 0.6),
    "canopy":   ("#1A3F12", "#2A5A1A", "#45782A", "#8A8E36", "#86B83A", 0.15),
    "canopy2":  ("#24461A", "#3A6624", "#5E8A34", "#A4983C", "#9CC848", 0.15),
    "seedling": ("#2A6418", "#4A9A28", "#78C040", "#C0C050", "#B8E860", 0.2),
    "brom":     ("#2E5418", "#4E7A22", "#7A9C34", "#A89A3A", "#A0C040", 0.1),
    "litter":   ("#4A2E16", "#6E4622", "#946232", "#B88A4A", "#A07040", 0.1),
}


def leaf(name="Leaf", pal="jungle", red_base=False, gloss=0.35):
    """Two-sided leaf: principled (glossy upper side) mixed with translucency for backlight glow."""
    m, g, out = _new("Leaf_" + name)
    if m is None:
        return _cache["Leaf_" + name]
    dark, mid, light, edge, transl, vein = LEAF_PALETTES[pal]
    luv = g.sep(g.attr("luv").outputs["Vector"])
    u, v, rid = luv[0], luv[1], luv[2]
    oi = g.n("ShaderNodeObjectInfo")
    rnd = g.math('FRACT', g.math('ADD', g.math('MULTIPLY', oi.outputs["Random"], 3.7), rid))
    av = g.math('ABSOLUTE', v)
    base = g.ramp(rnd, [(0.0, dark), (0.5, mid), (1.0, light)])
    # yellowing / browning at the edge & tip for a fraction of leaves
    edgef = g.math('MULTIPLY', g.maprange(g.math('ADD', av, g.math('MULTIPLY', u, 0.25)), 0.75, 1.15),
                   g.maprange(rnd, 0.55, 0.95))
    base = g.mix(g.math('MULTIPLY', edgef, 0.8), base, edge)
    if red_base:
        base = g.mix(g.maprange(u, 0.4, 0.1, 0.0, 1.0, interp='SMOOTHSTEP'), base, "#C02A26")
    # midrib + lateral veins (angled stripes running out from the rib)
    rib = g.maprange(av, 0.05, 0.0)
    lat = g.n("ShaderNodeTexWave", wave_type='BANDS', bands_direction='X', wave_profile='SIN')
    lat.inputs["Scale"].default_value = 1.0
    lat.inputs["Distortion"].default_value = 0.0
    lat_coord = g.n("ShaderNodeCombineXYZ")
    g.link(g.math('ADD', g.math('MULTIPLY', u, 16.0), g.math('MULTIPLY', av, 7.0)), lat_coord.inputs[0])
    g.link(lat_coord.outputs[0], lat.inputs["Vector"])
    latv = g.maprange(lat.outputs["Fac"], 0.88, 1.0, 0.0, 0.6)
    veins = g.math('MAXIMUM', rib, latv)
    blotch = g.noise(g.n("ShaderNodeTexCoord").outputs["Object"], 18.0, 3.0, 0.6)
    base = g.mix(g.math('MULTIPLY', g.maprange(blotch.outputs[0], 0.45, 0.7), 0.25), base, dark)
    surf = g.mix(g.math('MULTIPLY', veins, vein), base, light)
    tcol = g.mix(g.math('MULTIPLY', veins, 0.5), g.mix(0.5, transl, base, 'MULTIPLY'), transl)
    tcol = g.mix(g.math('MULTIPLY', edgef, 0.7), tcol, edge)
    bmp = g.bump(g.math('MULTIPLY', veins, -1.0), 0.25, 0.01)
    pr = g.principled(color=surf, rough=gloss + 0.15, spec=0.45, normal=bmp, sheen=0.15, coat=0.15)
    tr = g.n("ShaderNodeBsdfTranslucent")
    g.link(tcol, tr.inputs["Color"])
    g.link(bmp, tr.inputs["Normal"])
    mx = g.n("ShaderNodeMixShader")
    mx.inputs[0].default_value = 0.38
    g.link(pr, mx.inputs[1])
    g.link(tr.outputs[0], mx.inputs[2])
    g.link(mx.outputs[0], out.inputs["Surface"])
    return m


def flat(name, color, rough=0.5, sss=0.0, emit=None, emit_s=0.0, coat=0.0, transl=0.0):
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    kw = dict(color=color, rough=rough, coat=coat)
    if sss:
        kw.update(sss=sss, sss_radius=(0.2, 0.08, 0.04))
    if emit:
        kw.update(emit=emit, emit_s=emit_s)
    pr = g.principled(**kw)
    if transl:
        tr = g.n("ShaderNodeBsdfTranslucent", inputs={"Color": color})
        mx = g.n("ShaderNodeMixShader")
        mx.inputs[0].default_value = transl
        g.link(pr, mx.inputs[1])
        g.link(tr.outputs[0], mx.inputs[2])
        pr = mx.outputs[0]
    g.link(pr, out.inputs["Surface"])
    return m


def bract(name="Heliconia"):
    """Waxy red bract shading to yellow-green lips (uses leaf luv)."""
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    luv = g.sep(g.attr("luv").outputs["Vector"])
    c = g.ramp(g.math('ADD', g.math('ABSOLUTE', luv[1]), g.math('MULTIPLY', luv[0], 0.4)),
               [(0.0, "#C0141A"), (0.75, "#E8341E"), (0.95, "#F2C030"), (1.2, "#7EA032")])
    pr = g.principled(color=c, rough=0.25, coat=0.4, sss=0.15, sss_radius=(0.3, 0.05, 0.03))
    g.link(pr, out.inputs["Surface"])
    return m


# ------------------------------------------------------------------ wood
def bark(name="Bark", c0="#3E3226", c1="#6E6250", lichen="#9A9C88", moss=0.8, ridge_scale=1.0):
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    tc = g.n("ShaderNodeTexCoord")
    obj = tc.outputs["Object"]
    stretched = g.vmath('MULTIPLY', obj, (ridge_scale * 3.0, ridge_scale * 3.0, ridge_scale * 0.35))
    fiss = g.noise(stretched, 2.5, 8.0, 0.65, dist=1.2)
    vor = g.voronoi(stretched, 4.0, 'DISTANCE_TO_EDGE')
    h = g.math('ADD', g.math('MULTIPLY', fiss.outputs[0], 0.7), g.math('MULTIPLY', g.maprange(vor.outputs[0], 0.0, 0.08), 0.3))
    c = g.ramp(h, [(0.3, c0), (0.65, c1)])
    lic = g.noise(obj, 3.0, 5.0, 0.6)
    licf = g.maprange(lic.outputs[0], 0.58, 0.68)
    c = g.mix(g.math('MULTIPLY', licf, 0.65), c, lichen)
    geo = g.n("ShaderNodeNewGeometry")
    nz = g.sep(geo.outputs["Normal"])[2]
    # moss creeps on upward-ish faces and near the ground
    wz = g.sep(geo.outputs["Position"])[2]
    lowmoss = g.maprange(wz, 3.0, 0.3, 0.0, 0.7)
    mossc, mf = _moss(g, c, g.math('ADD', nz, lowmoss), moss, 1.5, obj, (0.45, 0.8))
    bmp = g.bump(h, 0.6, 0.08)
    pr = g.principled(color=mossc, rough=g.mixf(mf, 0.85, 0.95), spec=0.3, normal=bmp)
    g.link(pr, out.inputs["Surface"])
    return m


def palm_trunk(name="PalmTrunk"):
    """Ringed palm trunk: bands along luv.y (tube length) with fibrous noise."""
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    luv = g.sep(g.attr("luv").outputs["Vector"])
    tc = g.n("ShaderNodeTexCoord")
    ring = g.n("ShaderNodeTexWave", wave_type='BANDS', bands_direction='Z', wave_profile='SAW')
    ring.inputs["Scale"].default_value = 1.0
    cmb = g.n("ShaderNodeCombineXYZ")
    g.link(g.math('MULTIPLY', luv[1], 5.0), cmb.inputs[2])
    g.link(cmb.outputs[0], ring.inputs["Vector"])
    ring.inputs["Distortion"].default_value = 2.0
    ring.inputs["Detail"].default_value = 3.0
    fib = g.noise(g.vmath('MULTIPLY', tc.outputs["Object"], (8.0, 8.0, 0.6)), 6.0, 6.0, 0.6)
    h = g.math('ADD', g.math('MULTIPLY', ring.outputs["Fac"], 0.6), g.math('MULTIPLY', fib.outputs[0], 0.4))
    c = g.ramp(h, [(0.25, "#4A3E30"), (0.55, "#7C705C"), (0.8, "#A49A84")])
    geo = g.n("ShaderNodeNewGeometry")
    wz = g.sep(geo.outputs["Position"])[2]
    c = g.mix(g.maprange(wz, 2.5, 0.0, 0.0, 0.6), c, "#3E5020")
    bmp = g.bump(h, 0.7, 0.05)
    g.link(g.principled(color=c, rough=0.9, spec=0.3, normal=bmp), out.inputs["Surface"])
    return m


def stem(name="Stem", c0="#4E7A22", c1="#7EA43A", rough=0.45):
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    tc = g.n("ShaderNodeTexCoord")
    nz = g.noise(g.vmath('MULTIPLY', tc.outputs["Object"], (6.0, 6.0, 0.8)), 4.0, 4.0, 0.5)
    c = g.ramp(nz.outputs[0], [(0.35, c0), (0.7, c1)])
    g.link(g.principled(color=c, rough=rough, sss=0.1, sss_radius=(0.1, 0.2, 0.05), coat=0.1), out.inputs["Surface"])
    return m


def liana(name="Liana"):
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    tc = g.n("ShaderNodeTexCoord")
    nz = g.noise(tc.outputs["Object"], 14.0, 6.0, 0.6)
    c = g.ramp(nz.outputs[0], [(0.3, "#3A2E1E"), (0.55, "#5C4A30"), (0.75, "#6E7040")])
    geo = g.n("ShaderNodeNewGeometry")
    mc, mf = _moss(g, c, g.sep(geo.outputs["Normal"])[2], 0.6, 6.0, tc.outputs["Object"], (0.3, 0.9))
    g.link(g.principled(color=mc, rough=0.85, normal=g.bump(nz.outputs[0], 0.5, 0.02)), out.inputs["Surface"])
    return m


# ------------------------------------------------------------------ mineral
def stone(name="Stone", c0="#5E5A4E", c1="#8C8574", c2="#A69E88", moss=1.0, scale=1.0, carved=False, wet_z=0.25):
    """Weathered limestone/basalt with lichen, moss on top and darkening near the waterline."""
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    tc = g.n("ShaderNodeTexCoord")
    obj = tc.outputs["Object"]
    geo = g.n("ShaderNodeNewGeometry")
    wpos = g.sep(geo.outputs["Position"])
    n1 = g.noise(obj, 1.2 * scale, 8.0, 0.62, dist=0.3)
    vor = g.voronoi(obj, 2.5 * scale, 'F1')
    cr = g.voronoi(obj, 1.6 * scale, 'DISTANCE_TO_EDGE')
    cracks = g.math('MULTIPLY', g.maprange(cr.outputs[0], 0.0, 0.012, 1.0, 0.0),
                    g.maprange(g.noise(obj, 0.8 * scale, 2.0, 0.5).outputs[0], 0.45, 0.6))
    h = g.math('ADD', g.math('MULTIPLY', n1.outputs[0], 0.75), g.math('MULTIPLY', vor.outputs[0], 0.25))
    c = g.ramp(h, [(0.3, c0), (0.55, c1), (0.75, c2)])
    lic = g.noise(obj, 4.0 * scale, 6.0, 0.7)
    c = g.mix(g.math('MULTIPLY', g.maprange(lic.outputs[0], 0.6, 0.7), 0.5), c, "#B8B8A0")
    stain = g.noise(g.vmath('MULTIPLY', obj, (1.0, 1.0, 0.15)), 2.0 * scale, 4.0, 0.6)
    c = g.mix(g.math('MULTIPLY', g.maprange(stain.outputs[0], 0.5, 0.7), 0.3), c, "#3A3428")
    c = g.mix(g.math('MULTIPLY', cracks, 0.7), c, "#1E1A14")
    c, mf = _moss(g, c, g.sep(geo.outputs["Normal"])[2], moss, 1.2 * scale, obj)
    wet = g.maprange(wpos[2], wet_z + 0.35, wet_z, 0.0, 1.0)
    c = g.mix(g.math('MULTIPLY', wet, 0.6), c, "#1C1A14")
    rough = g.mixf(wet, g.mixf(mf, 0.82, 0.95), 0.25)
    hb = g.math('SUBTRACT', h, g.math('MULTIPLY', cracks, 0.4))
    if carved:
        # stepped meander glyph bands (Maya-ish fret) in object space
        wv = g.n("ShaderNodeTexWave", wave_type='BANDS', bands_direction='Z', wave_profile='SAW')
        wv.inputs["Scale"].default_value = 2.2
        wv.inputs["Distortion"].default_value = 0.0
        g.link(obj, wv.inputs["Vector"])
        sq = g.voronoi(g.vmath('MULTIPLY', obj, (3.0, 3.0, 3.0)), 1.0, 'F1', 0.0, 'CHEBYCHEV')
        glyph = g.math('MULTIPLY', g.math('GREATER_THAN', wv.outputs["Fac"], 0.55),
                       g.math('GREATER_THAN', sq.outputs["Distance"], 0.3))
        hb = g.math('SUBTRACT', hb, g.math('MULTIPLY', glyph, 0.6))
        c = g.mix(g.math('MULTIPLY', glyph, 0.35), c, "#2A2820")
    bmp = g.bump(hb, 0.8, 0.12)
    g.link(g.principled(color=c, rough=rough, spec=0.35, normal=bmp), out.inputs["Surface"])
    return m


def ground(name="Ground", water_z=0.0):
    """Forest floor: dark loam, leaf-litter tones, moss and wet mud toward the water and on steep cliffs (rock)."""
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    geo = g.n("ShaderNodeNewGeometry")
    pos = geo.outputs["Position"]
    wp = g.sep(pos)
    nz = g.sep(geo.outputs["Normal"])[2]
    n1 = g.noise(pos, 0.35, 6.0, 0.6)
    n2 = g.noise(pos, 3.0, 6.0, 0.65)
    soil = g.ramp(n2.outputs[0], [(0.3, "#1E1610"), (0.5, "#2C2016"), (0.7, "#3E2E1E")])
    litter = g.ramp(g.noise(pos, 9.0, 4.0, 0.6).outputs[0], [(0.3, "#3A2614"), (0.5, "#56391E"), (0.7, "#6E4E2C")])
    c = g.mix(g.maprange(n1.outputs[0], 0.4, 0.6), soil, litter)
    mossf = g.maprange(g.noise(pos, 0.6, 5.0, 0.6).outputs[0], 0.5, 0.62, 0.0, 0.85)
    mossc = g.ramp(n2.outputs[0], [(0.3, "#2E4614"), (0.7, "#5A7A26")])
    c = g.mix(mossf, c, mossc)
    # mud toward the waterline, wet darkening
    near = g.maprange(wp[2], water_z + 0.6, water_z + 0.05)
    c = g.mix(near, c, g.ramp(n2.outputs[0], [(0.3, "#2E2418"), (0.7, "#4A3C2A")]))
    wet = g.maprange(wp[2], water_z + 0.25, water_z - 0.05)
    c = g.mix(g.math('MULTIPLY', wet, 0.5), c, "#120E0A")
    # cliffs: steep faces become wet rock
    rockf = g.maprange(nz, 0.55, 0.35)
    rv = g.voronoi(g.vmath('MULTIPLY', pos, (0.7, 0.7, 2.2)), 0.5, 'DISTANCE_TO_EDGE')   # horizontal bedding joints
    rn = g.noise(pos, 1.5, 8.0, 0.6)
    strata = g.n("ShaderNodeTexWave", wave_type='BANDS', bands_direction='Z', wave_profile='SIN')
    strata.inputs["Scale"].default_value = 0.35
    strata.inputs["Distortion"].default_value = 6.0
    strata.inputs["Detail"].default_value = 4.0
    g.link(pos, strata.inputs["Vector"])
    rock = g.ramp(g.math('ADD', g.math('MULTIPLY', rn.outputs[0], 0.7), g.math('MULTIPLY', strata.outputs["Fac"], 0.3)),
                  [(0.3, "#2E2C26"), (0.5, "#4A473C"), (0.68, "#67624F"), (0.8, "#58604A")])
    streak = g.noise(g.vmath('MULTIPLY', pos, (4.0, 4.0, 0.25)), 1.2, 4.0, 0.6)   # dark seepage streaks
    rock = g.mix(g.math('MULTIPLY', g.maprange(streak.outputs[0], 0.55, 0.7), 0.35), rock, "#141210")
    rock = g.mix(g.math('MULTIPLY', g.maprange(rv.outputs[0], 0.0, 0.01, 0.35, 0.0),
                        g.maprange(rn.outputs[0], 0.5, 0.6)), rock, "#16140F")
    c = g.mix(rockf, c, rock)
    rough = g.mixf(wet, 0.9, 0.35)
    h = g.math('ADD', g.math('MULTIPLY', n2.outputs[0], 0.5), g.math('MULTIPLY', g.math('MULTIPLY', rn.outputs[0], rockf), 1.0))
    h = g.math('SUBTRACT', h, g.math('MULTIPLY', g.maprange(rv.outputs[0], 0.0, 0.02, 0.3, 0.0), rockf))
    bmp = g.bump(h, 0.5, 0.15)
    g.link(g.principled(color=c, rough=rough, spec=0.4, normal=bmp), out.inputs["Surface"])
    return m


# ------------------------------------------------------------------ water
_anim_inputs = []   # (socket, values_per_frame fn) keyed later by lighting.animate_textures


def water(name="Water"):
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    geo = g.n("ShaderNodeNewGeometry")
    mp = g.n("ShaderNodeMapping")
    g.link(geo.outputs["Position"], mp.inputs["Vector"])
    _anim_inputs.append((mp.inputs["Location"], (0.0, -0.05, 0.0)))   # flow toward -y (per frame)
    r1 = g.noise(g.vmath('MULTIPLY', mp.outputs[0], (1.0, 0.45, 1.0)), 1.6, 3.0, 0.5)
    r2 = g.noise(mp.outputs[0], 7.0, 2.0, 0.5, dist=0.4)
    h = g.math('ADD', r1.outputs[0], g.math('MULTIPLY', r2.outputs[0], 0.35))
    bmp = g.bump(h, 0.25, 0.08)
    pr = g.principled(color="#16241A", rough=0.04, ior=1.33, trans=1.0, spec=0.6, normal=bmp)
    vol = g.n("ShaderNodeVolumeAbsorption", inputs={"Color": "#3C6A42", "Density": 0.9})
    g.link(pr, out.inputs["Surface"])
    g.link(vol.outputs[0], out.inputs["Volume"])
    m.cycles.volume_sampling = 'EQUIANGULAR'
    return m


def falls(name="Falls"):
    """Streaky white water sheet: mix of transparent and bright aerated water, streaks scroll downward."""
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    luv = g.attr("luv").outputs["Vector"]
    mp = g.n("ShaderNodeMapping")
    g.link(luv, mp.inputs["Vector"])
    _anim_inputs.append((mp.inputs["Location"], (0.0, -0.045, 0.0)))
    st = g.noise(g.vmath('MULTIPLY', mp.outputs[0], (14.0, 1.2, 1.0)), 1.0, 6.0, 0.65, dist=0.6)
    fine = g.noise(g.vmath('MULTIPLY', mp.outputs[0], (60.0, 4.0, 1.0)), 1.0, 3.0, 0.6)
    s = g.math('ADD', g.math('MULTIPLY', st.outputs[0], 0.7), g.math('MULTIPLY', fine.outputs[0], 0.3))
    v = g.sep(luv)
    edge = g.math('MULTIPLY', g.maprange(g.math('ABSOLUTE', v[0]), 0.0, 0.1, 0.0, 1.0),
                  g.maprange(g.math('ABSOLUTE', v[0]), 1.0, 0.9, 0.0, 1.0))
    # a few broad gaps so the curtain separates into sheets and ropes of water
    cols = g.noise(g.vmath('MULTIPLY', luv, (2.5, 0.15, 1.0)), 1.0, 2.0, 0.5)
    a = g.math('MULTIPLY', g.maprange(s, 0.36, 0.62, 0.1, 1.0), edge)
    a = g.math('MULTIPLY', a, g.maprange(cols.outputs[0], 0.32, 0.5, 0.35, 1.0))
    a = g.math('MULTIPLY', a, g.maprange(v[1], 0.0, 0.12, 0.5, 1.0))
    white = g.principled(color="#E8F0EC", rough=0.35, sss=0.3, sss_radius=(0.3, 0.4, 0.5), trans=0.2, emit="#DDEAEA", emit_s=0.08)
    tr = g.n("ShaderNodeBsdfTransparent")
    mx = g.n("ShaderNodeMixShader")
    g.link(a, mx.inputs[0])
    g.link(tr.outputs[0], mx.inputs[1])
    g.link(white, mx.inputs[2])
    g.link(mx.outputs[0], out.inputs["Surface"])
    m.blend_method = 'HASHED'
    return m


def foam(name="Foam"):
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    geo = g.n("ShaderNodeNewGeometry")
    tc = g.n("ShaderNodeTexCoord")
    mp = g.n("ShaderNodeMapping")
    g.link(geo.outputs["Position"], mp.inputs["Vector"])
    _anim_inputs.append((mp.inputs["Location"], (0.0, -0.03, 0.0)))
    nz = g.noise(mp.outputs[0], 2.5, 8.0, 0.7, dist=0.8)
    vr = g.voronoi(mp.outputs[0], 6.0, 'DISTANCE_TO_EDGE')
    bub = g.maprange(vr.outputs[0], 0.0, 0.06, 1.0, 0.0)
    # radial falloff from object centre
    d = g.vmath('LENGTH', g.vmath('MULTIPLY', tc.outputs["Object"], (1.0, 1.0, 0.0)))
    fall = g.maprange(d, 0.95, 0.1, 0.0, 1.0, interp='SMOOTHSTEP')
    a = g.math('MULTIPLY', g.math('ADD', g.maprange(nz.outputs[0], 0.4, 0.65), g.math('MULTIPLY', bub, 0.5)), fall, clamp=True)
    white = g.principled(color="#EEF4F0", rough=0.5, sss=0.2)
    tr = g.n("ShaderNodeBsdfTransparent")
    mx = g.n("ShaderNodeMixShader")
    g.link(a, mx.inputs[0])
    g.link(tr.outputs[0], mx.inputs[1])
    g.link(white, mx.inputs[2])
    g.link(mx.outputs[0], out.inputs["Surface"])
    return m


def haze(name="Haze", density=0.012, color="#D8E4C4", aniso=0.72, falloff_z=(1.0, 16.0)):
    """Ground-hugging humid haze: density falls off with height and breaks up with noise (gives god rays)."""
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    geo = g.n("ShaderNodeNewGeometry")
    pos = geo.outputs["Position"]
    z = g.sep(pos)[2]
    nz = g.noise(pos, 0.12, 3.0, 0.5)
    d = g.math('MULTIPLY', g.maprange(z, falloff_z[0], falloff_z[1], 1.0, 0.25),
               g.maprange(nz.outputs[0], 0.3, 0.7, 0.45, 1.3))
    d = g.math('MULTIPLY', d, density)
    vol = g.n("ShaderNodeVolumePrincipled", inputs={"Color": color, "Anisotropy": aniso})
    g.link(d, vol.inputs["Density"])
    g.link(vol.outputs[0], out.inputs["Volume"])
    return m


def mist(name="Mist", density=0.9):
    """Spray cloud at the foot of the waterfall (object-space radial falloff)."""
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    tc = g.n("ShaderNodeTexCoord")
    o = tc.outputs["Object"]
    d = g.vmath('LENGTH', o)
    nz = g.noise(o, 2.0, 4.0, 0.6)
    den = g.math('MULTIPLY', g.maprange(d, 1.0, 0.2), g.maprange(nz.outputs[0], 0.35, 0.7))
    den = g.math('MULTIPLY', den, density)
    vol = g.n("ShaderNodeVolumePrincipled", inputs={"Color": "#F2F6F4", "Anisotropy": 0.3})
    g.link(den, vol.inputs["Density"])
    g.link(vol.outputs[0], out.inputs["Volume"])
    return m


def wing(name="MorphoWing"):
    """Blue morpho: iridescent blue centre (facing-dependent), black border with white dots (uses luv)."""
    m, g, out = _new(name)
    if m is None:
        return _cache[name]
    luv = g.sep(g.attr("luv").outputs["Vector"])
    r = g.vmath('LENGTH', g.attr("luv").outputs["Vector"])
    lw = g.n("ShaderNodeLayerWeight", inputs={"Blend": 0.5})
    blue = g.mix(lw.outputs["Facing"], "#1A6CFF", "#28E0FF")
    border = g.maprange(r, 0.62, 0.72)
    c = g.mix(border, blue, "#0A0A12")
    dots = g.voronoi(g.attr("luv").outputs["Vector"], 9.0, 'F1', 0.6)
    dotf = g.math('MULTIPLY', g.maprange(dots.outputs["Distance"], 0.12, 0.05), g.maprange(r, 0.75, 0.82))
    c = g.mix(dotf, c, "#EEE6D0")
    g.link(g.principled(color=c, rough=0.2, metal=g.math('MULTIPLY', g.math('SUBTRACT', 1.0, border), 0.6), coat=0.6, emit=blue,
                        emit_s=g.math('MULTIPLY', g.math('SUBTRACT', 1.0, border), 0.4)), out.inputs["Surface"])
    m.use_backface_culling = False
    return m
