"""Build the jungle set.  python3 build_scene.py [--out scene.blend] [--quick]

--quick builds fewer plants (for layout previews)."""
import os
import sys
import math
import time
import random
import argparse
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import helpers as H  # noqa: E402
import materials as M  # noqa: E402
import terrain as T  # noqa: E402
import plants as P  # noqa: E402
import ruins as RU  # noqa: E402
import vines as V  # noqa: E402
import fauna as F  # noqa: E402
import lighting as L  # noqa: E402

KAPOK = Vector((14.5, 9.0, 0))
FLOOR_PLANT = (6.6, -7.4)


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    H._collections.clear()
    H._inst_groups.clear()
    M._cache.clear()
    M._anim_inputs.clear()
    scene = bpy.context.scene
    scene.name = "Jungle"
    scene.unit_settings.system = 'METRIC'
    return scene


def slope(x, y, e=0.4):
    dx = T.height(x + e, y) - T.height(x - e, y)
    dy = T.height(x, y + e) - T.height(x, y - e)
    return math.hypot(dx, dy) / (2 * e)


def in_temple(x, y, pad=0.0):
    tx, ty = T.TEMPLE
    if abs(x - tx) < 5.6 + pad and abs(y - ty) < 4.7 + pad:
        return True
    return tx + 5.0 < x < tx + 8.2 + pad and abs(y - ty) < 2.5 + pad


class Keepout:
    """Discs (x, y, r) where a class of plants must not grow (camera positions, flight path, landmarks)."""

    def __init__(self):
        self.d = []

    def add(self, x, y, r):
        self.d.append((x, y, r))

    def ok(self, x, y, scale=1.0):
        return all((x - a) ** 2 + (y - b) ** 2 > (r * scale) ** 2 for a, b, r in self.d)


def place(pts, r, z_off=0.0, s=(0.8, 1.2), tilt=0.12):
    items = []
    for x, y in pts:
        z = T.height(x, y) + z_off
        items.append(((x, y, z), (r.uniform(-tilt, tilt), r.uniform(-tilt, tilt), r.uniform(0, H.TAU)), r.uniform(*s)))
    return items


def spread(name, assets, items, collection, r):
    """Distribute items over the asset variants and make one instancer per variant."""
    buckets = [[] for _ in assets]
    for it in items:
        buckets[r.randrange(len(assets))].append(it)
    for a, b in zip(assets, buckets):
        H.instancer(f"{name}_{a.name}", a, b, collection)


