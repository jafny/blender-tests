"""World, sun, light portals, interior lights, cameras, flythrough animation, render settings."""
import math
from math import radians as rad
import bpy
from mathutils import Vector, Matrix
from helpers import A, B, H, link, empty, coll

SUN_AZIMUTH = 205.0    # compass degrees (0 = north, clockwise) - sun in the south-south-west
SUN_ELEV = 34.0


def world():
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    sky = nt.nodes.new("ShaderNodeTexSky")
    sky.sky_type = 'NISHITA'
    sky.sun_disc = False
    sky.sun_elevation = rad(SUN_ELEV)
    sky.sun_rotation = rad(SUN_AZIMUTH)
    sky.altitude = 20
    sky.air_density = 1.0
    sky.dust_density = 1.5
    sky.ozone_density = 1.5
    bg.inputs["Strength"].default_value = 0.015
    nt.links.new(sky.outputs[0], bg.inputs["Color"])
    nt.links.new(bg.outputs[0], out.inputs[0])
    w.cycles.sampling_method = 'MANUAL'
    w.cycles.sample_map_resolution = 1024
    return w


def sun():
    ld = bpy.data.lights.new("Sun", 'SUN')
    ld.energy = 4.0
    ld.angle = rad(0.7)
    ld.color = (1.0, 0.95, 0.88)
    ob = bpy.data.objects.new("Sun", ld)
    link(ob, "Lights")
    az, el = rad(SUN_AZIMUTH), rad(SUN_ELEV)
    to_sun = Vector((math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)))
    ob.rotation_euler = (-to_sun).to_track_quat('-Z', 'Y').to_euler()
    ob.location = (0, 0, 8)
    return ob


def portals(info):
    for i, p in enumerate(info["portals"]):
        ld = bpy.data.lights.new(f"Portal{i}", 'AREA')
        ld.shape = 'RECTANGLE'
        ld.size = p["w"]
        ld.size_y = p["h"]
        ld.cycles.is_portal = True
        ob = bpy.data.objects.new(f"Portal{i}", ld)
        link(ob, "Lights")
        # area light emits along -Z; rotate so -Z points along local -Y of the frame (into the room)
        ob.matrix_world = p["matrix"] @ Matrix.Rotation(-math.pi / 2, 4, 'X')


def point(name, loc, watts, color=(1.0, 0.78, 0.55), radius=0.04, collection="Lights"):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.energy = watts
    ld.color = color
    ld.shadow_soft_size = radius
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    link(ob, collection)
    return ob


def fire_light(info):
    m = info.get("fire_light")
    if m is None:
        return
    ob = point("FireLight", m.to_translation(), 60.0, (1.0, 0.5, 0.15), 0.15)
    # flicker-free, but warm; no animation to keep frames consistent
    return ob


# ------------------------------------------------------------------ cameras
def camera(name, loc, aim, lens=28, fstop=None, focus=None, sensor=36):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = sensor
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


STILLS = {
    # name: (location, aim, lens, fstop)
    "01_hero_desk":      ((-1.9, 3.9, 1.55), (0.15, -3.2, 1.05), 24, None),
    "02_fireplace":      ((0.9, -3.2, 1.45), (-0.1, 5.2, 1.6), 24, None),
    "03_seating_east":   ((3.6, 0.2, 1.5), (-0.6, 1.4, 0.9), 28, None),
    "04_desk_detail":    ((1.5, -1.5, 1.25), (-0.15, -3.3, 0.85), 40, 4.0),
    "05_ceiling_seal":   ((0.0, 0.2, 1.2), (0.0, 0.25, H), 24, None),
    "06_from_west_door": ((-3.7, 0.6, 1.6), (1.2, -1.8, 1.0), 22, None),
}


def stills():
    cams = {}
    for name, (loc, aim, lens, fs) in STILLS.items():
        cams[name] = camera("Cam_" + name, loc, aim, lens, fs)
    return cams


# ------------------------------------------------------------------ flythrough
FLY_FPS = 24
FLY_FRAMES = 360
# (frame, camera position, aim position)
FLY_KEYS = [
    (1,   (-3.0, 3.35, 1.65), (0.6, -2.4, 1.0)),
    (70,  (-2.45, 0.2, 1.6), (0.6, -3.0, 0.95)),
    (110, (-1.6, -1.55, 1.5), (0.3, -3.4, 0.9)),
    (150, (0.1, -1.7, 1.35), (0.0, -3.6, 0.85)),
    (215, (2.7, -0.9, 1.6), (-0.4, 2.6, 1.2)),
    (290, (1.5, 1.7, 1.45), (-0.2, 5.3, 1.7)),
    (360, (0.3, -0.6, 2.7), (0.0, 4.6, 1.5)),
]


def flythrough(scene):
    aim = empty("FlyAim", collection="Cameras")
    cd = bpy.data.cameras.new("Cam_Fly")
    cd.lens = 24
    cd.sensor_width = 36
    cd.clip_end = 400
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
            # ease in/out at the ends
            fc.keyframe_points[0].easing = 'EASE_IN_OUT'
    scene.frame_start = 1
    scene.frame_end = FLY_FRAMES
    scene.render.fps = FLY_FPS
    return cam


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
    c.adaptive_threshold = 0.02 if animation else 0.01
    c.adaptive_min_samples = 16
    c.use_denoising = True
    c.denoiser = 'OPENIMAGEDENOISE'
    c.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    c.denoising_prefilter = 'ACCURATE'
    c.max_bounces = 10
    c.diffuse_bounces = 4
    c.glossy_bounces = 4
    c.transmission_bounces = 8
    c.transparent_max_bounces = 8
    c.volume_bounces = 0
    c.sample_clamp_direct = 0.0
    c.sample_clamp_indirect = 6.0
    c.caustics_reflective = False
    c.caustics_refractive = False
    c.blur_glossy = 1.0
    c.use_light_tree = True
    c.use_fast_gi = True
    c.fast_gi_method = 'REPLACE'
    c.ao_bounces = 3
    c.ao_bounces_render = 3
    scene.world.light_settings.ao_factor = 0.8
    scene.world.light_settings.distance = 3.0
    c.pixel_filter_type = 'BLACKMAN_HARRIS'
    c.filter_width = 1.5
    vs = scene.view_settings
    vs.view_transform = 'AgX'
    vs.look = 'AgX - Medium High Contrast'
    vs.exposure = 0.0
    vs.gamma = 1.0
    scene.display_settings.display_device = 'sRGB'
