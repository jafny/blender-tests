"""Render stills or flythrough frames.

    python3 render.py stills  [--samples 256] [--res 1920 1080] [--pct 100] [--only NAME ...] [--out DIR]
    python3 render.py anim    [--samples 64]  [--res 1280 720]  [--start 1] [--end 360] [--out DIR]
    python3 render.py frame N [--samples 32] ...   (single flythrough frame, for previews)
"""
import os
import sys
import time
import argparse
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_scene  # noqa: E402
import lighting  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["stills", "anim", "frame"])
    ap.add_argument("n", nargs="?", type=int, default=1)
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--res", type=int, nargs=2, default=None)
    ap.add_argument("--pct", type=int, default=100)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--end", type=int, default=lighting.FLY_FRAMES)
    ap.add_argument("--no-props", action="store_true")
    ap.add_argument("--save", default=None, help="also save .blend here")
    a = ap.parse_args()
    scene, cams, fly = build_scene.build(props=not a.no_props)
    if a.save:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(a.save))
    anim = a.mode != "stills"
    samples = a.samples or (64 if anim else 256)
    res = tuple(a.res) if a.res else ((1280, 720) if anim else (1920, 1080))
    lighting.render_settings(scene, samples=samples, res=res, pct=a.pct, animation=anim)
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "renders", "stills" if a.mode == "stills" else "frames")
    os.makedirs(out, exist_ok=True)
    if a.mode == "stills":
        for name, cam in cams.items():
            if a.only and name not in a.only:
                continue
            scene.camera = cam
            scene.frame_set(1)
            scene.render.filepath = os.path.join(out, name + ".png")
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"[still] {name} {time.time() - t:.1f}s", flush=True)
    else:
        scene.camera = fly
        frames = [a.n] if a.mode == "frame" else range(a.start, a.end + 1)
        for f in frames:
            path = os.path.join(out, f"frame_{f:04d}.png")
            if a.mode == "anim" and os.path.exists(path):
                continue
            scene.frame_set(f)
            scene.render.filepath = path
            t = time.time()
            bpy.ops.render.render(write_still=True)
            print(f"[frame] {f} {time.time() - t:.1f}s", flush=True)


if __name__ == "__main__":
    main()
