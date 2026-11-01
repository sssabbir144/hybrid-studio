"""Character design and asset management.

A registry of original characters: name, proportions, colour palette and
asset paths. JSON save/load with validation. Pure Python (no Blender).
"""

import json
import os
import re

from .studio_log import get_logger

log = get_logger("hybrid_studio.character_manager")

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
DEFAULT_PROPORTIONS = {
    "height": 1.8,
    "head_ratio": 0.28,
    "shoulder_width": 0.55,
    "hip_width": 0.36,
}


def hex_to_rgba(value, alpha=1.0):
    """Convert '#RRGGBB' to an (r, g, b, a) tuple of floats in 0..1."""
    if not isinstance(value, str) or not _HEX_RE.match(value):
        raise ValueError("colour must be a '#RRGGBB' hex string, got %r" % (value,))
    r = int(value[1:3], 16) / 255.0
    g = int(value[3:5], 16) / 255.0
    b = int(value[5:7], 16) / 255.0
    return (r, g, b, float(alpha))


def _validate_proportions(props):
    if props is None:
        return dict(DEFAULT_PROPORTIONS)
    if not isinstance(props, dict) or not props:
        raise ValueError("proportions must be a non-empty object of positive numbers")
    out = {}
    for key, val in props.items():
        if not isinstance(val, (int, float)) or isinstance(val, bool) or val <= 0:
            raise ValueError("proportion %r must be a positive number, got %r" % (key, val))
        out[str(key)] = float(val)
    return out


def _validate_palette(palette):
    if palette is None:
        return {}
    if not isinstance(palette, dict):
        raise ValueError("palette must be an object mapping part name -> '#RRGGBB'")
    out = {}
    for key, val in palette.items():
        hex_to_rgba(val)  # raises with a clear message when invalid
        out[str(key)] = val.upper()
    return out


class Character:
    def __init__(self, name, proportions=None, palette=None, asset_paths=None, notes=""):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("character name must be a non-empty string")
        self.name = name.strip()
        self.proportions = _validate_proportions(proportions)
        self.palette = _validate_palette(palette)
        if asset_paths is None:
            asset_paths = {}
        if not isinstance(asset_paths, dict):
            raise ValueError("asset_paths must be an object mapping kind -> path")
        self.asset_paths = {str(k): str(v) for k, v in asset_paths.items()}
        self.notes = notes or ""

    def to_dict(self):
        return {
            "name": self.name,
            "proportions": self.proportions,
            "palette": self.palette,
            "asset_paths": self.asset_paths,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("character entry must be an object")
        return cls(
            data.get("name"), data.get("proportions"), data.get("palette"),
            data.get("asset_paths"), data.get("notes", ""),
        )


class CharacterRegistry:
    def __init__(self):
        self._characters = {}

    def add(self, character):
        if not isinstance(character, Character):
            raise ValueError("add expects a Character instance")
        if character.name in self._characters:
            raise ValueError("duplicate character name %r" % character.name)
        self._characters[character.name] = character
        log.info("Registered character '%s'", character.name)
        return character

    def get(self, name):
        if name not in self._characters:
            raise KeyError(
                "character %r not registered (have: %s)"
                % (name, ", ".join(sorted(self._characters)) or "none")
            )
        return self._characters[name]

    def names(self):
        return sorted(self._characters)

    def __len__(self):
        return len(self._characters)

    def to_dict(self):
        return {"characters": [self._characters[n].to_dict() for n in self.names()]}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("registry data must be an object")
        reg = cls()
        for raw in data.get("characters", []):
            reg.add(Character.from_dict(raw))
        return reg


def save_registry(registry, path):
    if not isinstance(registry, CharacterRegistry):
        raise ValueError("save_registry expects a CharacterRegistry")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(registry.to_dict(), fh, indent=2, sort_keys=True)
    log.info("Saved character registry (%d characters) to %s", len(registry), path)
    return path


def load_registry(path):
    if not os.path.isfile(path):
        raise FileNotFoundError("character registry not found: %s" % path)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    reg = CharacterRegistry.from_dict(data)
    log.info("Loaded character registry (%d characters)", len(reg))
    return reg
