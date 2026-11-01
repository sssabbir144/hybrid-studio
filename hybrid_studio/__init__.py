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
