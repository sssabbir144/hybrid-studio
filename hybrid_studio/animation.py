"""3D animation helpers (Blender / bpy).

Keyframe helpers with easing, named actions, and two ready-made animation
builders (bounce for an object/armature, wave for an arm pose bone).
Uses ``keyframe_insert`` so Blender 5.x layered actions and slots are
created correctly by Blender itself.
"""

import math

from ._bpyutil import require_bpy
from .studio_log import get_logger

log = get_logger("hybrid_studio.animation")


def _iter_fcurves(action):
    """Yield fcurves from both legacy and layered (4.4+/5.x) actions."""
    legacy = getattr(action, "fcurves", None)
    if legacy:
        for fc in legacy:
            yield fc
        return
    for layer in getattr(action, "layers", []):
        for strip in getattr(layer, "strips", []):
            channelbag = getattr(strip, "channelbag", None)
            if channelbag is not None:
                for fc in channelbag.fcurves:
                    yield fc


def get_or_create_action(bpy, owner, name):
    """Ensure ``owner`` has animation data with an action called ``name``."""
    if owner.animation_data is None:
        owner.animation_data_create()
    action = bpy.data.actions.get(name)
    if action is None:
        action = bpy.data.actions.new(name)
    owner.animation_data.action = action
    return action


def apply_easing(action, interpolation="BEZIER"):
    """Set interpolation on every keyframe point of an action."""
    count = 0
    for fcurve in _iter_fcurves(action):
        for point in fcurve.keyframe_points:
            point.interpolation = interpolation
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"
            count += 1
    log.info("Applied %s easing to %d keyframe points", interpolation, count)
    return count


def keyframe_transform(obj, frame, location=None, rotation_euler=None, scale=None):
    """Insert location/rotation/scale keyframes on an object at ``frame``."""
    if not isinstance(frame, int) or frame < 0:
        raise ValueError("frame must be a non-negative integer, got %r" % (frame,))
    if location is not None:
        obj.location = location
        obj.keyframe_insert("location", frame=frame)
    if rotation_euler is not None:
        obj.rotation_euler = rotation_euler
        obj.keyframe_insert("rotation_euler", frame=frame)
    if scale is not None:
        obj.scale = scale
        obj.keyframe_insert("scale", frame=frame)


def keyframe_pose_bone(armature_obj, bone_name, frame, rotation_euler=None, location=None):
    """Insert keyframes on a pose bone (switches it to XYZ euler mode)."""
    pbone = armature_obj.pose.bones.get(bone_name)
    if pbone is None:
        raise ValueError(
            "pose bone %r not found on %r (have: %s)"
            % (bone_name, armature_obj.name, ", ".join(b.name for b in armature_obj.pose.bones))
        )
    if rotation_euler is not None:
        pbone.rotation_mode = "XYZ"
        pbone.rotation_euler = rotation_euler
        pbone.keyframe_insert("rotation_euler", frame=frame)
    if location is not None:
        pbone.location = location
        pbone.keyframe_insert("location", frame=frame)
    return pbone


def animate_bounce(obj, action_name="Bounce", frames=24, height=0.35, start_z=0.0):
    """A squash-free vertical bounce: up at 1/4, down at 1/2, up, rest.

    Returns the created action.
    """
    bpy = require_bpy()
    if frames < 4:
        raise ValueError("bounce animation needs at least 4 frames")
    if height <= 0:
        raise ValueError("bounce height must be positive")
    action = get_or_create_action(bpy, obj, action_name)
    keys = [
        (1, start_z),
        (max(2, frames // 4), start_z + height),
        (max(3, frames // 2), start_z),
        (max(4, (3 * frames) // 4), start_z + height * 0.6),
        (frames, start_z),
    ]
    base = tuple(obj.location)
    for frame, z in keys:
        keyframe_transform(obj, frame, location=(base[0], base[1], z))
    apply_easing(action)
    log.info("Bounce animation '%s' on %s over %d frames", action_name, obj.name, frames)
    return action


def animate_wave(armature_obj, action_name="Wave", bone_name="arm.R",
                 frames=24, lift=math.radians(115.0), sway=math.radians(25.0)):
    """Raise an arm bone and sway it side to side (a friendly wave)."""
    bpy = require_bpy()
    if frames < 6:
        raise ValueError("wave animation needs at least 6 frames")
    action = get_or_create_action(bpy, armature_obj, action_name)
    mid = frames // 2
    keyframe_pose_bone(armature_obj, bone_name, 1, rotation_euler=(0.0, 0.0, 0.0))
    keyframe_pose_bone(armature_obj, bone_name, max(2, frames // 6),
                       rotation_euler=(0.0, 0.0, -lift))
    keyframe_pose_bone(armature_obj, bone_name, mid,
                       rotation_euler=(sway, 0.0, -lift))
    keyframe_pose_bone(armature_obj, bone_name, max(mid + 1, (3 * frames) // 4),
                       rotation_euler=(-sway, 0.0, -lift))
    keyframe_pose_bone(armature_obj, bone_name, frames,
                       rotation_euler=(0.0, 0.0, -lift * 0.85))
    apply_easing(action)
    log.info("Wave animation '%s' on bone %s of %s", action_name, bone_name, armature_obj.name)
    return action


def set_frame_range(scene, start, end):
    if not isinstance(start, int) or not isinstance(end, int) or end < start or start < 0:
        raise ValueError("invalid frame range %r..%r" % (start, end))
    scene.frame_start = start
    scene.frame_end = end
    return (start, end)