def vegetation(spots, keep_big, keep_small, quick=False):
    r = random.Random(2024)
    q = 0.25 if quick else 1.0
    A = H.coll(P.ASSETS)
    # ---- asset library
    clusters = [P.leaf_cluster(i, "canopy") for i in range(3)] + [P.leaf_cluster(10 + i, "canopy2") for i in range(3)]
    ferns = [P.fern(i) for i in range(6)]
    palms = [P.palm(100 + i) for i in range(5)]
    bananas = [P.banana(200 + i, fruit=(i == 0)) for i in range(4)]
    helis = [P.heliconia(300 + i) for i in range(3)]
    ears = [P.elephant_ear(400 + i) for i in range(4)]
    broms = [P.bromeliad(500 + i) for i in range(4)]
    seeds = [P.seedling(600 + i) for i in range(6)]
    sedges = [P.sedge(700 + i) for i in range(3)]
    litter = [P.litter_patch(800 + i) for i in range(4)]
    trees = [P.canopy_tree(900 + i, clusters=clusters[(i % 2) * 3:(i % 2) * 3 + 3]) for i in range(8)]
    # ---- hero kapok + fig
    kap, kpts, ktips = P.kapok(spots["kapok"], clusters=clusters[:3], epiphytes=broms[:2] + ferns[:2])
    fig_top = V.strangler_fig(clusters[3:])
    H.exclude(P.ASSETS)
    kx, ky = spots["kapok"].x, spots["kapok"].y
    hx, hy = T.HEAD
    lx = spots["log"]

    def land(x, y, wmin=0.4, smax=0.9):
        return T.water_dist(x, y) > wmin and slope(x, y) < smax

    def free(x, y, rk=5.5, rt=0.0):
        return (x - kx) ** 2 + (y - ky) ** 2 > rk ** 2 and (x - hx) ** 2 + (y - hy) ** 2 > 2.6 ** 2 and not in_temple(x, y, rt)

    A_ = (T.X0 + 2, T.X1 - 2, T.Y0 + 2, T.Y1 - 2)
    NEAR = (-34, 34, -30, 40)
    t = time.time()
    # canopy trees: everywhere except the river corridor, clearings and camera sightlines
    pts = H.scatter(lambda x, y: land(x, y, 6.5, 0.9) and free(x, y, 11.0, 2.5) and keep_big.ok(x, y, 1.6), A_, int(110 * q), 1, 6.5)
    spread("Trees", trees, place(pts, r, -0.4, (0.75, 1.25), 0.05), "Forest", r)
    anchors = [Vector((x, y, T.height(x, y) + r.uniform(13, 18))) for x, y in pts if abs(x) < 22 and -20 < y < 30][:30]
    # palms along the banks and the plateau
    pts = H.scatter(lambda x, y: land(x, y, 0.8, 0.8) and free(x, y, 7.0, 1.5) and keep_big.ok(x, y, 1.2)
                    and T.water_dist(x, y) < 9.0, NEAR, int(60 * q), 2, 3.5)
    spread("Palms", palms, place(pts, r, -0.2, (0.8, 1.25), 0.2), "Forest", r)
    # bananas & heliconias in the moist strip near the water
    pts = H.scatter(lambda x, y: land(x, y, 0.8, 0.7) and free(x, y, 6.0, 1.0) and keep_big.ok(x, y)
                    and T.water_dist(x, y) < 6.0, NEAR, int(80 * q), 3, 2.2)
    spread("Bananas", bananas, place(pts, r, -0.05, (0.8, 1.15), 0.1), "Understory", r)
    pts = H.scatter(lambda x, y: land(x, y, 0.5, 0.8) and free(x, y, 6.0, 0.6) and keep_big.ok(x, y, 0.8), NEAR, int(110 * q), 4, 1.6)
    spread("Heliconias", helis, place(pts, r, -0.03, (0.8, 1.2), 0.1), "Understory", r)
    # elephant ears
    pts = H.scatter(lambda x, y: land(x, y, 0.3, 0.9) and free(x, y, 5.5, 0.3) and keep_big.ok(x, y, 0.7), NEAR, int(320 * q), 5, 1.4)
    spread("ElephantEars", ears, place(pts, r, -0.02, (0.8, 1.3), 0.1), "Understory", r)
    # ferns: the main ground cover (also on the plaza, ledges and the plateau)
    pts = H.scatter(lambda x, y: land(x, y, 0.2, 1.4) and free(x, y, 4.6, -0.6) and keep_small.ok(x, y), A_, int(2600 * q), 6, 0.7)
    spread("Ferns", ferns, place(pts, r, -0.02, (0.7, 1.4), 0.15), "Understory", r)
    pts = H.scatter(lambda x, y: land(x, y, 0.2, 1.2) and free(x, y, 4.6, 0.0) and keep_small.ok(x, y, 0.5), NEAR, int(500 * q), 7, 0.6)
    spread("Bromeliads", broms, place(pts, r, -0.01, (0.8, 1.5), 0.15), "Understory", r)
    pts = H.scatter(lambda x, y: land(x, y, 0.1, 1.5) and free(x, y, 4.0, -0.4), NEAR, int(4000 * q), 8, 0.25)
    spread("Seedlings", seeds, place(pts, r, -0.01, (0.6, 1.6), 0.2), "Understory", r)
    pts = H.scatter(lambda x, y: -0.2 < T.water_dist(x, y) < 1.4 and keep_small.ok(x, y, 0.6) and free(x, y, 4.0, 0.0),
                    NEAR, int(700 * q), 9, 0.45)
    spread("Sedges", sedges, place(pts, r, -0.05, (0.7, 1.3), 0.2), "Understory", r)
    pts = H.scatter(lambda x, y: T.water_dist(x, y) > 0.3 and free(x, y, 3.8, -0.8), NEAR, int(2400 * q), 10, 0.9)
    spread("Litter", litter, place(pts, r, 0.0, (0.8, 1.3), 0.0), "Understory", r)
    print(f"[veg] scattered in {time.time() - t:.1f}s", flush=True)
    # hero plants for the macro shot
    fx, fy = FLOOR_PLANT
    H.instancer("Hero_Bromeliad", broms[1], [((fx, fy, T.height(fx, fy) - 0.02), (0, 0, 0.4), 1.5)], "Understory")
    H.instancer("Hero_Fern", ferns[2], [((fx + 1.0, fy + 1.6, T.height(fx + 1.0, fy + 1.6) - 0.02), (0, 0, 1.0), 1.3),
                                        ((fx - 1.4, fy + 1.9, T.height(fx - 1.4, fy + 1.9) - 0.02), (0, 0, 2.0), 1.1)], "Understory")
    H.instancer("Hero_Heliconia", helis[0], [((fx + 0.2, fy + 2.4, T.height(fx + 0.2, fy + 2.4) - 0.02), (0, 0, 0.0), 1.2)], "Understory")
    # epiphytes on the fallen log
    items = []
    for k in range(6):
        p = spots["log_pts"][4 + k * 6]
        items.append(((p.x, p.y, p.z + 0.4), (0, 0, r.uniform(0, H.TAU)), r.uniform(0.6, 1.0)))
    H.instancer("Log_Bromeliads", broms[2], items[::2], "Understory")
    H.instancer("Log_Ferns", ferns[4], items[1::2], "Understory")
    return kpts, ktips, anchors, fig_top


