"""Production build: "শালিক পাখির দুঃখ আর বুড়ি মা" (30s Shorts, 9:16).

HYBRID style (owner's pick, Step 6): 3D environment built in Blender +
2D characters drawn with Grease Pencil inside the same 3D world.

Run inside Blender 5.2.3:
    blender -b --python scripts/shalik_production.py -- --qc --out <dir>
    blender -b --python scripts/shalik_production.py -- --out <dir>

Modes:
    (default)  build the scene, save shalik_scene.blend into <dir>
    --qc       additionally render one hero still per shot into <dir>/qc

Stage-1 scope (blocking pass): composition, camera, timing, mood and
character placement with proxy GP drawings. Detail/refinement comes
after the owner's QC verdict - the full render is NOT part of Stage 1.
"""

import math
import os
import sys

# Repo-root bootstrap: Blender only adds this script's own folder
# (scripts/) to sys.path in background mode, so `import hybrid_studio`
# fails without this. (Found in the Stage-1 QC run, 2026-11-06.)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import bpy

from hybrid_studio import check_environment, _bpyutil
from hybrid_studio import cinematography, lighting_materials
from hybrid_studio import grease_pencil as gp
from hybrid_studio import animation as anim
from hybrid_studio.config import load_config

FPS = 24
FRAME_END = 720  # 30 s at 24 fps

# Shot plan: (name, start, end, cam_loc, target_loc, hero_frame)
SHOTS = [
    ("S1_Dawn_Call",      1,   96,  (0.0, -7.5, 1.9),  (0.0, 0.6, 1.0),  48),
    ("S2_Hand_Feeding",   97,  192, (0.9, -2.4, 1.5),  (0.3, 1.2, 0.9),  144),
    ("S3_Days_Ritual",    193, 312, (-2.6, -5.5, 2.2), (0.0, 0.6, 1.1),  252),
    ("S4_Empty_Door",     313, 408, (0.4, -4.2, 1.6),  (-1.2, 2.0, 1.1), 360),
    ("S5_Window_Peck",    409, 528, (1.7, -2.8, 1.9),  (1.4, 2.1, 1.6),  468),
    ("S6_Last_Offering",  529, 648, (0.0, -4.6, 1.7),  (0.2, 1.0, 0.9),  576),
    ("S7_Golden_Farewell", 649, 720, (0.0, -8.5, 3.0), (0.2, 1.0, 1.1),  690),
]

VERANDA = (0.3, 1.55, 0.14)      # where Buri Ma sits
BIRD_HAND = (0.78, 1.32, 0.62)   # beside her offering hand
TREE_BRANCH = (-2.9, 0.4, 2.35)  # bird's home branch
WINDOW_SILL = (1.4, 1.98, 1.24)  # S5 perch


def _mat(name, hex_color, roughness=0.85):
    return lighting_materials.create_material(name, hex_color, roughness)


def _box(name, location, scale, material):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    if material:
        obj.data.materials.append(material)
    return obj


def _cylinder(name, location, radius, depth, material):
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=depth,
                                        location=location)
    obj = bpy.context.active_object
    obj.name = name
    if material:
        obj.data.materials.append(material)
    return obj


def _sphere(name, location, scale, material):
    bpy.ops.mesh.primitive_uv_sphere_add(location=location)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = scale
    bpy.ops.object.transform_apply(scale=True)
    if material:
        obj.data.materials.append(material)
    return obj


def build_environment():
    """3D courtyard set: mud house, veranda, door, window, mango tree."""
    mud = _mat("MudWall", "#B08968")
    mud_dark = _mat("MudDark", "#7A5C3E")
    roof_m = _mat("Roof", "#5D4128")
    earth = _mat("Earth", "#9C7A54")
    wood = _mat("Wood", "#6B4A2F")
    leaf = _mat("Leaf", "#4A7C3A")
    dark = _mat("DarkOpen", "#1A120B")
    brass = _mat("Brass", "#C9A227", 0.35)

    # Courtyard ground + house wall + roof + veranda.
    ground = _box("Courtyard", (0, 0, -0.05), (7, 6, 0.05), earth)
    _box("HouseWall", (0, 2.35, 1.6), (3.6, 0.18, 1.6), mud)
    _box("Roof", (0, 2.15, 3.35), (3.9, 0.85, 0.09), roof_m)
    _box("VerandaFloor", (0, 1.55, 0.07), (3.4, 0.75, 0.07), mud_dark)
    for x in (-3.1, 3.1):
        _box("VerandaPost", (x, 0.95, 1.15), (0.07, 0.07, 1.15), wood)
    _box("VerandaBeam", (0, 0.95, 2.28), (3.3, 0.08, 0.08), wood)
    # Door (dark opening) + window with frame and sill.
    _box("Door", (-1.2, 2.14, 1.0), (0.45, 0.03, 1.0), dark)
    _box("Window", (1.4, 2.14, 1.65), (0.42, 0.03, 0.42), dark)
    _box("WindowSill", (1.4, 1.98, 1.2), (0.5, 0.09, 0.04), wood)
    # Mango tree (bird's home) + low fence + rice bowl prop.
    _cylinder("TreeTrunk", (-3.1, 0.4, 1.0), 0.16, 2.0, wood)
    for loc, sc in [((-3.1, 0.4, 2.5), (1.15, 1.0, 0.8)),
                    ((-2.3, 0.3, 2.2), (0.8, 0.7, 0.6)),
                    ((-3.9, 0.5, 2.25), (0.85, 0.75, 0.62))]:
        _sphere("TreeCanopy", loc, sc, leaf)
    for x in (-5.4, -4.6, 4.6, 5.4):
        _box("FencePost", (x, -1.8, 0.45), (0.05, 0.05, 0.45), wood)
    bowl = _cylinder("RiceBowl", (0.82, 1.28, 0.2), 0.17, 0.09, brass)
    return bowl


