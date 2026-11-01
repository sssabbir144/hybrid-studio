"""2D Grease Pencil production (Blender / bpy).

Blender 5.x uses Grease Pencil v3, whose Python API differs significantly
from v2 (data lives in ``bpy.data.grease_pencils`` as the new GreasePencil
type, drawings hang off layer frames, strokes are created with
``drawing.add_strokes`` and point positions live in the ``position``
attribute). This module tries the v3 API first, then the v2 API, and raises
:class:`GreasePencilAPIError` with a detailed message if neither works —
it never silently pretends an effect was created.
"""

import math

from ._bpyutil import require_bpy
from .studio_log import get_logger

log = get_logger("hybrid_studio.grease_pencil")


class GreasePencilAPIError(RuntimeError):
    """Raised when the Grease Pencil API does not behave as expected."""


def _star_points(center=(0.0, 0.0, 2.4), radius=0.45, spikes=4):
    """Polyline points for a sparkling 4-point star outline (closed)."""
    cx, cy, cz = center
    pts = []
    steps = spikes * 2
    for i in range(steps + 1):
        angle = (i / steps) * math.tau + math.pi / 2.0
        r = radius if i % 2 == 0 else radius * 0.28
        pts.append((cx + r * math.cos(angle), cy, cz + r * math.sin(angle)))
    return pts


def _swirl_points(center=(0.0, 0.0, 2.4), radius=0.5, turns=1.5, count=40):
    cx, cy, cz = center
    pts = []
    for i in range(count):
        t = i / float(count - 1)
        angle = t * turns * math.tau
        r = radius * (1.0 - t * 0.75)
        pts.append((cx + r * math.cos(angle), cy, cz + r * math.sin(angle)))
    return pts


def create_gp_object(bpy, name):
    """Create a Grease Pencil object (v3 preferred, v2 fallback)."""
    # Preferred: operator creates a valid v3 object with a default layer.
    try:
        bpy.ops.object.grease_pencil_add(type="EMPTY")
        obj = bpy.context.active_object
        if obj is not None and obj.type == "GREASEPENCIL":
            obj.name = name
            return obj
    except Exception as exc:  # operator unavailable (e.g. no view layer)
        log.warning("grease_pencil_add operator failed (%s); trying data API", exc)
    # Data-API fallback (v2 style data block).
    data = None
    for coll_name in ("grease_pencils_v3", "grease_pencils"):
        coll = getattr(bpy.data, coll_name, None)
        if coll is not None:
            try:
                data = coll.new(name)
                break
            except Exception:
                continue
    if data is None:
        raise GreasePencilAPIError(
            "Could not create a Grease Pencil data block: neither "
            "bpy.ops.object.grease_pencil_add nor bpy.data.grease_pencils "
            "worked. This Blender build's GP API differs from v2/v3 "
            "expectations."
        )
    obj = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(obj)
    return obj


def _get_layer(gp_data, layer_name):
    layers = getattr(gp_data, "layers", None)
    if layers is None:
        raise GreasePencilAPIError("Grease Pencil data has no 'layers' attribute")
    for layer in layers:
        if layer.name == layer_name:
            return layer
    try:
        return layers.new(layer_name, set_active=True)
    except TypeError:
        return layers.new(layer_name)
    except Exception as exc:
        raise GreasePencilAPIError("Could not create GP layer %r: %s" % (layer_name, exc))


def _get_drawing(layer, frame_number):
    """Return (drawing, api_flavour) for a layer frame, creating it if possible."""
    frames = getattr(layer, "frames", None)
    if frames is None:
        raise GreasePencilAPIError("GP layer has no 'frames' attribute")
    for frame in frames:
        if getattr(frame, "frame_number", None) == frame_number:
            drawing = getattr(frame, "drawing", None)
            if drawing is not None:
                return drawing
    if len(frames) > 0:
        drawing = getattr(frames[0], "drawing", None)
        if drawing is not None:
            return drawing
    new = getattr(frames, "new", None)
    if callable(new):
        try:
            frame = new(frame_number)
            drawing = getattr(frame, "drawing", None)
            if drawing is not None:
                return drawing
        except Exception as exc:
            log.warning("frames.new(%d) failed: %s", frame_number, exc)
    raise GreasePencilAPIError(
        "No drawing available on GP layer %r and no way to create one "
        "(frames collection: %s). The Grease Pencil frame API differs "
        "from expectations." % (getattr(layer, "name", "?"), type(frames).__name__)
    )


def _add_stroke(drawing, points):
    """Add one stroke through ``points``; tries v3 then v2 stroke APIs."""
    flat = [coord for point in points for coord in point]
    # --- Grease Pencil v3 -------------------------------------------------
    add_strokes = getattr(drawing, "add_strokes", None)
    if callable(add_strokes):
        add_strokes([len(points)])
        stroke = drawing.strokes[-1]
        pts = stroke.points
        try:
            pts.foreach_set("position", flat)
        except Exception:
            for i, point in enumerate(points):
                try:
                    pts[i].position = point
                except Exception:
                    pts[i].co = point
        try:
            stroke.radius = 0.02
        except Exception:
            pass
        return stroke
    # --- Grease Pencil v2 -------------------------------------------------
    strokes = getattr(drawing, "strokes", None)
    if strokes is not None and hasattr(strokes, "new"):
        stroke = strokes.new()
        stroke.points.add(len(points))
        for i, point in enumerate(points):
            stroke.points[i].co = point
        return stroke
    raise GreasePencilAPIError(
        "Drawing object %r supports neither v3 add_strokes nor v2 "
        "strokes.new(); cannot create an effect stroke." % type(drawing).__name__
    )


def _gp_material(bpy, gp_data, name, hex_color):
    from .character_manager import hex_to_rgba
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    gp_settings = getattr(mat, "grease_pencil", None)
    if gp_settings is not None:
        gp_settings.color = hex_to_rgba(hex_color)
        gp_settings.fill_color = hex_to_rgba(hex_color, alpha=0.35)
    try:
        gp_data.materials.append(mat)
    except Exception as exc:
        log.warning("Could not append GP material: %s", exc)
    return mat


def create_sparkle_effect(name="GP_Sparkle", layer_name="Effects",
                          center=(0.0, 0.0, 2.4), color="#FFD94D",
                          frame_number=1, effect="star"):
    """Create a GP object with one sparkling effect stroke.

    ``effect``: "star" (closed 4-point star) or "swirl" (open spiral).
    Returns the Grease Pencil object. Raises GreasePencilAPIError with a
    detailed message if the GP API of this Blender build differs.
    """
    bpy = require_bpy()
    if effect not in ("star", "swirl"):
        raise ValueError("effect must be 'star' or 'swirl', got %r" % effect)
    obj = create_gp_object(bpy, name)
    gp_data = obj.data
    layer = _get_layer(gp_data, layer_name)
    drawing = _get_drawing(layer, frame_number)
    if effect == "star":
        points = _star_points(center)
    else:
        points = _swirl_points(center)
    stroke = _add_stroke(drawing, points)
    _gp_material(bpy, gp_data, "%s_Mat" % name, color)
    log.info(
        "Grease Pencil effect '%s' (%s, %d points) created on layer '%s'",
        name, effect, len(points), layer_name,
    )
    return obj
