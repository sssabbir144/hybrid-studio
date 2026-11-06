"""CLI: import Prisma 3D exports (.obj/.fbx) into a Blender scene.

Usage (from the repo root):

    blender -b --python scripts/import_prisma3d.py -- [options] [PATH ...]

    PATH ...            files and/or folders to import; a folder is
                        scanned for .obj/.fbx/.glb/.gltf files. With no
                        PATH, the repo inbox is used:
                        assets/prisma3d/incoming/
    --save OUT.blend    save the resulting scene to OUT.blend (put
                        results in assets/prisma3d/processed/)
    --target-height M   rescale each imported mesh to M metres tall
    --no-ground         keep the imported position (default: rest on Z=0)
    --collection NAME   target collection (default: Prisma3D_Imports)

Prints one ``ASSET_REPORT`` JSON line per imported file and finishes
with ``PRISMA_IMPORT: OK/FAIL``.
"""

import json
import os
import sys

# Blender adds only this script's own folder to sys.path, so insert the
# repo root (parent of scripts/) ourselves -- lesson from the Shalik
# Stage-1 runs: PYTHONPATH does not help on this build.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import bpy  # noqa: E402

from hybrid_studio import asset_pipeline  # noqa: E402


def _parse_args(argv):
    opts = {"paths": [], "save": None, "target_height": None,
            "ground": True, "collection": asset_pipeline.DEFAULT_COLLECTION}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--save":
            i += 1
            opts["save"] = argv[i]
        elif arg == "--target-height":
            i += 1
            opts["target_height"] = float(argv[i])
        elif arg == "--no-ground":
            opts["ground"] = False
        elif arg == "--collection":
            i += 1
            opts["collection"] = argv[i]
        else:
            opts["paths"].append(arg)
        i += 1
    return opts


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    opts = _parse_args(argv)

    targets = []
    for path in opts["paths"] or [asset_pipeline.DEFAULT_INCOMING]:
        if os.path.isdir(path):
            targets.extend(e["path"] for e in asset_pipeline.scan_incoming(path))
        else:
            targets.append(path)

    reports = []
    for path in targets:
        try:
            reports.append(asset_pipeline.import_asset(
                bpy, path,
                collection_name=opts["collection"],
                ground=opts["ground"],
                target_height=opts["target_height"]))
        except Exception as exc:  # report and continue with the batch
            reports.append({"file": path, "error": str(exc)})

    for report in reports:
        print("ASSET_REPORT " + json.dumps(report, ensure_ascii=False))

    if opts["save"] and any("error" not in r for r in reports):
        out = os.path.abspath(opts["save"])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print("SAVED " + out)

    ok = bool(reports) and all("error" not in r for r in reports)
    print("PRISMA_IMPORT: " + ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
