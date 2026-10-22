"""Sky + sun, humid haze volume, cameras, flythrough animation, Cycles settings."""
import math
from math import radians as rad
import bpy
from mathutils import Vector
from helpers import link, empty, coll
import materials as M
import terrain as T

SUN_AZIMUTH = 128.0    # compass degrees (0 = +y/north = upstream, clockwise): sun in the south-east
SUN_ELEV = 50.0


def sun_dir():
    az, el = rad(SUN_AZIMUTH), rad(SUN_ELEV)
    return Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))


def world():
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = 'NISHITA'
    sky.sun_disc = False          # the sun lamp provides the direct light
    sky.sun_elevation = rad(SUN_ELEV)
    sky.sun_rotation = rad(90.0 - SUN_AZIMUTH)   # sky texture: rotation measured from +x, counter-clockwise
    sky.altitude = 200.0
    sky.air_density = 1.0
    sky.dust_density = 1.2
    sky.ozone_density = 1.0
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = 0.3
    nt.links.new(sky.outputs[0], bg.inputs[0])
    nt.links.new(bg.outputs[0], out.inputs[0])
    w.cycles.sampling_method = 'MANUAL'
    w.cycles.sample_map_resolution = 1024
    return w


def sun():
    ld = bpy.data.lights.new("Sun", 'SUN')
    ld.energy = 7.0
    ld.angle = rad(0.8)
    ld.color = (1.0, 0.93, 0.80)
    ob = bpy.data.objects.new("Sun", ld)
    link(ob, "Lights")
    ob.rotation_euler = (-sun_dir()).to_track_quat('-Z', 'Y').to_euler()
    ob.location = (0, 0, 40)
    return ob


def bounce():
    """Very soft green-tinted skylight under the canopy (stands in for light bouncing off foliage)."""
    ld = bpy.data.lights.new("CanopyBounce", 'AREA')
    ld.shape = 'RECTANGLE'
    ld.size, ld.size_y = 50.0, 60.0
    ld.energy = 4000.0
    ld.color = (0.80, 0.95, 0.75)
    ob = bpy.data.objects.new("CanopyBounce", ld)
    ob.location = (0.0, 6.0, 30.0)
    ob.visible_camera = False
    ob.visible_glossy = False
    ob.visible_shadow = False
    ob.visible_volume_scatter = False
    link(ob, "Lights")


def fleck(target, energy=1500.0, size_deg=18.0):
    """A shaft of sun breaking through the canopy onto a spot (a 'sun fleck'), aligned with the sun direction."""
    ld = bpy.data.lights.new("SunFleck", 'SPOT')
    ld.energy = energy
    ld.spot_size = rad(size_deg)
    ld.spot_blend = 0.6
    ld.shadow_soft_size = 0.05
    ld.color = (1.0, 0.92, 0.78)
    ob = bpy.data.objects.new("SunFleck", ld)
    ob.location = Vector(target) + sun_dir() * 7.0
    ob.rotation_euler = (-sun_dir()).to_track_quat('-Z', 'Y').to_euler()
    ob.visible_camera = False
    link(ob, "Lights")
    return ob


def haze(density=0.0035):
    """A volume box over the valley: aerial perspective + god rays through the canopy gaps."""
    import helpers as H
    mb = H.MB()
    x0, x1, y0, y1, z0, z1 = -40, 40, -32, 56, -1.5, 34
    c = [mb.vert((x, y, z)) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)]
    for f in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        mb.face([c[i] for i in f])
    ob = mb.build("Haze", [M.haze(density=density)], "Atmosphere", smooth=False)
    ob.visible_shadow = False
    return ob


# ------------------------------------------------------------------ cameras
def camera(name, loc, aim, lens=24, fstop=None, focus=None, sensor=36):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = sensor
    cd.clip_start = 0.05
    cd.clip_end = 400
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


STILLS = {}      # filled by set_shots() once the scene layout is known


def set_shots(spots):
    """spots: dict of named world positions computed by the builders (temple, kapok, log, falls foot...)."""
    t, k, f, lg = spots["temple"], spots["kapok"], spots["falls"], spots["log"]
    rx = T.river_x
    STILLS.clear()
    STILLS.update({
        # name: (location, aim, lens, fstop, focus)
        "01_hero_river":    ((rx(-16) + 0.6, -16.0, 2.1), (rx(14) - 0.5, 18.0, 4.4), 22, None, None),
        "02_waterfall":     ((f.x + 3.5, f.y - 13.0, 1.5), (f.x - 0.3, f.y + 2.5, 5.2), 28, None, None),
        "03_temple":        ((t.x + 11.0, t.y - 9.5, 3.4), (t.x - 0.5, t.y + 0.5, 3.0), 24, None, None),
        "04_kapok_roots":   ((k.x - 4.5, k.y - 7.5, 1.7), (k.x, k.y, 6.0), 18, None, None),
        "05_forest_floor":  ((spots["floor"].x, spots["floor"].y, spots["floor"].z), (spots["floor_aim"].x, spots["floor_aim"].y, spots["floor_aim"].z), 50, 2.8, None),
        "06_log_bridge":    ((lg.x - 2.0, lg.y - 8.0, 1.5), (lg.x + 0.5, lg.y + 0.5, 1.0), 26, None, None),
        "07_canopy_up":     ((k.x - 9.0, k.y - 2.0, 1.6), (k.x - 4.0, k.y + 2.0, 22.0), 16, None, None),
        "08_temple_top":    ((t.x + 3.2, t.y - 0.6, t.z + 0.9), (rx(16) + 1.0, 21.0, 3.2), 22, None, None),
    })


