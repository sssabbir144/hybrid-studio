"""Studio configuration loading and validation.

Loads ``studio_config.json`` (project paths, fps, render presets,
GPU/CPU preference). Lookup order:
1. explicit path argument,
2. ``HYBRID_STUDIO_CONFIG`` environment variable,
3. ``studio_config.json`` next to the package (studio root),
4. ``studio_config.json`` in the current working directory,
5. built-in defaults (with a logged warning).
"""

import json
import os

from .studio_log import get_logger

log = get_logger("hybrid_studio.config")

SUPPORTED_ENGINES = ("BLENDER_EEVEE", "CYCLES", "BLENDER_WORKBENCH")

DEFAULT_CONFIG = {
    "project_name": "hybrid_studio_project",
    "fps": 24,
    "paths": {"projects_root": "projects"},
    "resolution_presets": {
        "preview": {"engine": "BLENDER_EEVEE", "width": 320, "height": 180, "samples": 16},
        "production": {"engine": "BLENDER_EEVEE", "width": 960, "height": 540, "samples": 32},
        "final": {"engine": "BLENDER_EEVEE", "width": 1920, "height": 1080, "samples": 64},
    },
    "render": {
        "prefer_gpu": True,
        "file_format": "PNG",
        "frame_padding": 4,
        "checkpoint_manifest": "render_manifest.json",
    },
}


class ConfigError(ValueError):
    """Raised when the studio configuration is invalid."""


def _studio_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_config_file(explicit=None):
    """Locate studio_config.json using the documented lookup order."""
    candidates = []
    if explicit:
        candidates.append(explicit)
    env = os.environ.get("HYBRID_STUDIO_CONFIG")
    if env:
        candidates.append(env)
    candidates.append(os.path.join(_studio_root(), "studio_config.json"))
    candidates.append(os.path.join(os.getcwd(), "studio_config.json"))
    for cand in candidates:
        if cand and os.path.isfile(cand):
            return cand
    return None


def validate_config(cfg):
    """Validate a config dict; raise ConfigError with a clear message."""
    if not isinstance(cfg, dict):
        raise ConfigError("config must be a JSON object (dict)")
    fps = cfg.get("fps")
    if not isinstance(fps, int) or fps <= 0:
        raise ConfigError("config 'fps' must be a positive integer, got %r" % (fps,))
    presets = cfg.get("resolution_presets")
    if not isinstance(presets, dict) or not presets:
        raise ConfigError("config 'resolution_presets' must be a non-empty object")
    for name in ("preview", "production", "final"):
        if name not in presets:
            raise ConfigError("config is missing required render preset %r" % name)
    for name, preset in presets.items():
        if not isinstance(preset, dict):
            raise ConfigError("preset %r must be an object" % name)
        for key in ("width", "height"):
            val = preset.get(key)
            if not isinstance(val, int) or val <= 0:
                raise ConfigError(
                    "preset %r: %r must be a positive integer, got %r" % (name, key, val)
                )
        engine = preset.get("engine", "BLENDER_EEVEE")
        if engine not in SUPPORTED_ENGINES:
            raise ConfigError(
                "preset %r: unsupported engine %r (supported: %s). NOTE: "
                "'BLENDER_EEVEE_NEXT' was removed in Blender 5.x; use "
                "'BLENDER_EEVEE'." % (name, engine, ", ".join(SUPPORTED_ENGINES))
            )
    render = cfg.get("render", {})
    if not isinstance(render, dict):
        raise ConfigError("config 'render' must be an object")
    padding = render.get("frame_padding", 4)
    if not isinstance(padding, int) or padding < 1 or padding > 8:
        raise ConfigError("render.frame_padding must be an int in 1..8, got %r" % (padding,))
    return cfg


def _deep_merge(base, override):
    out = dict(base)
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], val)
        else:
            out[key] = val
    return out


def load_config(path=None):
    """Load, merge over defaults, validate and return the config dict."""
    cfg_file = find_config_file(path)
    if cfg_file is None:
        log.warning("studio_config.json not found; using built-in defaults")
        return validate_config(json.loads(json.dumps(DEFAULT_CONFIG)))
    with open(cfg_file, "r", encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ConfigError("invalid JSON in %s: %s" % (cfg_file, exc))
    merged = _deep_merge(json.loads(json.dumps(DEFAULT_CONFIG)), raw)
    validate_config(merged)
    log.info("Loaded studio config from %s", cfg_file)
    return merged


def get_preset(cfg, name):
    """Return a named render preset or raise ConfigError."""
    presets = cfg.get("resolution_presets", {})
    if name not in presets:
        raise ConfigError(
            "unknown render preset %r (available: %s)" % (name, ", ".join(sorted(presets)))
        )
    return presets[name]


def get_fps(cfg):
    return int(cfg.get("fps", 24))
