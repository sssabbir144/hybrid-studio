"""3D modeling (Blender / bpy).

Builds a simple, original cartoon character from bevelled primitives plus a
small stylized environment (ground, trees, rocks). Objects are named with a
character prefix so rigging, lighting and QC can find them reliably.

Character proportions (metres, Z up), tuned to the default rig in
``rigging.py``:
- legs:  z 0.00 - 0.55
- body:  centre z ~0.90
- head:  centre z ~1.55, radius ~0.32
"""

from .character_manager import hex_to_rgba
from ._bpyutil import require_bpy
from .studio_log import get_logger

log = get_logger("hybrid_studio.modeling")

DEFAULT_PALETTE = {
    "body": "#3E7CB1",
    "head": "#F2C094",
    "limbs": "#3E7CB1",
    "eyes": "#1A1A1A",
    "accent": "#E4572E",
}


def _material(bpy, name, hex_color, roughness=0.65):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = hex_to_rgba(hex_color)
        bsdf.inputs["Roughness"].default_value = roughness
    return mat


def _finish_object(bpy, obj, name, material=None, bevel=0.0):
    obj.name = name
    if material is not None and obj.type == "MESH":
        obj.data.materials.append(material)
    if bevel > 0 and obj.type == "MESH":
        mod = obj.modifiers.new(name="SoftBevel", type="BEVEL")
        mod.width = bevel
        mod.segments = 2
    return obj


def _sphere(bpy, name, location, scale, material, bevel=0.02):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=location)
    obj = bpy.context.active_object
    obj.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _finish_object(bpy, obj, name, material, bevel)


def _box(bpy, name, location, scale, material, bevel=0.04):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.active_object
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return _finish_object(bpy, obj, name, material, bevel)


def build_simple_character(name="Hero", palette=None, location=(0.0, 0.0, 0.0)):
    """Build the demo cartoon character. Returns {part: object_name}.

    Parts: Body, Head, Eye_L, Eye_R, Arm_L, Arm_R, Leg_L, Leg_R, Hat.
    """
    bpy = require_bpy()
    if not isinstance(name, str) or not name.strip():
        raise ValueError("character name must be a non-empty string")
    palette = dict(DEFAULT_PALETTE, **(palette or {}))
    for key, val in palette.items():
        hex_to_rgba(val)  # validation with clear error
    lx, ly, lz = (float(location[0]), float(location[1]), float(location[2]))

    mats = {
        part: _material(bpy, "%s_%s" % (name, part), palette[part])
        for part in ("body", "head", "limbs", "eyes", "accent")
    }
    parts = {}
    parts["Body"] = _sphere(
        bpy, "%s_Body" % name, (lx, ly, lz + 0.90), (0.42, 0.34, 0.50), mats["body"]
    ).name
    parts["Head"] = _sphere(
        bpy, "%s_Head" % name, (lx, ly, lz + 1.55), (0.32, 0.30, 0.32), mats["head"]
    ).name
    parts["Eye_L"] = _sphere(
        bpy, "%s_Eye_L" % name, (lx + 0.12, ly + 0.24, lz + 1.62), (0.045, 0.03, 0.06),
        mats["eyes"], bevel=0.0,
    ).name
    parts["Eye_R"] = _sphere(
        bpy, "%s_Eye_R" % name, (lx - 0.12, ly + 0.24, lz + 1.62), (0.045, 0.03, 0.06),
        mats["eyes"], bevel=0.0,
    ).name
    parts["Arm_L"] = _sphere(
        bpy, "%s_Arm_L" % name, (lx + 0.52, ly, lz + 0.95), (0.11, 0.11, 0.34), mats["limbs"]
    ).name
    parts["Arm_R"] = _sphere(
        bpy, "%s_Arm_R" % name, (lx - 0.52, ly, lz + 0.95), (0.11, 0.11, 0.34), mats["limbs"]
    ).name
    parts["Leg_L"] = _sphere(
        bpy, "%s_Leg_L" % name, (lx + 0.18, ly, lz + 0.27), (0.13, 0.13, 0.28), mats["limbs"]
    ).name
    parts["Leg_R"] = _sphere(
        bpy, "%s_Leg_R" % name, (lx - 0.18, ly, lz + 0.27), (0.13, 0.13, 0.28), mats["limbs"]
    ).name
    parts["Hat"] = _sphere(
        bpy, "%s_Hat" % name, (lx, ly, lz + 1.82), (0.30, 0.30, 0.10), mats["accent"]
    ).name
    log.info("Built character '%s' with parts: %s", name, ", ".join(sorted(parts)))
    return parts


def build_simple_environment(prefix="ENV"):
    """Build a ground plane, three stylized trees and two rocks.

    Returns {part: object_name}.
    """
    bpy = require_bpy()
    ground_mat = _material(bpy, "%s_GroundMat" % prefix, "#5DA85F", roughness=0.9)
    trunk_mat = _material(bpy, "%s_TrunkMat" % prefix, "#7A5230", roughness=0.85)
    leaf_mat = _material(bpy, "%s_LeafMat" % prefix, "#2E7D4F", roughness=0.8)
    rock_mat = _material(bpy, "%s_RockMat" % prefix, "#8D99AE", roughness=0.95)

    parts = {}
    bpy.ops.mesh.primitive_plane_add(size=40.0, location=(0.0, 0.0, 0.0))
    parts["Ground"] = _finish_object(
        bpy, bpy.context.active_object, "%s_Ground" % prefix, ground_mat
    ).name

    tree_positions = [(3.2, -2.0), (-3.6, -1.2), (1.8, -4.2)]
    for idx, (tx, ty) in enumerate(tree_positions, start=1):
        bpy.ops.mesh.primitive_cylinder_add(
            radius=0.16, depth=1.4, location=(tx, ty, 0.7)
        )
        parts["Tree%d_Trunk" % idx] = _finish_object(
            bpy, bpy.context.active_object, "%s_Tree%d_Trunk" % (prefix, idx), trunk_mat, 0.02
        ).name
        bpy.ops.mesh.primitive_cone_add(
            radius1=0.85, radius2=0.0, depth=1.9, location=(tx, ty, 2.2)
        )
        parts["Tree%d_Top" % idx] = _finish_object(
            bpy, bpy.context.active_object, "%s_Tree%d_Top" % (prefix, idx), leaf_mat, 0.02
        ).name

    rock_positions = [(1.6, 1.8, 0.45), (-2.2, 2.4, 0.65)]
    for idx, (rx, ry, rs) in enumerate(rock_positions, start=1):
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=rs, location=(rx, ry, rs * 0.6))
        parts["Rock%d" % idx] = _finish_object(
            bpy, bpy.context.active_object, "%s_Rock%d" % (prefix, idx), rock_mat, 0.03
        ).name

    log.info("Built environment with parts: %s", ", ".join(sorted(parts)))
    return parts
