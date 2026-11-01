"""Automatic quality control.

Pure checks (run anywhere): project structure, manifest presence, story
file validity, render completeness vs the checkpoint manifest, character
registry validity. Blender-only check: verify a .blend file opens and list
its objects (via bpy.data.libraries.load — the current scene is untouched).

Writes a QC report as JSON + Markdown.
"""

import json
import os

from ._bpyutil import require_bpy, has_bpy
from . import project_manager, render_manager
from .studio_log import get_logger

log = get_logger("hybrid_studio.quality_control")


def _check(name, status, detail):
    return {"name": name, "status": status, "detail": detail}


def check_project_structure(project_dir):
    checks = []
    manifest_file = os.path.join(project_dir, project_manager.MANIFEST_NAME)
    checks.append(_check(
        "manifest_exists", "PASS" if os.path.isfile(manifest_file) else "FAIL",
        manifest_file,
    ))
    for sub in project_manager.PROJECT_DIRS:
        path = os.path.join(project_dir, sub)
        checks.append(_check(
            "dir:%s" % sub, "PASS" if os.path.isdir(path) else "FAIL", path,
        ))
    return checks


def check_render_completeness(render_dir):
    """Compare frames on disk vs the checkpoint manifest (pure)."""
    try:
        manifest = render_manager.load_checkpoint_manifest(render_dir)
    except FileNotFoundError:
        return [_check("render_manifest", "FAIL", "no render_manifest.json in %s" % render_dir)]
    missing = render_manager.find_missing_frames(
        render_dir, manifest["frame_start"], manifest["frame_end"],
        manifest.get("padding", 4),
    )
    status = "PASS" if not missing else "FAIL"
    detail = "all %d frames valid" % manifest["expected_count"] if not missing \
        else "missing/invalid frames: %s" % missing
    return [_check("render_completeness", status, detail)]


def check_story_file(path):
    from .story_manager import load_story
    try:
        story = load_story(path)
        return [_check("story_valid", "PASS",
                       "'%s': %d scenes, %d frames"
                       % (story.title, len(story.scenes), story.duration_frames))]
    except Exception as exc:
        return [_check("story_valid", "FAIL", str(exc))]


def check_character_file(path):
    from .character_manager import load_registry
    try:
        reg = load_registry(path)
        return [_check("characters_valid", "PASS",
                       "%d characters: %s" % (len(reg), ", ".join(reg.names())))]
    except Exception as exc:
        return [_check("characters_valid", "FAIL", str(exc))]


def check_blend_opens(blend_path):
    """Verify a .blend loads and list its objects (Blender only)."""
    if not has_bpy():
        return [_check("blend_opens", "SKIP",
                       "bpy unavailable; run inside Blender to verify .blend files")]
    bpy = require_bpy()
    if not os.path.isfile(blend_path):
        return [_check("blend_opens", "FAIL", "file not found: %s" % blend_path)]
    try:
        with bpy.data.libraries.load(blend_path) as (data_from, _data_to):
            objects = list(data_from.objects)
            scenes = list(data_from.scenes)
        return [_check("blend_opens", "PASS",
                       "%d objects, %d scenes in %s"
                       % (len(objects), len(scenes), os.path.basename(blend_path)))]
    except Exception as exc:
        return [_check("blend_opens", "FAIL", "could not open %s: %s" % (blend_path, exc))]


def run_qc(project_dir, render_dir=None, story_path=None, character_path=None,
           blend_path=None):
    """Run all applicable QC checks; returns the report dict."""
    checks = []
    checks += check_project_structure(project_dir)
    if render_dir:
        checks += check_render_completeness(render_dir)
    if story_path:
        checks += check_story_file(story_path)
    if character_path:
        checks += check_character_file(character_path)
    if blend_path:
        checks += check_blend_opens(blend_path)
    failed = [c for c in checks if c["status"] == "FAIL"]
    report = {
        "project_dir": os.path.abspath(project_dir),
        "checks": checks,
        "passed": sum(1 for c in checks if c["status"] == "PASS"),
        "failed": len(failed),
        "skipped": sum(1 for c in checks if c["status"] == "SKIP"),
        "overall": "PASS" if not failed else "FAIL",
    }
    log.info("QC overall=%s (%d passed, %d failed, %d skipped)",
             report["overall"], report["passed"], report["failed"], report["skipped"])
    return report


def write_qc_report(report, out_dir, stem="qc_report"):
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, stem + ".json")
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
    md_path = os.path.join(out_dir, stem + ".md")
    lines = [
        "# Quality Control Report",
        "",
        "- Project: `%s`" % report.get("project_dir", ""),
        "- Overall: **%s** (%d passed, %d failed, %d skipped)"
        % (report["overall"], report["passed"], report["failed"], report["skipped"]),
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    for check in report["checks"]:
        lines.append("| %s | %s | %s |" % (check["name"], check["status"], check["detail"]))
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    log.info("QC report written: %s, %s", json_path, md_path)
    return {"json": json_path, "markdown": md_path}
