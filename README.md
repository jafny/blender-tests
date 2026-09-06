# Oval Office — procedural Blender replica

A fully procedural, high-fidelity recreation of the White House Oval Office built with
Blender's Python API (`bpy` 4.2, Cycles). No external textures or assets are used: every
material (parquet sunburst floor, marble, brass, fabric, flags, paintings) is a node graph
and every object (Resolute desk, sofas, flags, tall-case clock, presidential seal…) is
generated from code.

## Deliverables

* `renders/stills/*.png` — 1080p still renders from six cameras
* `renders/flythrough.mp4` — 15 s camera flythrough (1280x720, 24 fps)

## Layout

```
oval_office/
  helpers.py       ellipse math, mesh builder, placement frames
  materials.py     procedural PBR materials
  architecture.py  elliptical walls with openings, cornice/cove, windows, doors, fireplace, exterior
  props.py         furniture and props
  lighting.py      sun/sky, light portals, cameras, flythrough animation, Cycles settings
  build_scene.py   assembles the scene (optionally saves a .blend)
  render.py        renders stills / animation frames
```

## Reproduce

```bash
pip install bpy==4.2.0 imageio-ffmpeg
cd oval_office
python3 build_scene.py --out ../oval_office.blend        # save a .blend to open in Blender
python3 render.py stills --samples 256 --res 1920 1080   # stills -> renders/stills
python3 render.py anim --samples 64 --res 1280 720       # frames -> renders/frames
ffmpeg -framerate 24 -i ../renders/frames/frame_%04d.png -c:v libx264 -pix_fmt yuv420p -crf 18 ../renders/flythrough.mp4
```

The scripts also run inside a full Blender install: `blender -b -P oval_office/build_scene.py -- --out scene.blend`.

## Room facts encoded

* 35'10" x 29' ellipse, 18'6" ceiling; 0.45 m walls
* Three tall south windows with gold drapes and swag valances; US and presidential flags between them
* Resolute desk (1.83 x 1.22 m) with carved presidential seal on the modesty panel
* Fireplace on the north wall with marble mantel, Swedish ivy, Washington portrait above
* East door: glass door to the Rose Garden colonnade; west, north-east and north-west six-panel doors
* Oak/walnut sunburst parquet, oval sunbeam rug with presidential seal, plaster seal medallion in the ceiling cove
* Two sofas, coffee table, wing chairs flanking the fireplace, side tables with lamps, Seymour tall-case clock, bookcases, busts and bronze
