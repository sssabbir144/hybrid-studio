"""Lighting and materials (Blender / bpy).

Three-point lighting (key / fill / rim), a world background, a Principled
material helper and palette application by object-name part.
"""

import math

from .character_manager import hex_to_rgba
from ._bpyutil import require_bpy
from .studio_log import get_logger

log = get_logger("hybrid_studio.lighting_materials")


def create_material(name, hex_color, roughness=0.6, metallic=0.0):
    """Create (or update) a Principled BSDF material from a hex colour."""
    bpy = require_bpy()
    rgba = hex_to_rgba(hex_color)  # validates the hex string clearly
    if not (0.0 <= roughness <= 1.0):
        raise ValueError("roughness must be in 0..1, got %r" % (roughness,))
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf is None:
        raise RuntimeError("material %r has no Principled BSDF node" % name)
    bsdf.inputs["Base Color"].default_value = rgba
    bsdf.inputs["Roughness"].default_value = float(roughness)
    bsdf.inputs["Metallic"].default_value = float(metallic)
    return mat


def _add_sun(bpy, name, location, rotation_deg, energy, color):
    data = bpy.data.lights.new(name=name, type="SUN")
    data.energy = energy
    data.color = hex_to_rgba(color)[:3]
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = tuple(math.radians(a) for a in rotation_deg)
    return obj


def three_point_lighting(prefix="LGT", key_energy=3.2, fill_energy=1.1, rim_energy=2.4):
    """Create key/fill/rim sun lights. Returns {role: object_name}."""
    bpy = require_bpy()
    lights = {}
    lights["Key"] = _add_sun(
        bpy, "%s_Key" % prefix, (4.0, -3.0, 6.0), (55.0, 0.0, 35.0), key_energy, "#FFF1D6"
    ).name
    lights["Fill"] = _add_sun(
        bpy, "%s_Fill" % prefix, (-5.0, -2.0, 3.0), (65.0, 0.0, -50.0), fill_energy, "#D6E8FF"
    ).name
    lights["Rim"] = _add_sun(
        bpy, "%s_Rim" % prefix, (0.0, 5.0, 4.5), (120.0, 0.0, 180.0), rim_energy, "#FFD9A0"
    ).name
    log.info("Three-point lighting created: %s", ", ".join(sorted(lights)))
    return lights


def set_world_background(hex_color="#1B2A3A", strength=0.55):
    """Set the world background colour/strength (creates a world if needed)."""
    bpy = require_bpy()
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    world = scene.world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg is None:
        raise RuntimeError("world node tree has no Background node")
    bg.inputs[0].default_value = hex_to_rgba(hex_color)
    bg.inputs[1].default_value = float(strength)
    log.info("World background set to %s (strength %.2f)", hex_color, strength)
    return world


def apply_palette_to_parts(parts, palette, material_prefix="MAT"):
    """Assign palette materials to objects by part-name suffix.

    ``parts``: {part: object_name}; ``palette``: {part: '#RRGGBB'}.
    Parts missing from the palette are skipped. Returns assigned mapping.
    """
    bpy = require_bpy()
    assigned = {}
    for part, obj_name in parts.items():
        if part not in palette:
            continue
        obj = bpy.data.objects.get(obj_name)
        if obj is None or obj.type != "MESH":
            log.warning("apply_palette: object %r missing or not a mesh; skipped", obj_name)
            continue
        mat = create_material("%s_%s" % (material_prefix, part), palette[part])
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        assigned[part] = obj_name
    log.info("Applied palette materials to: %s", ", ".join(sorted(assigned)) or "none")
    return assigned
