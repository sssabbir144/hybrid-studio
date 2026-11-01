"""Project management: directory structure, manifest, delivery packaging.

Pure Python (no Blender required). All functions validate inputs, log their
actions and are safe to rerun (creating an existing project returns its
existing manifest after ensuring the structure is complete).
"""

import json
import os
import re
from datetime import datetime, timezone

from .studio_log import get_logger

log = get_logger("hybrid_studio.project_manager")

PROJECT_DIRS = [
    "characters",
    "environments",
    "animation",
    "grease_pencil",
    "shots",
    "renders",
    "compositing",
    "audio",
    "blend_projects",
    "scripts",
    "reports",
]

MANIFEST_NAME = "project.json"
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\- ]*$")


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def validate_project_name(name):
    if not isinstance(name, str) or not name.strip():
        raise ValueError("project name must be a non-empty string")
    if "/" in name or "\\" in name or name.strip() in (".", ".."):
        raise ValueError("project name must not contain path separators: %r" % name)
    if not _NAME_RE.match(name.strip()):
        raise ValueError(
            "project name may only contain letters, digits, spaces, '_' and '-': %r" % name
        )
    return name.strip()


def project_path(root, name):
    """Absolute path of a project under a projects root."""
    if not root:
        raise ValueError("projects root must be a non-empty path")
    return os.path.join(os.path.abspath(root), validate_project_name(name))


def create_project(root, name, config=None, fps=None):
    """Create (or reopen) a project directory structure + manifest.

    Returns the manifest dict (includes absolute ``path``).
    Idempotent: rerunning keeps the original manifest and fills in any
    missing directories.
    """
    name = validate_project_name(name)
    pdir = project_path(root, name)
    for sub in PROJECT_DIRS:
        os.makedirs(os.path.join(pdir, sub), exist_ok=True)
    manifest_file = os.path.join(pdir, MANIFEST_NAME)
    if os.path.isfile(manifest_file):
        with open(manifest_file, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        log.info("Reopened existing project '%s' at %s", name, pdir)
    else:
        manifest = {
            "name": name,
            "created_utc": _utc_now(),
            "fps": fps if fps is not None else (config or {}).get("fps", 24),
            "directories": list(PROJECT_DIRS),
            "status": "created",
            "assets": {"characters": [], "shots": [], "renders": []},
        }
        with open(manifest_file, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, sort_keys=True)
        log.info("Created project '%s' at %s", name, pdir)
    manifest["path"] = pdir
    manifest["manifest_file"] = manifest_file
    return manifest


def load_manifest(project_dir):
    """Load a project manifest from a project directory."""
    manifest_file = os.path.join(project_dir, MANIFEST_NAME)
    if not os.path.isfile(manifest_file):
        raise FileNotFoundError("project manifest not found: %s" % manifest_file)
    with open(manifest_file, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    manifest["path"] = os.path.abspath(project_dir)
    manifest["manifest_file"] = manifest_file
    return manifest


def save_manifest(manifest):
    """Persist a manifest dict back to its project directory."""
    manifest_file = manifest.get("manifest_file") or os.path.join(
        manifest["path"], MANIFEST_NAME
    )
    data = {k: v for k, v in manifest.items() if k not in ("path", "manifest_file")}
    with open(manifest_file, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
    log.info("Saved manifest: %s", manifest_file)
    return manifest_file


def register_asset(manifest, kind, entry):
    """Record an asset entry (character/shot/render) in the manifest."""
    if kind not in ("characters", "shots", "renders"):
        raise ValueError("asset kind must be characters/shots/renders, got %r" % kind)
    manifest.setdefault("assets", {}).setdefault(kind, [])
    if entry not in manifest["assets"][kind]:
        manifest["assets"][kind].append(entry)
    return manifest


def delivery_package_list(manifest):
    """Return the expected delivery contents for a finished project."""
    pdir = manifest.get("path", "")
    rel = [
        "blend_projects",
        "characters",
        "environments",
        "grease_pencil",
        "renders",
        "compositing",
        "audio",
        "scripts",
        "reports",
        MANIFEST_NAME,
    ]
    return [
        {"item": item, "path": os.path.join(pdir, item), "exists": os.path.exists(os.path.join(pdir, item))}
        for item in rel
    ]
