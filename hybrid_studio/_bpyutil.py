"""Internal helper: lazy ``bpy`` access.

Keeping the import lazy means every module in this package can be imported
(and byte-compiled / unit-tested) outside Blender, while Blender-only
functions fail with a clear, actionable error when ``bpy`` is missing.
"""


class BlenderRequiredError(RuntimeError):
    pass


def require_bpy():
    """Import and return bpy, or raise BlenderRequiredError."""
    try:
        import bpy
    except ImportError as exc:
        raise BlenderRequiredError(
            "This function requires Blender's Python API (bpy). Run it inside "
            "Blender 5.2.3 (e.g. `blender -b --python script.py`). Original "
            "error: %s" % exc
        )
    return bpy


def has_bpy():
    try:
        import bpy  # noqa: F401
        return True
    except ImportError:
        return False
