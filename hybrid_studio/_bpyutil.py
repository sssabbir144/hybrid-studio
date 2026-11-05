"""Internal helper: lazy ``bpy`` access + Blender 5.2.3 compatibility layer.

Keeping the import lazy means every module in this package can be imported
(and byte-compiled / unit-tested) outside Blender, while Blender-only
functions fail with a clear, actionable error when ``bpy`` is missing.

ALL version-sensitive ``bpy`` access in this package goes through this
module (Step 3 rule): probe before use, order fallbacks new-API -> legacy,
and never fail silently. The patterns here mirror the validated fixes in
the ``hybrid-studio-fixes`` repository (animation / compositing /
render_manager).
"""

import logging

log = logging.getLogger(__name__)

# The Blender build this package is tested against. Keep in sync with
# "blender.tested_version" in studio_config.json.
TESTED_BLENDER_VERSION = (5, 2, 3)


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


# ---------------------------------------------------------------------------
# Runtime Version Guard
# ---------------------------------------------------------------------------

def check_blender_version():
    """Fail early, with a clear message, on an untested Blender build.

    Raises RuntimeError when the running Blender's major.minor differs
    from TESTED_BLENDER_VERSION; a patch-level difference only logs a
    warning. No-op outside Blender.
    """
    if not has_bpy():
        return
    import bpy
    running = tuple(bpy.app.version)[:3]
    tested = TESTED_BLENDER_VERSION
    if running[:2] != tested[:2]:
        raise RuntimeError(
            "Hybrid Studio is tested on Blender %s; running build is %s. "
            "APIs may differ - run api_diagnostic.py (hybrid-studio-fixes) "
            "inside this Blender and check MEMORY_BANK.md rules before use."
            % (".".join(map(str, tested)), ".".join(map(str, running)))
        )
    if running != tested:
        log.warning(
            "Blender patch version %s differs from tested %s; continuing.",
            ".".join(map(str, running)), ".".join(map(str, tested)),
        )


# ---------------------------------------------------------------------------
# Generic probes
# ---------------------------------------------------------------------------

def safe_getattr(obj, name, default=None):
    """getattr that never raises."""
    try:
        return getattr(obj, name)
    except Exception:
        return default


def is_real_collection(value):
    """True when value is a non-callable, iterable collection.

    In Blender 5.x some attributes that look like collections are actually
    ``bpy_func`` methods (e.g. ``strip.channelbag``); treating a method as
    a collection is the classic 5.2.3 AttributeError trap.
    """
    if value is None or callable(value):
        return False
    try:
        iter(value)
        return True
    except TypeError:
        return False


# ---------------------------------------------------------------------------
# ImageFormatSettings - `file_format`, not `format` (renamed in Blender 2.8+)
# ---------------------------------------------------------------------------

def set_image_format(image_settings, fmt):
    """Set the render file format across Blender API generations.

    Tries ``file_format`` first, then ``format``, then any introspected
    non-callable attribute whose name contains 'format'. Raises a clear
    RuntimeError listing the available attributes if none exists.
    """
    for attr in ("file_format", "format"):
        if hasattr(image_settings, attr):
            setattr(image_settings, attr, fmt)
            return attr
    for attr in dir(image_settings):
        if attr.startswith("_") or "format" not in attr.lower():
            continue
        if callable(safe_getattr(image_settings, attr)):
            continue
        setattr(image_settings, attr, fmt)
        log.warning(
            "ImageFormatSettings: using fallback attribute %r for the "
            "file format.", attr,
        )
        return attr
    raise RuntimeError(
        "ImageFormatSettings has no format attribute. Available: %s"
        % ", ".join(a for a in dir(image_settings) if not a.startswith("_"))
    )


# ---------------------------------------------------------------------------
# Layered Actions (Blender 5.x) - never touch action.fcurves directly
# ---------------------------------------------------------------------------

def _fcurves_from(holder):
    """Return holder's fcurves as a list, or [] if it has no real ones."""
    fcurves = safe_getattr(holder, "fcurves")
    if not is_real_collection(fcurves):
        return []
    return list(fcurves)


def _channelbags_for_strip(strip, action):
    """All channelbags of a keyframe strip, across Blender API shapes."""
    bags = []
    collection = safe_getattr(strip, "channelbags")
    if is_real_collection(collection):
        bags.extend(collection)
    legacy_bag = safe_getattr(strip, "channelbag")
    if legacy_bag is not None and not callable(legacy_bag):
        bags.append(legacy_bag)  # legacy plain-property shape
    method = safe_getattr(strip, "channelbag")
    if callable(method):
        slots = safe_getattr(action, "slots")
        if is_real_collection(slots):
            for slot in slots:
                try:
                    bag = method(slot)
                except Exception:
                    continue
                if bag is not None:
                    bags.append(bag)
    return bags


def collect_fcurves(action):
    """Collect every fcurve of an Action on Blender 5.x and legacy builds.

    Traversal order: layered strips' channelbags collection ->
    ``channelbag(slot)`` per Action Slot -> the strip itself -> legacy
    direct ``action.fcurves``. Logs a warning when an action has layered
    strips but no fcurves could be reached, instead of failing silently.
    """
    found = []
    layers = safe_getattr(action, "layers")
    has_layers = is_real_collection(layers)
    if has_layers:
        for layer in layers:
            strips = safe_getattr(layer, "strips")
            if not is_real_collection(strips):
                continue
            for strip in strips:
                for bag in _channelbags_for_strip(strip, action):
                    found.extend(_fcurves_from(bag))
                found.extend(_fcurves_from(strip))
    if not found:
        found = _fcurves_from(action)
    if has_layers and not found:
        log.warning(
            "Action %r has layered strips but no fcurves were reached.",
            safe_getattr(action, "name", action),
        )
    return found


# ---------------------------------------------------------------------------
# Compositor - tree location and node types are NOT guaranteed on 5.2.3
# ---------------------------------------------------------------------------

def get_compositor_tree(scene):
    """Return (tree, source) for the scene's compositor.

    Legacy ``scene.node_tree`` first; otherwise a fresh
    ``CompositorNodeTree`` node group (the 5.x location).
    """
    legacy = safe_getattr(scene, "node_tree")
    if legacy is not None:
        return legacy, "scene.node_tree"
    bpy = require_bpy()
    group = bpy.data.node_groups.new("Compositing", "CompositorNodeTree")
    return group, "node_groups.new(CompositorNodeTree)"


def new_node(tree, type_name, fallbacks=()):
    """Create a node, probing fallbacks when a type is undefined.

    On Blender 5.2.3 background mode some types (e.g.
    ``CompositorNodeComposite``) raise ``RuntimeError: Node type ...
    undefined``. Tries ``type_name`` then each of ``fallbacks``; raises a
    clear RuntimeError naming everything tried.
    """
    tried = []
    for candidate in (type_name,) + tuple(fallbacks):
        tried.append(candidate)
        try:
            return tree.nodes.new(candidate)
        except RuntimeError:
            continue
    raise RuntimeError(
        "No compositor node type could be created (tried: %s). "
        "Run api_diagnostic.py to see what this Blender build exposes."
        % ", ".join(tried)
    )
