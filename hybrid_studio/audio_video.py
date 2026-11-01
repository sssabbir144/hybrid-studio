"""Audio and video editing helpers.

Two layers:
- Pure Python: a VSE strip-layout *plan* (video strips + audio track
  slots) and an ffmpeg command builder (returns the command string; ffmpeg
  does not need to be installed).
- Blender (optional): apply the plan to the Video Sequencer with image
  strips and placeholder audio slots.
"""

import os
import shlex

from ._bpyutil import require_bpy
from .studio_log import get_logger

log = get_logger("hybrid_studio.audio_video")

AUDIO_SLOTS = ("music", "dialogue", "sfx")


def build_sequence_plan(frame_start=1, frame_end=24, fps=24, frames_dir="renders",
                        prefix="frame_", audio_files=None):
    """Build a VSE strip-layout plan (pure data, JSON-serialisable).

    ``audio_files``: optional {slot: path} using slots in AUDIO_SLOTS.
    """
    if not isinstance(frame_start, int) or not isinstance(frame_end, int) \
            or frame_end < frame_start or frame_start < 1:
        raise ValueError("invalid frame range %r..%r" % (frame_start, frame_end))
    if not isinstance(fps, int) or fps <= 0:
        raise ValueError("fps must be a positive integer")
    plan = {
        "fps": fps,
        "frame_start": frame_start,
        "frame_end": frame_end,
        "duration_frames": frame_end - frame_start + 1,
        "duration_seconds": round((frame_end - frame_start + 1) / float(fps), 3),
        "video_strips": [{
            "name": "MainRender",
            "type": "IMAGE_SEQUENCE",
            "channel": 2,
            "frame_start": frame_start,
            "frame_end": frame_end,
            "directory": frames_dir,
            "file_pattern": "%s%%04d.png" % prefix,
        }],
        "audio_strips": [],
    }
    audio_files = audio_files or {}
    channel = 3
    for slot in AUDIO_SLOTS:
        path = audio_files.get(slot)
        plan["audio_strips"].append({
            "name": "Audio_%s" % slot.capitalize(),
            "type": "SOUND" if path else "EMPTY_SLOT",
            "slot": slot,
            "channel": channel,
            "frame_start": frame_start,
            "filepath": path,
        })
        channel += 1
    return plan


def build_ffmpeg_command(input_pattern, output_path, fps=24, audio_path=None,
                         crf=18, preset="medium", audio_bitrate="160k"):
    """Build (but do not run) an ffmpeg command assembling frames -> mp4.

    ``input_pattern``: printf-style pattern, e.g. 'renders/frame_%04d.png'.
    Returns the full command as a single shell-safe string.
    """
    if not input_pattern or "%" not in input_pattern:
        raise ValueError(
            "input_pattern must contain a printf frame pattern like %%04d, got %r"
            % (input_pattern,)
        )
    if not output_path:
        raise ValueError("output_path must be non-empty")
    if not isinstance(fps, int) or fps <= 0:
        raise ValueError("fps must be a positive integer")
    parts = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", input_pattern,
    ]
    if audio_path:
        parts += ["-i", audio_path, "-shortest"]
    parts += [
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-crf", str(int(crf)), "-preset", preset,
        "-r", str(fps),
    ]
    if audio_path:
        parts += ["-c:a", "aac", "-b:a", audio_bitrate]
    parts.append(output_path)
    command = " ".join(shlex.quote(p) if any(c in p for c in " %") else p for p in parts)
    log.info("Built ffmpeg command: %s", command)
    return command


def apply_vse_plan(scene, plan):
    """Apply a sequence plan inside Blender's Video Sequencer (best effort).

    Adds the image-sequence strip; audio slots with real files are added as
    sound strips, empty slots are logged and skipped. Returns strip names.
    """
    bpy = require_bpy()
    if scene.sequence_editor is None:
        scene.sequence_editor_create()
    seq = scene.sequence_editor
    container = getattr(seq, "strips", None) or getattr(seq, "sequences", None)
    if container is None:
        raise RuntimeError("this Blender build exposes no VSE strip container")
    created = []
    for strip in plan["video_strips"]:
        directory = strip["directory"]
        first_file = strip["file_pattern"] % strip["frame_start"]
        filepath = os.path.join(directory, first_file)
        try:
            new = container.new_image(strip["name"], filepath, strip["channel"],
                                      strip["frame_start"])
            created.append(new.name)
        except Exception as exc:
            log.warning("VSE image strip %r not created (%s)", strip["name"], exc)
    for strip in plan["audio_strips"]:
        if strip["type"] != "SOUND" or not strip.get("filepath"):
            log.info("Audio slot %r left empty (no file provided)", strip["slot"])
            continue
        try:
            new = container.new_sound(strip["name"], strip["filepath"],
                                      strip["channel"], strip["frame_start"])
            created.append(new.name)
        except Exception as exc:
            log.warning("VSE sound strip %r not created (%s)", strip["name"], exc)
    log.info("VSE plan applied; strips created: %s", ", ".join(created) or "none")
    return created