def stills():
    return {name: camera("Cam_" + name, loc, aim, lens, fs, fd) for name, (loc, aim, lens, fs, fd) in STILLS.items()}


# ------------------------------------------------------------------ flythrough
FLY_FPS = 24
FLY_FRAMES = 360
FLY_KEYS = []


def set_fly(spots):
    t, k, f, lg = spots["temple"], spots["kapok"], spots["falls"], spots["log"]
    rx = T.river_x
    FLY_KEYS[:] = [
        # glide low over the river, past the log bridge, swing by the temple, rise toward the falls
        (1,   (rx(-24), -24.0, 1.4), (rx(-6), -6.0, 1.6)),
        (70,  (rx(-10) + 0.5, -10.0, 1.3), (lg.x, lg.y, 1.2)),
        (130, (rx(1) + 0.8, 1.0, 2.6), (t.x + 1.0, t.y, 3.5)),
        (190, (t.x + 7.5, t.y + 3.0, 3.8), (k.x, k.y + 2.0, 8.0)),
        (250, (rx(11) + 1.0, 11.0, 2.6), (f.x, f.y + 2.0, 5.0)),
        (310, (f.x + 1.5, f.y - 7.0, 2.4), (f.x - 0.2, f.y + 2.0, 6.5)),
        (360, (f.x + 0.8, f.y - 4.5, 5.6), (f.x, f.y + 5.0, 9.5)),
    ]


def flythrough(scene):
    aim = empty("FlyAim", collection="Cameras")
    cd = bpy.data.cameras.new("Cam_Fly")
    cd.lens = 22
    cd.sensor_width = 36
    cd.clip_start = 0.05
    cd.clip_end = 400
    cam = bpy.data.objects.new("Cam_Fly", cd)
    link(cam, "Cameras")
    c = cam.constraints.new('TRACK_TO')
    c.target = aim
    c.track_axis = 'TRACK_NEGATIVE_Z'
    c.up_axis = 'UP_Y'
    for fr, loc, a in FLY_KEYS:
        cam.location = loc
        cam.keyframe_insert("location", frame=fr)
        aim.location = a
        aim.keyframe_insert("location", frame=fr)
    for ob in (cam, aim):
        for fc in ob.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'BEZIER'
                kp.handle_left_type = kp.handle_right_type = 'AUTO_CLAMPED'
    scene.frame_start = 1
    scene.frame_end = FLY_FRAMES
    scene.render.fps = FLY_FPS
    return cam


def animate_textures(scene):
    """Scroll the water / falls / foam textures (mapping offsets keyed linearly over the shot)."""
    for sock, per_frame in M._anim_inputs:
        for fr in (scene.frame_start, scene.frame_end):
            sock.default_value = tuple(v * fr for v in per_frame)
            sock.keyframe_insert("default_value", frame=fr)
    for mat in bpy.data.materials:
        ad = mat.node_tree.animation_data if mat.node_tree else None
        if ad and ad.action:
            for fc in ad.action.fcurves:
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'


# ------------------------------------------------------------------ render settings
def render_settings(scene, samples=128, res=(1920, 1080), pct=100, animation=False):
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
    c.adaptive_threshold = 0.04 if animation else 0.012
    c.adaptive_min_samples = 8 if animation else 24
    c.use_denoising = True
    c.denoiser = 'OPENIMAGEDENOISE'
    c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    c.denoising_prefilter = 'ACCURATE'
    c.max_bounces = 8
    c.diffuse_bounces = 2
    c.glossy_bounces = 2
    c.transmission_bounces = 6
    c.transparent_max_bounces = 16
    c.volume_bounces = 0
    c.volume_step_rate = 4.0 if animation else 2.0
    c.volume_max_steps = 256
    c.sample_clamp_direct = 0.0
    c.sample_clamp_indirect = 3.0
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 1.0
    c.use_light_tree = True
    c.pixel_filter_type = 'BLACKMAN_HARRIS'
    c.filter_width = 1.5
    vs = scene.view_settings
    vs.view_transform = 'AgX'
    try:
        vs.look = 'AgX - Medium High Contrast'
    except TypeError:
        vs.look = 'None'
    vs.exposure = 0.9
    scene.display_settings.display_device = 'sRGB'
    r.use_motion_blur = False
