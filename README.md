# Blender procedural sets

Three fully procedural Blender scenes generated with the `bpy` 4.2 Python module (Cycles, CPU).
No external textures or assets: every material is a node graph and every object is built from code.

* [Jungle](#jungle) — `jungle/`
* [Dr. Seuss kitchen](#dr-seuss-kitchen) — `seuss_kitchen/`
* [Oval Office replica](#oval-office--procedural-blender-replica) — `oval_office/`

# Jungle

A lush, fully procedural rainforest set: a river winds up a valley to a pool fed by a waterfall pouring
off a mossy basalt cliff; an overgrown Maya-style stepped temple with a strangler fig gripping its tiers
stands on the west bank beside a half-buried colossal stone head; a giant kapok (ceiba) with plank
buttress roots towers over the east bank; a mossy fallen log bridges the river. Thousands of ferns,
palms, bananas, heliconias, elephant ears, bromeliads, sedges and seedlings carpet the floor under a
canopy of rainforest trees, lianas loop down from the limbs, roots and vines curtain the cliff, a humid
haze catches the sunbeams, and blue morpho butterflies flutter through.

## Deliverables

* `jungle.blend` — the scene (cameras, flythrough animation, animated water and render settings included)
* `renders/jungle_stills/*.png` — 1080p stills from eight cameras (Cycles + OIDN denoise)
* `renders/jungle_flythrough.mp4` — camera flythrough along the river, past the temple, up to the falls

## Layout

```
jungle/
  helpers.py      mesh builder with attributes, parallel-transport tubes, the leaf generator, GN point instancer, scatter
  materials.py    leaves (veins, edge burn, translucency), bark, palm trunk, stone (+carvings, moss, wet line), forest floor, water, falls, foam, haze, mist, morpho wings
  terrain.py      river valley heightfield, pool, cliff + plunge alcove, waterfall sheets, foam, spray, boulders, cliff outcrops, fallen log
  plants.py       fern, palm, banana, heliconia, elephant ear, bromeliad, seedling, sedge, leaf litter, leaf sprays, canopy trees, the kapok
  ruins.py        stepped pyramid of individual eroded blocks, stairway, corbel-vaulted shrine + roof comb, collapse + rubble, stelae, colossal head
  vines.py        lianas, cliff root curtain, strangler fig on the temple, leafy climbers
  fauna.py        flapping blue morpho butterflies
  lighting.py     Nishita sky, sun, canopy bounce, sun fleck, haze volume, cameras, flythrough, texture animation, Cycles settings
  build_scene.py  asset library + scattering (keep-out zones around cameras/flight path), assembles the scene
  render.py       renders stills / animation frames
  encode.sh       frames -> mp4
```

## Reproduce

```bash
pip install bpy==4.2.0 imageio-ffmpeg     # bpy 4.2 needs Python 3.11
cd jungle
python3 build_scene.py --out ../jungle.blend                                   # ~30 s, saves the .blend
python3 render.py stills --samples 96 --res 1920 1080 --out ../renders/jungle_stills
python3 render.py anim --samples 10 --res 960 540 --out ../renders/jungle_frames
./encode.sh ../renders/jungle_frames ../renders/jungle_flythrough.mp4
python3 render.py stills --quick --samples 16 --res 640 360 --out /tmp/preview   # fast layout preview (¼ of the plants)
```

## How it is made

* **Leaves are geometry, not alpha cards.** `helpers.leaf()` grows a blade along a spine that droops,
  twists and V-folds, with an optional heart lobe and lateral tears (banana leaves). Every vertex stores
  `luv` = (along, across, per-leaf random) so the shader can draw the midrib, lateral veins, yellowed or
  browned edges and per-leaf colour shifts; a translucent BSDF mixed in makes backlit leaves glow.
* **Instancing keeps it light.** Each plant variant is built once (from a seed) into an excluded `Assets`
  collection; scattered points carry `rot`/`scl` attributes and a geometry-nodes modifier instances the
  asset on them. Canopy trees are whole collections (trunk + their own leaf-spray instancers), so the
  instances nest. Hundreds of thousands of leaves cost only a few MB.
* **Scattering with intent.** Dart-throwing with per-species rules — bananas and sedges hug the water,
  trees stay out of the river corridor (the canopy gap lets light in), nothing grows on the temple, the
  head or between the kapok's buttresses — plus keep-out discs around every camera, its first metres of
  sightline and the flythrough path.
* **Terrain** is one heightfield function shared by the mesh and the scatterer: a meandering channel,
  a pool, banks rising into valley walls, a flattened temple plaza and a curved cliff with a plunge
  alcove behind the falls; steep vertices are pushed around with 3D noise and dozens of boulder
  outcrops break up the cliff face.
* **The temple** is hundreds of individually eroded blocks (superellipse lofts with noise chipping) laid in
  courses with jitter, missing stones, a collapsed corner whose blocks spill downhill, and a strangler
  fig whose roots are traced over the stepped surface tier by tier.
* **Water**: a refractive surface with a green absorption volume and flowing ripples, waterfall curtains
  that roll over the lip and fall on a parabola with scrolling streaks and gaps, foam discs, a spray
  volume and a light humid haze for sunbeams. Water, falls and foam textures are keyframed to flow.
* **Light**: Nishita sky, a south-east sun, a soft green canopy-bounce area light (excluded from the
  volume) and a sun-fleck spot for the forest-floor close-up; AgX view transform.

# Dr. Seuss kitchen

A picture-book kitchen where nothing is straight: bulging walls, a domed ceiling, wobbly porthole
windows, pillowy cabinet doors with oversized ball knobs, a leaning bulbous fridge, a stove with
coil burners and a bendy hood pipe, a loop-de-loop faucet, a twisted-pedestal table with curly-backed
chairs, striped pendant lamps, jars, pans, a plant and a wonky clock — all in candy colours with ink
outlines (Freestyle), and truffula trees on the hills outside.

## Deliverables

* `seuss_kitchen.blend` — the scene (cameras, flythrough animation and render settings included)
* `renders/seuss_stills/*.png` — 1080p still renders from eight cameras (Cycles, 128 spp + OIDN denoise)
* `renders/seuss_flythrough.mp4` — 12.5 s camera flythrough (300 frames, 1280x720, 24 fps, 16 spp + OIDN denoise)

## Layout

```
seuss_kitchen/
  helpers.py       lofted "wobbly" primitives (blob, lathe, slab, tube, torus…), NURBS tubes with per-point radius
  materials.py     candy colours, stripes, polka dots, wavy checkerboard, wainscot wall, alpha-mask cut-outs
  architecture.py  bulging room shell + dome, floor, windows, door, trim piping, outside (hills, truffula trees, clouds)
  props.py         cabinets, counter, sink, stove/hood, fridge, upper cabinets, shelves, table, chairs, lamps, clutter
  lighting.py      sky world, sun, fill lights, cameras, flythrough keys, Cycles + Freestyle settings
  build_scene.py   assembles the scene (optionally saves a .blend)
  render.py        renders stills / animation frames
  encode.sh        frames -> mp4
```

## Reproduce

```bash
pip install bpy==4.2.0 imageio-ffmpeg
cd seuss_kitchen
python3 build_scene.py --out ../seuss_kitchen.blend                       # save the .blend
python3 render.py stills --samples 128 --res 1920 1080 --out ../renders/seuss_stills
python3 render.py anim --samples 16 --res 1280 720 --out ../renders/seuss_frames
./encode.sh ../renders/seuss_frames ../renders/seuss_flythrough.mp4       # frames -> mp4
```

The scripts also run inside a full Blender install: `blender -b -P seuss_kitchen/build_scene.py -- --out scene.blend`.

## How the Seuss look is made

* **Nothing is straight.** Every box is a loft of superellipse rings with mid-height bulge, lean, taper,
  twist and a sinusoidal wobble, then smoothed with a subdivision surface (`helpers.blob`).
  Doors and drawer fronts are "pillows" (the same loft with a cushion profile turned on its side).
* **Curls everywhere.** Faucet, chair backs, cabinet finials, shelf brackets, steam and hooks are NURBS
  curves with a bevel and a per-point radius that tapers to a point (`helpers.tube`, `curl_top`).
* **Candy materials.** Stripes, polka dots and the wavy checker floor are procedural node graphs in
  object space with a small noise warp so every edge looks hand-drawn.
* **Window openings** are alpha masks in the wall material (wobbly ellipses evaluated in shader nodes) —
  the pip build of `bpy` has a non-functional boolean modifier, and a masked single-surface wall is
  cheaper to render anyway. The sink cut-out in the counter works the same way.
* **Ink outlines** come from Freestyle (silhouette + crease + border lines, view-culled, with a
  slightly varying stroke thickness).

# Oval Office — procedural Blender replica

A fully procedural, high-fidelity recreation of the White House Oval Office built with
Blender's Python API (`bpy` 4.2, Cycles). No external textures or assets are used: every
material (parquet sunburst floor, marble, brass, fabric, flags, paintings) is a node graph
and every object (Resolute desk, sofas, flags, tall-case clock, presidential seal…) is
generated from code.

## Deliverables

* `renders/stills/*.png` — 1080p still renders from six cameras (Cycles, 128 spp + OIDN denoise)
* `renders/flythrough.mp4` — 12.5 s camera flythrough (300 frames, 1280x720, 24 fps, 24 spp + OIDN denoise)

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
python3 render.py anim --samples 24 --res 1280 720       # frames -> renders/frames
./encode.sh                                              # frames -> renders/flythrough.mp4
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
