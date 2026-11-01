"""Character rigging (Blender / bpy).

Creates a simple armature (root / spine / head / arm.L / arm.R / leg.L /
leg.R), binds character meshes to bones through vertex groups + an
Armature modifier (deterministic, headless-safe), and adds reusable
Idle/Wave action placeholders.
"""

from ._bpyutil import require_bpy
from . import animation as anim
from .studio_log import get_logger

log = get_logger("hybrid_studio.rigging")

# Bone layout matching modeling.build_simple_character proportions.
BONES = {
    # name: (head, tail, parent)
    "root":  ((0.0, 0.0, 0.02), (0.0, 0.0, 0.35), None),
    "spine": ((0.0, 0.0, 0.35), (0.0, 0.0, 1.15), "root"),
    "head":  ((0.0, 0.0, 1.15), (0.0, 0.0, 1.75), "spine"),
    "arm.L": ((0.12, 0.0, 1.12), (0.58, 0.0, 0.72), "spine"),
    "arm.R": ((-0.12, 0.0, 1.12), (-0.58, 0.0, 0.72), "spine"),
    "leg.L": ((0.16, 0.0, 0.35), (0.18, 0.0, 0.02), "root"),
    "leg.R": ((-0.16, 0.0, 0.35), (-0.18, 0.0, 0.02), "root"),
}

# Which bone each modeling part binds to (part suffix -> bone).
PART_BONE_MAP = {
    "Body": "spine",
    "Head": "head",
    "Eye_L": "head",
    "Eye_R": "head",
    "Hat": "head",
    "Arm_L": "arm.L",
    "Arm_R": "arm.R",
    "Leg_L": "leg.L",
    "Leg_R": "leg.R",
}


def create_simple_armature(name="HeroRig", location=(0.0, 0.0, 0.0)):
    """Create the armature object. Returns the armature object."""
    bpy = require_bpy()
    if not isinstance(name, str) or not name.strip():
        raise ValueError("armature name must be a non-empty string")
    lx, ly, lz = (float(location[0]), float(location[1]), float(location[2]))
    arm_data = bpy.data.armatures.new(name)
    arm_obj = bpy.data.objects.new(name, arm_data)
    bpy.context.collection.objects.link(arm_obj)
    bpy.context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    try:
        edit_bones = arm_data.edit_bones
        created = {}
        for bone_name in ("root", "spine", "head", "arm.L", "arm.R", "leg.L", "leg.R"):
            head, tail, parent = BONES[bone_name]
            bone = edit_bones.new(bone_name)
            bone.head = (head[0] + lx, head[1] + ly, head[2] + lz)
            bone.tail = (tail[0] + lx, tail[1] + ly, tail[2] + lz)
            if parent is not None:
                bone.parent = created[parent]
            created[bone_name] = bone
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
    arm_obj.location = (0.0, 0.0, 0.0)
    log.info("Created armature '%s' with bones: %s", name, ", ".join(BONES))
    return arm_obj


def attach_meshes(armature_obj, mesh_bone_map):
    """Bind meshes to bones via vertex groups + Armature modifier.

    ``mesh_bone_map``: {object_name: bone_name}. Every vertex of a mesh is
    assigned weight 1.0 to its bone's vertex group (simple, robust binding
    for primitive-built characters). Returns the list of bound object names.
    """
    bpy = require_bpy()
    bone_names = {b.name for b in armature_obj.data.bones}
    bound = []
    for obj_name, bone_name in mesh_bone_map.items():
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            raise ValueError("attach_meshes: object %r not found" % obj_name)
        if obj.type != "MESH":
            raise ValueError("attach_meshes: object %r is not a mesh" % obj_name)
        if bone_name not in bone_names:
            raise ValueError(
                "attach_meshes: bone %r not in armature %r" % (bone_name, armature_obj.name)
            )
        group = obj.vertex_groups.get(bone_name) or obj.vertex_groups.new(name=bone_name)
        indices = list(range(len(obj.data.vertices)))
        if indices:
            group.add(indices, 1.0, "REPLACE")
        existing = [m for m in obj.modifiers if m.type == "ARMATURE"]
        for mod in existing:
            obj.modifiers.remove(mod)
        mod = obj.modifiers.new(name="Armature", type="ARMATURE")
        mod.object = armature_obj
        obj.parent = armature_obj
        bound.append(obj_name)
    log.info("Bound %d meshes to armature '%s'", len(bound), armature_obj.name)
    return bound


def attach_character(armature_obj, character_name="Hero"):
    """Bind all parts built by modeling.build_simple_character."""
    mapping = {
        "%s_%s" % (character_name, part): bone for part, bone in PART_BONE_MAP.items()
    }
    return attach_meshes(armature_obj, mapping)


def create_placeholder_actions(armature_obj, frames=24):
    """Create reusable 'Idle' and 'Wave' actions on the armature.

    Idle: gentle spine sway. Wave: arm.R raise + sway (delegated to
    animation.animate_wave under a separate action name).
    Returns {action_name: action}.
    """
    bpy = require_bpy()
    actions = {}
    idle = anim.get_or_create_action(bpy, armature_obj, "%s_Idle" % armature_obj.name)
    anim.keyframe_pose_bone(armature_obj, "spine", 1, rotation_euler=(0.0, 0.0, 0.0))
    anim.keyframe_pose_bone(armature_obj, "spine", frames // 2, rotation_euler=(0.03, 0.0, 0.02))
    anim.keyframe_pose_bone(armature_obj, "spine", frames, rotation_euler=(0.0, 0.0, 0.0))
    anim.apply_easing(idle)
    actions["Idle"] = idle
    wave = anim.animate_wave(
        armature_obj, action_name="%s_Wave" % armature_obj.name,
        bone_name="arm.R", frames=frames,
    )
    actions["Wave"] = wave
    # Leave the armature showing the Idle action by default.
    armature_obj.animation_data.action = idle
    log.info("Placeholder actions ready on %s: Idle, Wave", armature_obj.name)
    return actions
