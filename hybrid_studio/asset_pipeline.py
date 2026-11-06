"""External 3D asset pipeline (Prisma 3D -> Blender).

Prisma 3D (the phone app) exports models as Wavefront ``.obj`` or
Autodesk ``.fbx`` files. This module is the toolkit's single entry point
for bringing those files into a Blender scene:

- ``scan_incoming(folder)`` -- pure Python (no Blender needed): list the
  supported asset files waiting in a folder, with sizes.
- ``import_asset(bpy, filepath, ...)`` -- import one file with the
  correct Blender 5.2.3 operator, move the new objects into a dedicated
  collection, optionally ground them on Z=0 / scale them to a target
  height, and return a report dict.
- ``import_incoming(bpy, folder, ...)`` -- batch version for a folder
  (by default the repo's ``assets/prisma3d/incoming``).

Repo layout (see ``assets/README.md``)::

    assets/prisma3d/incoming/    raw exports dropped from the phone
    assets/prisma3d/processed/   cleaned .blend results saved by the CLI
    assets/prisma3d/textures/    texture images belonging to the models

Version-sensitive operator access (``bpy.ops.wm.obj_import`` vs the
legacy ``bpy.ops.import_scene.obj``) is probed before use, following the
project rule that all such access goes through ``_bpyutil`` helpers --
here ``_get_op`` below, built on ``_bpyutil.safe_getattr``.
"""

import os

from ._bpyutil import require_bpy, safe_getattr
from .studio_log import get_logger

log = get_logger("hybrid_studio.asset_pipeline")

SUPPORTED_EXTENSIONS = (".obj", ".fbx", ".glb", ".gltf")

DEFAULT_COLLECTION = "Prisma3D_Imports"

# Repo-relative default inbox: <repo>/assets/prisma3d/incoming
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_INCOMING = os.path.join(_REPO_ROOT, "assets", "prisma3d", "incoming")


def scan_incoming(folder=None):
    """List supported asset files in *folder* (pure Python, no Blender).

    Returns a list of dicts ``{"path", "name", "ext", "size_bytes"}``
    sorted by file name. A missing folder yields an empty list.
    """
    folder = folder or DEFAULT_INCOMING
    found = []
    if not os.path.isdir(folder):
        log.warning("scan_incoming: folder does not exist: %s", folder)
        return found
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in SUPPORTED_EXTENSIONS:
            found.append({
                "path": path,
                "name": name,
                "ext": ext,
                "size_bytes": os.path.getsize(path),
            })
    return found


def _get_op(bpy, *paths):
    """Return the first available ``bpy.ops`` callable among *paths*.

    Each path is dotted, e.g. ``"wm.obj_import"``. Probing first keeps
    the importer working across Blender builds whose operator names
    differ (5.2.3 ships the new ``wm.obj_import``; older/alt builds may
    only have ``import_scene.obj``).
    """
    for path in paths:
        node = bpy.ops
        ok = True
        for part in path.split("."):
            node = safe_getattr(node, part)
            if node is None:
                ok = False
                break
        if ok and callable(node):
            return node
    return None


def _import_with_operator(bpy, filepath, ext):
    """Call the right import operator for *ext*; return the op used."""
    if ext == ".obj":
        op = _get_op(bpy, "wm.obj_import", "import_scene.obj")
        label = "obj"
    elif ext == ".fbx":
        op = _get_op(bpy, "import_scene.fbx")
        label = "fbx"
    elif ext in (".glb", ".gltf"):
        op = _get_op(bpy, "import_scene.gltf")
        label = "gltf"
    else:
        raise ValueError("unsupported asset extension: %r" % ext)
    if op is None:
        raise RuntimeError(
            "no %s import operator available in this Blender build" % label)
    op(filepath=filepath)
    return label


