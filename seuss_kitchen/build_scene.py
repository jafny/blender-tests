"""Build the Dr. Seuss kitchen.  python3 build_scene.py [--out scene.blend] [--no-props]"""
import os
import sys
import argparse
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402
import architecture  # noqa: E402
import props  # noqa: E402
import lighting  # noqa: E402


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    helpers._collections.clear()
    import materials
    materials._cache.clear()
    scene = bpy.context.scene
    scene.name = "SeussKitchen"
    scene.unit_settings.system = 'METRIC'
    return scene


def build(props_=True):
    scene = reset()
    for c in ("Room", "Props", "Lights", "Cameras", "Outside"):
        helpers.coll(c)
    architecture.build()
    if props_:
        props.build()
    lighting.world()
    lighting.sun()
    lighting.fills()
    cams = lighting.stills()
    fly = lighting.flythrough(scene)
    scene.camera = cams["01_hero_wide"]
    return scene, cams, fly


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-props", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    a = ap.parse_args(argv)
    scene, cams, fly = build(props_=not a.no_props)
    lighting.render_settings(scene)
    n_obj = len(scene.objects)
    n_poly = sum(len(o.data.polygons) for o in scene.objects if o.type == 'MESH')
    print(f"scene built: {n_obj} objects, {n_poly} base polygons")
    if a.out:
        out = os.path.abspath(a.out)
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print("saved", out)


if __name__ == "__main__":
    main()
