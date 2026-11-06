#!/usr/bin/env python3
"""Stage-3 diagnostic probe: WHY do GP character colours not render?

Part A opens the saved production .blend and dumps, for every Grease
Pencil object: its material slots (name + GP colour) and the histogram
of stroke material_index values actually stored in the data.

Part B builds a controlled test with the toolkit's own functions,
exactly as the production script does: one GP object, two closed
circles, two materials (red / blue), material_index set per stroke.
It renders a tiny frame and counts red vs blue pixels in the result,
and also probes whether strokes can be made cyclic (needed for fill).

Usage:
    blender -b --python scripts/shalik_gp_probe.py -- <scene.blend> <out_dir>

Prints PROBE_A / PROBE_B lines and a final GP_PROBE: DONE marker.
"""

import math
import os
import sys
from collections import Counter

# Blender puts only this script's folder on sys.path; add the repo root
# so `import hybrid_studio` resolves (same bootstrap as the production
# script).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import bpy  # noqa: E402


def _circle(cx, cz, r, n=24):
    return [(cx + r * math.cos(2 * math.pi * i / n), 0.0,
             cz + r * math.sin(2 * math.pi * i / n)) for i in range(n + 1)]


def part_a(blend_path):
    print("PROBE_A opening:", blend_path)
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    found = 0
    for obj in bpy.data.objects:
        data = obj.data
        if data is None or not hasattr(data, "layers"):
            continue
        found += 1
        print("PROBE_A OBJ", obj.name, "type", obj.type)
        try:
            mats = list(data.materials)
        except Exception as exc:
            mats = []
            print("PROBE_A MATERIALS_ERROR", repr(exc))
        print("PROBE_A MAT_COUNT", len(mats))
        for i, mat in enumerate(mats):
            gps = getattr(mat, "grease_pencil", None)
            col = None
            fill = None
            if gps is not None:
                try:
                    col = tuple(round(float(c), 3) for c in gps.color)
                except Exception:
                    pass
                try:
                    fill = tuple(round(float(c), 3) for c in gps.fill_color)
                except Exception:
                    pass
            print("PROBE_A MAT", i, getattr(mat, "name", "?"),
                  "color", col, "fill", fill)
        counter = Counter()
        total = 0
        for layer in data.layers:
            for frame in layer.frames:
                drawing = getattr(frame, "drawing", None)
                if drawing is None:
                    continue
                for stroke in drawing.strokes:
                    counter[repr(getattr(stroke, "material_index",
                                         "NOATTR"))] += 1
                    total += 1
        print("PROBE_A STROKES", total, dict(counter))
    print("PROBE_A GP_OBJECTS", found)


def part_b(out_dir):
    from hybrid_studio import grease_pencil as gp

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 320
    scene.render.resolution_y = 180
    scene.render.image_settings.file_format = "PNG"
    try:
        scene.view_settings.view_transform = "Standard"
    except Exception as exc:
        print("PROBE_B VIEW_TRANSFORM", repr(exc))

    world = bpy.data.worlds.new("ProbeWorld")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is not None:
        bg.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
        bg.inputs["Strength"].default_value = 1.0

    obj = gp.create_gp_object(bpy, "ProbeTest")
    data = obj.data
    layer = gp._get_layer(data, "Figure")
    drawing = gp._get_drawing(layer, 1)
    red = gp._gp_material(bpy, data, "Probe_Red", "#E03131")
    blue = gp._gp_material(bpy, data, "Probe_Blue", "#1B5FE0")
    try:
        print("PROBE_B SLOTS", [m.name for m in data.materials])
        print("PROBE_B IDX red", list(data.materials).index(red),
              "blue", list(data.materials).index(blue))
    except Exception as exc:
        print("PROBE_B SLOTS_ERROR", repr(exc))

    s1 = gp._add_stroke(drawing, _circle(-0.55, 1.0, 0.35))
    s2 = gp._add_stroke(drawing, _circle(0.55, 1.0, 0.35))
    for label, stroke, idx in (("s1", s1, 0), ("s2", s2, 1)):
        try:
            stroke.material_index = idx
            print("PROBE_B SET", label, "-> readback",
                  getattr(stroke, "material_index", "NOATTR"))
        except Exception as exc:
            print("PROBE_B SET_ERROR", label, repr(exc))
        try:
            stroke.cyclic = True
            print("PROBE_B CYCLIC", label, "ok ->",
                  getattr(stroke, "cyclic", "NOATTR"))
        except Exception as exc:
            print("PROBE_B CYCLIC_ERROR", label, repr(exc))
    print("PROBE_B STROKE_ATTRS",
          [a for a in dir(s1)
           if "cycl" in a.lower() or "material" in a.lower()])

    # Camera + light, plain and frontal.
    cam_data = bpy.data.cameras.new("ProbeCam")
    cam = bpy.data.objects.new("ProbeCam", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = (0.0, -4.0, 1.0)
    cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    scene.camera = cam
    sun_data = bpy.data.lights.new("ProbeSun", type="SUN")
    sun = bpy.data.objects.new("ProbeSun", sun_data)
    bpy.context.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50.0), 0.0, math.radians(20.0))

    out_path = os.path.join(out_dir, "probe_render.png")
    scene.render.filepath = out_path
    bpy.ops.render.render(write_still=True)
    print("PROBE_B RENDERED", out_path)

    img = bpy.data.images.load(out_path)
    px = img.pixels[:]
    red_line = blue_line = pink_fill = lblue_fill = 0
    for i in range(0, len(px), 4):
        r, g, b = px[i], px[i + 1], px[i + 2]
        if r > 0.45 and r > g + 0.15 and r > b + 0.15:
            red_line += 1
        if b > 0.45 and b > r + 0.15 and b > g + 0.10:
            blue_line += 1
        if r > 0.80 and 0.45 < g < 0.86 and 0.45 < b < 0.86:
            pink_fill += 1
        if b > 0.80 and 0.45 < r < 0.86 and 0.45 < g < 0.86:
            lblue_fill += 1
    print("PROBE_B PIXELS red_line", red_line, "blue_line", blue_line,
          "pink_fill", pink_fill, "lightblue_fill", lblue_fill)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    blend_path = argv[0] if len(argv) > 0 else ""
    out_dir = argv[1] if len(argv) > 1 else "/tmp/gp_probe"
    os.makedirs(out_dir, exist_ok=True)
    if blend_path and os.path.exists(blend_path):
        part_a(blend_path)
    else:
        print("PROBE_A SKIPPED (no blend path)")
    part_b(out_dir)
    print("GP_PROBE: DONE")


main()