def _world_bbox(bpy, obj):
    """World-space bounding box corners of *obj* as (min, max) tuples."""
    import mathutils
    corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    zs = [c.z for c in corners]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _ground_and_scale(bpy, obj, target_height=None):
    """Apply the object's scale, optionally rescale to *target_height*
    metres, and drop it so its lowest point sits on Z=0."""
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.transform_apply(location=False, rotation=False,
                                   scale=True)
    obj.select_set(False)
    (mn, mx) = _world_bbox(bpy, obj)
    height = mx[2] - mn[2]
    if target_height and height > 1e-6:
        factor = float(target_height) / height
        obj.scale = (obj.scale[0] * factor,
                     obj.scale[1] * factor,
                     obj.scale[2] * factor)
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)
        bpy.ops.object.transform_apply(location=False, rotation=False,
                                       scale=True)
        obj.select_set(False)
        (mn, mx) = _world_bbox(bpy, obj)
        height = mx[2] - mn[2]
    obj.location.z -= mn[2]
    return height


def import_asset(bpy, filepath, collection_name=DEFAULT_COLLECTION,
                 ground=True, target_height=None):
    """Import one .obj/.fbx/.glb file into the current scene.

    New objects are moved into the *collection_name* collection (created
    if needed). With ``ground=True`` (default) each mesh is dropped onto
    Z=0 after its scale is applied; ``target_height`` (metres, optional)
    rescales each mesh to exactly that height first -- handy because
    Prisma 3D exports are often in centimetre-ish units.

    Returns a report dict: ``{"file", "format", "operator", "objects",
    "meshes", "materials", "dimensions"}`` where ``dimensions`` is the
    combined (x, y, z) size in metres after any normalisation.
    """
    bpy = bpy or require_bpy()
    filepath = os.path.abspath(filepath)
    if not os.path.isfile(filepath):
        raise FileNotFoundError("asset file not found: %s" % filepath)
    ext = os.path.splitext(filepath)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError("unsupported asset extension: %r" % ext)

    before = set(bpy.data.objects)
    operator = _import_with_operator(bpy, filepath, ext)
    new_objects = [o for o in bpy.data.objects if o not in before]
    if not new_objects:
        raise RuntimeError("import produced no objects: %s" % filepath)

    collection = bpy.data.collections.get(collection_name)
    if collection is None:
        collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(collection)
    for obj in new_objects:
        for parent in list(obj.users_collection):
            parent.objects.unlink(obj)
        collection.objects.link(obj)

    meshes = [o for o in new_objects if o.type == "MESH"]
    if ground or target_height:
        for obj in meshes:
            _ground_and_scale(bpy, obj, target_height=target_height)

    materials = sorted({slot.material.name
                        for o in meshes
                        for slot in o.material_slots if slot.material})
    dims = (0.0, 0.0, 0.0)
    if meshes:
        mins = [None, None, None]
        maxs = [None, None, None]
        for obj in meshes:
            mn, mx = _world_bbox(bpy, obj)
            for i in range(3):
                mins[i] = mn[i] if mins[i] is None else min(mins[i], mn[i])
                maxs[i] = mx[i] if maxs[i] is None else max(maxs[i], mx[i])
        dims = tuple(round(maxs[i] - mins[i], 4) for i in range(3))

    report = {
        "file": filepath,
        "format": ext.lstrip("."),
        "operator": operator,
        "objects": [o.name for o in new_objects],
        "meshes": len(meshes),
        "materials": materials,
        "dimensions": dims,
    }
    log.info("imported %s -> %d object(s), dims %s",
             os.path.basename(filepath), len(new_objects), dims)
    return report


def import_incoming(bpy, folder=None, **kwargs):
    """Import every supported file in *folder* (default: repo inbox).

    Returns a list of per-file report dicts; a file that fails to import
    gets ``{"file": ..., "error": "..."}`` instead of raising, so one bad
    export never blocks the rest of the batch.
    """
    bpy = bpy or require_bpy()
    reports = []
    for entry in scan_incoming(folder):
        try:
            reports.append(import_asset(bpy, entry["path"], **kwargs))
        except Exception as exc:  # per-file isolation is intentional
            log.error("failed to import %s: %s", entry["name"], exc)
            reports.append({"file": entry["path"], "error": str(exc)})
    return reports
