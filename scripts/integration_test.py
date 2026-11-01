"""Phase 2 integration test — run INSIDE Blender headless on Kaggle.

Usage on Kaggle:
    blender -b --python scripts/integration_test.py

It drives StudioController.build_demo_scene() (character + environment +
rig + Grease Pencil sparkle + bounce/wave animation + camera move +
three-point lighting + preview render with checkpoint manifest + .blend
save), then REOPENS the saved .blend and verifies the required objects
survived. A JSON report is written to <project>/reports/integration_report.json
and PASS/FAIL is printed per step. Exit code 0 only if everything passed.
"""

import json
import os
import sys
import traceback

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if STUDIO_ROOT not in sys.path:
    sys.path.insert(0, STUDIO_ROOT)

PROJECTS_ROOT = os.environ.get(
    "HYBRID_STUDIO_PROJECTS", os.path.join(STUDIO_ROOT, "projects"))
PROJECT_NAME = os.environ.get("HYBRID_STUDIO_PROJECT_NAME", "phase2_demo")


def marker(text):
    print("\n" + "#" * 70)
    print("## %s" % text)
    print("#" * 70, flush=True)


def verify_reopened_scene(blend_path):
    """Reopen the .blend and verify required objects exist. Returns dict."""
    import bpy
    bpy.ops.wm.open_mainfile(filepath=blend_path)
    names = [obj.name for obj in bpy.data.objects]
    by_type = {}
    for obj in bpy.data.objects:
        by_type.setdefault(obj.type, []).append(obj.name)

    def has(prefix=None, exact=None, obj_type=None):
        pool = by_type.get(obj_type, names) if obj_type else names
        if exact:
            return exact in pool
        return any(n.startswith(prefix) for n in pool)

    checks = {
        "character_parts": all(
            has(exact="Hero_%s" % part) for part in
            ("Body", "Head", "Arm_L", "Arm_R", "Leg_L", "Leg_R", "Eye_L", "Eye_R")),
        "armature": has(exact="HeroRig", obj_type="ARMATURE"),
        "grease_pencil_object": len(by_type.get("GREASEPENCIL", [])) > 0,
        "camera": len(by_type.get("CAMERA", [])) > 0,
        "lights": len(by_type.get("LIGHT", [])) >= 3,
        "environment": has(prefix="ENV_Ground"),
    }
    return {"objects": sorted(names), "checks": checks,
            "all_present": all(checks.values())}


def main():
    report = {"steps": {}, "overall": "FAIL"}

    def record(name, fn):
        marker("STEP: %s" % name)
        try:
            detail = fn()
            report["steps"][name] = {"status": "PASS", "detail": str(detail)}
            print("PASS: %s -> %s" % (name, detail), flush=True)
            return detail
        except Exception as exc:
            report["steps"][name] = {
                "status": "FAIL",
                "detail": "%s: %s" % (type(exc).__name__, exc),
                "traceback": traceback.format_exc(),
            }
            print("FAIL: %s -> %s: %s" % (name, type(exc).__name__, exc), flush=True)
            return None

    from hybrid_studio.controller import StudioController

    controller = StudioController()
    record("create_project",
           lambda: controller.create_project(PROJECTS_ROOT, PROJECT_NAME)["path"])
    record("register_character", controller.register_demo_character)
    record("create_story", lambda: controller.create_demo_story()["story"])

    build_report = record("build_demo_scene", controller.build_demo_scene)
    if build_report is not None:
        for step_name, step_result in build_report.get("steps", {}).items():
            report["steps"]["build:%s" % step_name] = step_result
        blend_path = build_report.get("blend_path")
    else:
        blend_path = None

    if blend_path and os.path.isfile(blend_path):
        reopen = record("reopen_and_verify", lambda: verify_reopened_scene(blend_path))
        if reopen is not None and not reopen["all_present"]:
            report["steps"]["reopen_and_verify"] = {
                "status": "FAIL",
                "detail": "missing objects; checks=%s objects=%s"
                          % (reopen["checks"], reopen["objects"]),
            }
    else:
        report["steps"]["reopen_and_verify"] = {
            "status": "FAIL", "detail": "blend file missing: %s" % blend_path,
        }

    failed = [n for n, r in report["steps"].items() if r["status"] == "FAIL"]
    report["failed_steps"] = failed
    report["overall"] = "PASS" if not failed else "FAIL"

    project_dir = os.path.join(PROJECTS_ROOT, PROJECT_NAME)
    report_dir = os.path.join(project_dir, "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "integration_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)

    marker("INTEGRATION TEST %s" % report["overall"])
    print("Report: %s" % report_path)
    if failed:
        print("Failed steps: %s" % ", ".join(failed))
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
