"""Build the Oval Office scene.  Usage (with the bpy pip module or blender -b -P):

    python3 build_scene.py [--out scene.blend] [--no-props]
"""
import os
import sys
import argparse
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers  # noqa: E402
import materials  # noqa: E402
import architecture  # noqa: E402
import lighting  # noqa: E402


def build(props=True):
    helpers.clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    M = materials.lib()
    info = architecture.build(M)
    if props:
        import props as P
        P.build(M, info)
    lighting.world()
    lighting.sun()
    lighting.portals(info)
    lighting.fire_light(info)
    cams = lighting.stills()
    fly = lighting.flythrough(scene)
    scene.camera = cams["01_hero_desk"]
    lighting.render_settings(scene)
    return scene, cams, fly


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-props", action="store_true")
    args = ap.parse_args(sys.argv[1:] if "--" not in sys.argv else sys.argv[sys.argv.index("--") + 1:])
    build(props=not args.no_props)
    if args.out:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.out))
        print("saved", args.out)
