"""World (cartoon sky), sun, fill lights, cameras, flythrough animation, render settings (Cycles + Freestyle)."""
import math
from math import radians as rad
import bpy
from mathutils import Vector
from helpers import link, empty
import materials as M

SUN_AZIMUTH = 150.0    # compass degrees (0 = +y/north, clockwise): sun in the front-right (south-east)
SUN_ELEV = 38.0


def world():
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.1
    mr.inputs["From Max"].default_value = 0.6
    nt.links.new(sep.outputs[2], mr.inputs["Value"])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = 'EASE'
    el = ramp.color_ramp.elements
    el[0].position, el[0].color = 0.0, M.col("#FFF0C8")   # horizon: warm cream
    el[1].position, el[1].color = 1.0, M.col("#57B8FF")   # zenith: seuss blue
    e = el.new(0.35)
    e.color = M.col("#9EDCFF")
    nt.links.new(mr.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs[0], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    nt.links.new(bg.outputs[0], out.inputs[0])
    w.cycles.sampling_method = 'MANUAL'
    w.cycles.sample_map_resolution = 512
    return w


def sun():
    ld = bpy.data.lights.new("Sun", 'SUN')
    ld.energy = 4.5
    ld.angle = rad(1.5)
    ld.color = (1.0, 0.94, 0.82)
    ob = bpy.data.objects.new("Sun", ld)
    link(ob, "Lights")
    az, el = rad(SUN_AZIMUTH), rad(SUN_ELEV)
    to_sun = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    ob.rotation_euler = (-to_sun).to_track_quat('-Z', 'Y').to_euler()
    ob.location = (0, 0, 10)
    return ob


def fills():
    """Soft, camera-invisible area lights so the cartoon colours stay bright everywhere."""
    specs = [("FillCenter", (0.3, -0.3, 3.6), 260.0, (3.5, 2.5)), ("FillBack", (-1.0, 1.6, 3.2), 140.0, (3.0, 1.5)),
             ("FillFront", (1.5, -2.2, 3.2), 120.0, (2.5, 1.5))]
    for name, loc, watts, size in specs:
        ld = bpy.data.lights.new(name, 'AREA')
        ld.shape = 'RECTANGLE'
        ld.size, ld.size_y = size
        ld.energy = watts
        ld.color = (1.0, 0.97, 0.92)
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        ob.rotation_euler = (0, 0, 0)  # points down (-Z)
        ob.visible_camera = False
        ob.visible_glossy = False
        link(ob, "Lights")


# ------------------------------------------------------------------ cameras
def camera(name, loc, aim, lens=24, fstop=None, focus=None, sensor=36):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = sensor
    cd.clip_end = 300
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = focus or (Vector(aim) - Vector(loc)).length
    ob = bpy.data.objects.new(name, cd)
    link(ob, "Cameras")
    ob.location = loc
    d = Vector(aim) - Vector(loc)
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return ob


STILLS = {
    # name: (location, aim, lens, fstop)
    "01_hero_wide":      ((2.6, -3.1, 1.75), (-0.6, 1.6, 1.2), 20, None),
    "02_cabinet_run":    ((-0.2, -0.9, 1.5), (-1.4, 3.2, 1.35), 24, None),
    "03_sink_window":    ((0.9, 0.9, 1.35), (0.05, 3.3, 1.35), 30, 4.0),
    "04_stove_hood":     ((-0.9, 1.15, 1.45), (-2.35, 3.2, 1.35), 28, None),
    "05_fridge_corner":  ((1.3, 0.9, 1.45), (3.35, 3.0, 1.25), 26, None),
    "06_table_chairs":   ((-2.9, -2.6, 1.35), (0.5, -0.3, 0.8), 26, 5.6),
    "07_from_door":      ((-3.9, -1.2, 1.6), (1.5, 1.4, 1.1), 18, None),
    "08_shelves_clock":  ((0.6, -2.2, 1.4), (4.6, 0.3, 1.9), 26, None),
}


def stills():
    return {name: camera("Cam_" + name, loc, aim, lens, fs) for name, (loc, aim, lens, fs) in STILLS.items()}


# ------------------------------------------------------------------ flythrough
FLY_FPS = 24
FLY_FRAMES = 300
# (frame, camera position, aim position) - a slow glide from the door, along the counter, round the table
FLY_KEYS = [
    (1,   (-3.9, -2.3, 1.7), (0.3, 1.5, 1.2)),
    (60,  (-2.6, -1.0, 1.6), (-1.8, 3.0, 1.3)),
    (115, (-0.9, 0.6, 1.45), (-1.9, 3.2, 1.3)),
    (165, (1.0, 0.7, 1.4), (0.2, 3.3, 1.5)),
    (215, (2.4, -0.6, 1.5), (3.2, 3.0, 1.2)),
    (260, (2.3, -2.6, 1.55), (0.3, -0.4, 0.9)),
    (300, (0.4, -3.2, 1.9), (-0.3, 1.4, 1.1)),
]


def flythrough(scene):
    aim = empty("FlyAim", collection="Cameras")
    cd = bpy.data.cameras.new("Cam_Fly")
    cd.lens = 22
    cd.sensor_width = 36
    cd.clip_end = 300
    cam = bpy.data.objects.new("Cam_Fly", cd)
    link(cam, "Cameras")
    c = cam.constraints.new('TRACK_TO')
    c.target = aim
    c.track_axis = 'TRACK_NEGATIVE_Z'
    c.up_axis = 'UP_Y'
    for f, loc, a in FLY_KEYS:
        cam.location = loc
        cam.keyframe_insert("location", frame=f)
        aim.location = a
        aim.keyframe_insert("location", frame=f)
    for ob in (cam, aim):
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
    scene.frame_start = 1
    scene.frame_end = FLY_FRAMES
    scene.render.fps = FLY_FPS
    return cam


# ------------------------------------------------------------------ render settings
def freestyle(scene, thickness=1.6):
    """Ink outlines, like a picture-book illustration."""
    r = scene.render
    r.use_freestyle = True
    r.line_thickness_mode = 'ABSOLUTE'
    r.line_thickness = thickness
    vl = scene.view_layers[0]
    vl.use_freestyle = True
    fs = vl.freestyle_settings
    fs.crease_angle = rad(140)
    fs.use_culling = True
    fs.use_smoothness = False
    for ls in list(fs.linesets):
        fs.linesets.remove(ls)
    ls = fs.linesets.new("Ink")
    ls.select_silhouette = True
    ls.select_border = True
    ls.select_crease = True
    ls.select_contour = False
    ls.select_external_contour = False
    ls.select_material_boundary = False
    # keep lines off the outdoor set (too busy, far away)
    ls.select_by_collection = True
    ls.collection = bpy.data.collections.get("Outside")
    ls.collection_negation = 'EXCLUSIVE'
    st = ls.linestyle
    st.color = M.col("#2A1F3D")[:3]
    st.thickness = thickness
    st.alpha = 0.95
    st.use_chaining = True
    st.chaining = 'PLAIN'
    # slightly wobbly, hand-drawn thickness
    st.thickness_position = 'CENTER'
    mod = st.thickness_modifiers.new("Wobble", 'ALONG_STROKE')
    mod.value_min = thickness * 0.55
    mod.value_max = thickness * 1.25
    mod.blend = 'MIX'
    mod.influence = 0.6
    return ls


def compositor_ink(scene, strength=0.85, depth_thresh=0.12, normal_thresh=0.55, thick=1):
    """Post-process outlines: Sobel edges of the depth and normal passes darken the image."""
    vl = scene.view_layers[0]
    vl.use_pass_z = True
    vl.use_pass_normal = True
    scene.use_nodes = True
    nt = scene.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    rl = nt.nodes.new("CompositorNodeRLayers")
    rl.location = (-800, 0)
    comp = nt.nodes.new("CompositorNodeComposite")
    comp.location = (600, 0)
    # depth edges: sobel of log-ish depth so far and near edges respond alike
    dlog = nt.nodes.new("CompositorNodeMath")
    dlog.operation = 'LOGARITHM'
    dlog.inputs[1].default_value = 2.0
    dlog.location = (-600, -200)
    nt.links.new(rl.outputs["Depth"], dlog.inputs[0])
    dmin = nt.nodes.new("CompositorNodeMath")
    dmin.operation = 'MINIMUM'
    dmin.inputs[1].default_value = 7.0    # clamp the sky (depth 1e10)
    dmin.location = (-450, -200)
    nt.links.new(dlog.outputs[0], dmin.inputs[0])
    dsob = nt.nodes.new("CompositorNodeFilter")
    dsob.filter_type = 'SOBEL'
    dsob.location = (-300, -200)
    nt.links.new(dmin.outputs[0], dsob.inputs["Image"])
    dth = nt.nodes.new("CompositorNodeMath")
    dth.operation = 'GREATER_THAN'
    dth.inputs[1].default_value = depth_thresh
    dth.location = (-150, -200)
    nt.links.new(dsob.outputs[0], dth.inputs[0])
    # normal edges
    nsob = nt.nodes.new("CompositorNodeFilter")
    nsob.filter_type = 'SOBEL'
    nsob.location = (-300, -450)
    nt.links.new(rl.outputs["Normal"], nsob.inputs["Image"])
    nrgb = nt.nodes.new("CompositorNodeRGBToBW")
    nrgb.location = (-150, -450)
    nt.links.new(nsob.outputs[0], nrgb.inputs[0])
    nth = nt.nodes.new("CompositorNodeMath")
    nth.operation = 'GREATER_THAN'
    nth.inputs[1].default_value = normal_thresh
    nth.location = (0, -450)
    nt.links.new(nrgb.outputs[0], nth.inputs[0])
    mx = nt.nodes.new("CompositorNodeMath")
    mx.operation = 'MAXIMUM'
    mx.location = (150, -300)
    nt.links.new(dth.outputs[0], mx.inputs[0])
    nt.links.new(nth.outputs[0], mx.inputs[1])
    mask = mx.outputs[0]
    if thick > 0:
        dil = nt.nodes.new("CompositorNodeDilateErode")
        dil.mode = 'FEATHER'
        dil.distance = thick
        dil.falloff = 'SMOOTH'
        dil.location = (300, -300)
        nt.links.new(mask, dil.inputs[0])
        mask = dil.outputs[0]
    # darken: image * (1 - strength*mask) tinted toward ink
    inv = nt.nodes.new("CompositorNodeMath")
    inv.operation = 'MULTIPLY'
    inv.inputs[1].default_value = strength
    inv.location = (350, -150)
    nt.links.new(mask, inv.inputs[0])
    mix = nt.nodes.new("CompositorNodeMixRGB")
    mix.blend_type = 'MIX'
    mix.location = (450, 0)
    nt.links.new(inv.outputs[0], mix.inputs["Fac"])
    nt.links.new(rl.outputs["Image"], mix.inputs[1])
    mix.inputs[2].default_value = (0.02, 0.012, 0.03, 1.0)
    nt.links.new(mix.outputs[0], comp.inputs["Image"])
    scene.render.use_compositing = True


def render_settings(scene, samples=128, res=(1920, 1080), pct=100, animation=False, outlines=True):
    r = scene.render
    r.engine = 'CYCLES'
    r.resolution_x, r.resolution_y = res
    r.resolution_percentage = pct
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.image_settings.compression = 50
    r.use_persistent_data = True
    r.film_transparent = False
    c = scene.cycles
    c.device = 'CPU'
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.05 if animation else 0.01
    c.adaptive_min_samples = 8 if animation else 16
    c.use_denoising = True
    c.denoiser = 'OPENIMAGEDENOISE'
    c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    c.denoising_prefilter = 'ACCURATE'
    c.max_bounces = 8
    c.diffuse_bounces = 3
    c.glossy_bounces = 3
    c.transmission_bounces = 4
    c.transparent_max_bounces = 8
    c.volume_bounces = 0
    c.sample_clamp_direct = 0.0
    c.sample_clamp_indirect = 5.0
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 1.0
    c.use_light_tree = True
    c.use_fast_gi = True
    c.fast_gi_method = 'REPLACE'
    c.ao_bounces = 2
    c.ao_bounces_render = 2
    scene.world.light_settings.ao_factor = 0.9
    scene.world.light_settings.distance = 2.5
    c.pixel_filter_type = 'BLACKMAN_HARRIS'
    c.filter_width = 1.5
    vs = scene.view_settings
    vs.view_transform = 'AgX'
    try:
        vs.look = 'AgX - Punchy'
    except TypeError:
        vs.look = 'None'
    vs.exposure = 0.35
    vs.gamma = 1.0
    scene.display_settings.display_device = 'sRGB'
    r.use_freestyle = False
    scene.use_nodes = False
    if outlines == 'ink':
        compositor_ink(scene)
    elif outlines:
        freestyle(scene)
