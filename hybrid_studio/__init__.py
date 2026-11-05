"""Hybrid 2D + 3D Cinematic Animation Studio package.

A modular production architecture for Kaggle + Blender 5.2.3 LTS.

Design rules:
- Every module has clear inputs/outputs, validates its inputs, logs through
  the shared logger, and is safe to rerun.
- Modules that need Blender import ``bpy`` lazily so the pure-Python parts
  (config, project/story/character data, render-manifest logic, ffmpeg
  command building, QC file checks) work outside Blender.
"""

__version__ = "2.0.0"
__all__ = [
    "config",
    "controller",
    "project_manager",
    "story_manager",
    "character_manager",
    "modeling",
    "rigging",
    "grease_pencil",
    "animation",
    "cinematography",
    "lighting_materials",
    "render_manager",
    "compositing",
    "audio_video",
    "quality_control",
]


def check_environment():
    """Runtime Version Guard.

    Raises RuntimeError immediately when the package is imported inside a
    Blender build other than the tested 5.2.3 (major.minor must match;
    see ``_bpyutil.check_blender_version``). Outside Blender this is a
    no-op, so pure-Python tooling and tests can import the package freely.
    """
    from . import _bpyutil
    if _bpyutil.has_bpy():
        _bpyutil.check_blender_version()


# Fail at startup, not mid-render: importing this package inside an
# untested Blender build stops here with a clear error.
check_environment()