def build(quick=False):
    scene = reset()
    for c in ("Terrain", "Water", "Rocks", "Ruins", "Trees", "Forest", "Understory", "Vines", "Fauna", "Lights",
              "Cameras", "Atmosphere"):
        H.coll(c)
    t0 = time.time()
    ground, logpts = T.build()
    print(f"[terrain] {time.time() - t0:.1f}s", flush=True)
    ru = RU.build()
    kz = T.height(KAPOK.x, KAPOK.y)
    lc = logpts[len(logpts) // 2]
    fx, fy = FLOOR_PLANT
    falls_foot = Vector((T.LIP_X, T.cliff_y(T.LIP_X) - 1.6, 0.0))
    spots = {
        "temple": ru["top"], "kapok": Vector((KAPOK.x, KAPOK.y, kz)), "falls": falls_foot, "log": lc, "log_pts": logpts,
        "stair_foot": ru["stair_foot"], "head": ru["head"],
        "floor": Vector((fx - 0.7, fy - 1.6, T.height(fx - 0.7, fy - 1.6) + 0.45)),
        "floor_aim": Vector((fx, fy, T.height(fx, fy) + 0.3)),
        "brom_top": Vector((fx + 0.05, fy - 0.02, T.height(fx, fy) + 0.36)),
        "falls_view": falls_foot + Vector((2.0, -6.0, 0.0)),
        "kapok_front": Vector((KAPOK.x - 6, KAPOK.y - 4, T.height(KAPOK.x - 6, KAPOK.y - 4))),
        "river_mid": Vector((T.river_x(-6), -6.0, 0.0)),
    }
    L.set_shots(spots)
    L.set_fly(spots)
    keep_big, keep_small = Keepout(), Keepout()
    for name, (loc, aim, *_ ) in L.STILLS.items():
        keep_big.add(loc[0], loc[1], 2.8)
        keep_small.add(loc[0], loc[1], 1.1)
        if name.startswith("05"):
            keep_big.add(loc[0], loc[1], 5.0)
        # keep the first few metres of each sightline clear of big plants
        d = Vector(aim) - Vector(loc)
        d.z = 0
        if d.length > 1e-3:
            d.normalize()
            for s in (2.0, 4.0):
                keep_big.add(loc[0] + d.x * s, loc[1] + d.y * s, 1.8)
    fly = [k[1] for k in L.FLY_KEYS]
    for a, b in zip(fly, fly[1:]):
        for i in range(8):
            p = Vector(a).lerp(Vector(b), i / 8)
            if p.z < 7:
                keep_big.add(p.x, p.y, 2.6)
                keep_small.add(p.x, p.y, 0.6)
    kpts, ktips, anchors, fig_top = vegetation(spots, keep_big, keep_small, quick)
    print(f"[vegetation] {time.time() - t0:.1f}s", flush=True)
    V.lianas(ktips, kpts, anchors + [fig_top])
    V.cliff_curtain()
    print(f"[vines] {time.time() - t0:.1f}s", flush=True)
    F.build(spots)
    L.world()
    L.sun()
    L.bounce()
    L.haze()
    L.fleck(spots["floor_aim"])
    cams = L.stills()
    fly = L.flythrough(scene)
    L.animate_textures(scene)
    scene.camera = cams["01_hero_river"]
    return scene, cams, fly


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--quick", action="store_true")
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    a = ap.parse_args(argv)
    scene, cams, fly = build(quick=a.quick)
    L.render_settings(scene)
    n_obj = len(scene.objects)
    n_poly = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
    print(f"scene built: {n_obj} objects, {n_poly} base polygons (before instancing)")
    if a.out:
        out = os.path.abspath(a.out)
        bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
        print("saved", out)


if __name__ == "__main__":
    main()