def _circle(cx, cz, r, n=18):
    return [(cx + r * math.cos(2 * math.pi * i / n), 0.0,
             cz + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def _line(points):
    return [(x, 0.0, z) for (x, z) in points]


def build_buri_ma():
    """2D Grease Pencil character: seated old mother, white sari."""
    obj = gp.create_gp_object(bpy, "BuriMa")
    data = obj.data
    layer = gp._get_layer(data, "Figure")
    drawing = gp._get_drawing(layer, 1)
    gp._gp_material(bpy, data, "BuriMa_Line", "#EDEAE2")
    strokes = [
        _circle(0.0, 1.30, 0.145),                      # head
        _circle(0.10, 1.47, 0.05, 10),                  # hair bun
        _line([(-0.13, 1.16), (0.13, 1.16)]),            # shoulders
        _line([(-0.13, 1.16), (-0.34, 0.18)]),          # sari left drape
        _line([(0.13, 1.16), (0.30, 0.18)]),            # sari right drape
        _line([(-0.34, 0.18), (0.30, 0.18)]),           # seated base
        _line([(-0.30, 0.45), (0.34, 0.45)]),           # lap fold
        _line([(0.12, 1.05), (0.42, 0.62)]),            # offering arm
        _line([(0.42, 0.62), (0.50, 0.60)]),            # open palm
        _line([(-0.10, 0.20), (-0.16, 0.02)]),          # foot left
        _line([(0.14, 0.20), (0.22, 0.02)]),            # foot right
    ]
    for pts in strokes:
        gp._add_stroke(drawing, pts)
    obj.location = VERANDA
    return obj


def build_shalik():
    """2D Grease Pencil character: shalik (myna) bird, brown + yellow."""
    obj = gp.create_gp_object(bpy, "Shalik")
    data = obj.data
    layer = gp._get_layer(data, "Figure")
    drawing = gp._get_drawing(layer, 1)
    gp._gp_material(bpy, data, "Shalik_Line", "#8A6A48")
    body = [(0.15 * math.cos(2 * math.pi * i / 18), 0.0,
             0.20 + 0.105 * math.sin(2 * math.pi * i / 18)) for i in range(19)]
    strokes = [
        body,                                           # body ellipse
        _circle(0.155, 0.335, 0.072, 14),               # head
        _line([(0.22, 0.34), (0.325, 0.315)]),          # beak top
        _line([(0.325, 0.315), (0.215, 0.30)]),         # beak bottom
        _line([(-0.13, 0.16), (-0.30, 0.03)]),          # tail upper
        _line([(-0.13, 0.12), (-0.295, 0.005)]),        # tail lower
        _line([(-0.02, 0.10), (-0.02, 0.0)]),           # leg left
        _line([(0.05, 0.10), (0.05, 0.0)]),             # leg right
        _circle(0.175, 0.35, 0.016, 8),                 # eye
    ]
    for pts in strokes:
        gp._add_stroke(drawing, pts)
    obj.location = TREE_BRANCH
    return obj


def animate_characters(ma, bird):
    """Object-level keyframes across the 7 shots (24 fps, frames 1-720)."""
    def key(obj, frame, loc=None, rot=None):
        anim.keyframe_transform(obj, frame, location=loc, rotation_euler=rot)

    # --- Buri Ma: gentle bob; indoors (hidden) S4-S5; frail rise in S6.
    key(ma, 1, VERANDA)
    key(ma, 96, (VERANDA[0], VERANDA[1], VERANDA[2] + 0.02))
    key(ma, 192, VERANDA)
    key(ma, 312, (VERANDA[0], VERANDA[1], VERANDA[2] + 0.02))
    key(ma, 313, (0.3, 3.1, 0.14))            # inside the house
    key(ma, 528, (0.3, 3.1, 0.14))
    key(ma, 545, (0.3, 1.55, 0.05))           # returns, seated lower
    key(ma, 648, (0.3, 1.55, 0.07))
    key(ma, 720, (0.3, 1.55, 0.07))

    # --- Shalik: flight, feeding, waiting, window, farewell.
    key(bird, 1, TREE_BRANCH)
    key(bird, 55, (0.9, 0.6, 1.5))            # flight arc
    key(bird, 85, BIRD_HAND)                  # lands by her hand
    for f, dz in [(110, -0.05), (122, 0.0), (140, -0.05), (152, 0.0),
                  (170, -0.05), (182, 0.0)]:  # feeding pecks (S2)
        key(bird, f, (BIRD_HAND[0], BIRD_HAND[1], BIRD_HAND[2] + dz))
    key(bird, 240, (0.95, 1.25, 0.35))        # S3 hops near her
    key(bird, 290, BIRD_HAND)
    key(bird, 313, (0.0, -0.5, 0.02))         # S4: alone in the courtyard
    key(bird, 360, (0.15, -0.45, 0.02))
    key(bird, 408, (0.0, -0.5, 0.02))
    key(bird, 425, (0.8, 0.6, 1.6))           # S5: flies to the window
    key(bird, 450, WINDOW_SILL)
    for f, dx in [(470, 0.05), (482, 0.0), (500, 0.05), (512, 0.0)]:
        key(bird, f, (WINDOW_SILL[0] + dx, WINDOW_SILL[1], WINDOW_SILL[2]))
    key(bird, 545, (0.9, 1.28, 0.3))          # S6: comes down beside her
    key(bird, 576, (0.9, 1.28, 0.3), (0.35, 0.0, 0.0))   # head bowed
    key(bird, 648, (0.9, 1.28, 0.3), (0.35, 0.0, 0.0))
    key(bird, 680, (0.52, 1.48, 1.32), (0.15, 0.0, 0.0))  # S7: her shoulder
    key(bird, 720, (0.52, 1.48, 1.32), (0.15, 0.0, 0.0))


def setup_camera_and_lights():
    cam = cinematography.create_camera("StoryCam", SHOTS[0][3], 40.0)
    cinematography.look_at(cam, SHOTS[0][4])
    target = bpy.data.objects.get("CameraTarget")
    for (_name, start, end, loc, tgt, _hero) in SHOTS:
        anim.keyframe_transform(cam, start, location=loc)
        anim.keyframe_transform(cam, end, location=loc)
        if target is not None:
            anim.keyframe_transform(target, start, location=tgt)
            anim.keyframe_transform(target, end, location=tgt)
    # S7 slow pull-back (re-key the segment with a moving end point).
    anim.keyframe_transform(cam, 649, location=(0.0, -4.6, 1.7))
    anim.keyframe_transform(cam, 720, location=(0.0, -8.5, 3.0))
    # Cuts between shots, smooth only inside S7: set interpolation.
    for action in {cam.animation_data.action if cam.animation_data else None,
                   target.animation_data.action if target and
                   target.animation_data else None}:
        if action is None:
            continue
        for fc in _bpyutil.collect_fcurves(action):
            for point in fc.keyframe_points:
                point.interpolation = (
                    "BEZIER" if point.co[0] >= 649 else "CONSTANT")
    lighting_materials.three_point_lighting("LGT")
    lighting_materials.set_world_background("#35486B", 0.45)
    return cam


def main():
    check_environment()
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    out_dir = "."
    if "--out" in args:
        out_dir = args[args.index("--out") + 1]
    os.makedirs(out_dir, exist_ok=True)

    # Clean default scene.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start, scene.frame_end = 1, FRAME_END
    cfg = load_config(None)
    from hybrid_studio import render_manager
    render_manager.apply_render_config(
        scene, cfg, "production", out_dir)
    scene.render.resolution_x, scene.render.resolution_y = 1080, 1920
    scene.render.resolution_percentage = 100
    _bpyutil.set_image_format(scene.render.image_settings, "PNG")

    build_environment()
    ma = build_buri_ma()
    bird = build_shalik()
    animate_characters(ma, bird)
    for obj in (ma, bird):
        if obj.animation_data and obj.animation_data.action:
            anim.apply_easing(obj.animation_data.action)
    setup_camera_and_lights()
    from hybrid_studio import compositing
    compositing.setup_compositor(scene)

    blend_path = os.path.join(out_dir, "shalik_scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=blend_path)
    print("Saved:", blend_path)

    if "--qc" in args:
        qc_dir = os.path.join(out_dir, "qc")
        os.makedirs(qc_dir, exist_ok=True)
        for (name, _s, _e, _loc, _tgt, hero) in SHOTS:
            scene.frame_set(hero)
            scene.render.filepath = os.path.join(
                qc_dir, "%s_f%04d.png" % (name, hero))
            bpy.ops.render.render(write_still=True)
            print("QC still:", scene.render.filepath)
    print("SHALIK_PRODUCTION: BUILD OK")


if __name__ == "__main__":
    main()
