"""Camera and cinematography (Blender / bpy).

Camera creation with focal length, look-at via a Track To constraint on a
target empty, and a simple two-pose tracking move (location keyframes while
the constraint keeps the subject framed).
"""

from ._bpyutil import require_bpy
from . import animation as anim
from .studio_log import get_logger

log = get_logger("hybrid_studio.cinematography")


def create_camera(name="Camera", location=(4.5, -6.0, 2.2), focal_length=38.0):
    """Create a camera object and make it the scene camera."""
    bpy = require_bpy()
    if not (5.0 <= float(focal_length) <= 300.0):
        raise ValueError("focal_length must be in 5..300 mm, got %r" % (focal_length,))
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = float(focal_length)
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.collection.objects.link(cam)
    cam.location = location
    bpy.context.scene.camera = cam
    log.info("Camera '%s' created at %s, lens %.0fmm", name, tuple(location), focal_length)
    return cam


def look_at(camera, target_location, target_name="CameraTarget"):
    """Aim ``camera`` at a point using a Track To constraint + target empty."""
    bpy = require_bpy()
    target = bpy.data.objects.get(target_name)
    if target is None:
        target = bpy.data.objects.new(target_name, None)
        bpy.context.collection.objects.link(target)
    target.location = target_location
    for con in list(camera.constraints):
        if con.type == "TRACK_TO":
            camera.constraints.remove(con)
    con = camera.constraints.new(type="TRACK_TO")
    con.target = target
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    log.info("Camera '%s' now tracks %s", camera.name, target_name)
    return target


def animate_tracking_move(camera, location_a, location_b, frame_start=1, frame_end=24):
    """Keyframe the camera between two locations (smooth tracking move)."""
    if frame_end <= frame_start:
        raise ValueError("frame_end must be after frame_start")
    anim.keyframe_transform(camera, frame_start, location=tuple(location_a))
    anim.keyframe_transform(camera, frame_end, location=tuple(location_b))
    if camera.animation_data and camera.animation_data.action:
        anim.apply_easing(camera.animation_data.action)
    log.info(
        "Camera tracking move %s -> %s over frames %d-%d",
        tuple(location_a), tuple(location_b), frame_start, frame_end,
    )
    return camera
