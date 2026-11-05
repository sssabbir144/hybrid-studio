"""Runtime tests for the Hybrid Studio Blender 5.2.3 compatibility layer.

Run INSIDE Blender (full suite):

    blender -b --python test_studio_runtime.py

Run OUTSIDE Blender (mock suite only — Blender checks are skipped):

    python3 test_studio_runtime.py

What is covered:
- ``hybrid_studio._bpyutil`` probes: ``safe_getattr``, ``is_real_collection``
- ``set_image_format`` fallback order (``file_format`` -> ``format`` ->
  introspected attribute -> clear RuntimeError)
- ``collect_fcurves`` across every Action shape: layered ``channelbags``
  collection, ``channelbag(slot)`` *method* (the Blender 5.2.3 shape that
  broke the old code), legacy plain-property channelbag, legacy direct
  ``action.fcurves``
- Runtime Version Guard: no-op outside Blender; accepts the tested build;
  raises a clear RuntimeError on a simulated version mismatch
- Inside Blender only: a REAL keyframed action, the REAL
  ``ImageFormatSettings``, and compositor tree/node probing

Every check prints ``[PASS]``/``[FAIL]``; the run ends with the marker
``TEST_STUDIO_RUNTIME: ALL PASS`` or ``TEST_STUDIO_RUNTIME: FAILURES=<n>``
and exits with that failure count.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hybrid_studio import _bpyutil  # noqa: E402

FAILURES = []


def check(name, condition, detail=""):
    print("[%s] %s%s" % ("PASS" if condition else "FAIL", name,
                         (" - " + detail) if detail else ""))
    if not condition:
        FAILURES.append(name)


def check_raises(name, func, exc_type):
    try:
        func()
    except exc_type:
        check(name, True)
    except Exception as exc:  # noqa: BLE001
        check(name, False, "wrong exception: %r" % exc)
    else:
        check(name, False, "no exception raised")


# ---------------------------------------------------------------------------
# Fakes simulating the Blender API shapes (no Blender needed)
# ---------------------------------------------------------------------------

class FakeImageSettingsNew:
    def __init__(self):
        self.file_format = "JPEG"


class FakeImageSettingsLegacy:
    def __init__(self):
        self.format = "JPEG"


class FakeImageSettingsNone:
    def __init__(self):
        self.quality = 90


class FakeFCurve:
    def __init__(self, path):
        self.data_path = path


class FakeBag:
    def __init__(self, fcurves):
        self.fcurves = fcurves


class FakeStripCollection:
    """5.2.3 shape A: strip.channelbags is a real collection."""

    def __init__(self, bags):
        self.channelbags = bags


class FakeStripMethod:
    """5.2.3 shape B: strip.channelbag is a METHOD taking an Action Slot.

    This is the shape that killed the old code with
    ``AttributeError: 'bpy_func' object has no attribute 'fcurves'``.
    """

    def __init__(self, bag):
        self._bag = bag

    def channelbag(self, slot):
        return self._bag


class FakeStripLegacyBag:
    """Legacy shape: strip.channelbag is a plain property."""

    def __init__(self, bag):
        self.channelbag = bag


class FakeLayer:
    def __init__(self, strips):
        self.strips = strips


class FakeActionLayered:
    def __init__(self, strips, slots=()):
        self.name = "FakeLayered"
        self.layers = [FakeLayer(strips)]
        self.slots = list(slots)


class FakeActionLegacy:
    def __init__(self, fcurves):
        self.name = "FakeLegacy"
        self.fcurves = fcurves


# ---------------------------------------------------------------------------
# Mock suite (runs anywhere)
# ---------------------------------------------------------------------------

def mock_tests():
    check("safe_getattr returns default for missing attr",
          _bpyutil.safe_getattr(object(), "nope", 42) == 42)
    check("is_real_collection: list is real",
          _bpyutil.is_real_collection([1, 2]))
    check("is_real_collection: method is NOT a collection (5.2.3 trap)",
          not _bpyutil.is_real_collection(FakeStripMethod(None).channelbag))
    check("is_real_collection: None is not a collection",
          not _bpyutil.is_real_collection(None))

    new = FakeImageSettingsNew()
    used = _bpyutil.set_image_format(new, "PNG")
    check("set_image_format prefers file_format",
          used == "file_format" and new.file_format == "PNG")
    legacy = FakeImageSettingsLegacy()
    used = _bpyutil.set_image_format(legacy, "OPEN_EXR")
    check("set_image_format falls back to legacy format",
          used == "format" and legacy.format == "OPEN_EXR")
    check_raises("set_image_format raises clearly when nothing exists",
                 lambda: _bpyutil.set_image_format(FakeImageSettingsNone(), "PNG"),
                 RuntimeError)

    bag = FakeBag([FakeFCurve("location"), FakeFCurve("location")])
    action = FakeActionLayered([FakeStripCollection([bag])])
    check("collect_fcurves: channelbags collection shape",
          len(_bpyutil.collect_fcurves(action)) == 2)

    slot = object()
    bag = FakeBag([FakeFCurve("rotation_euler")] * 3)
    action = FakeActionLayered([FakeStripMethod(bag)], slots=[slot])
    check("collect_fcurves: channelbag(slot) method shape (5.2.3)",
          len(_bpyutil.collect_fcurves(action)) == 3)

    bag = FakeBag([FakeFCurve("scale")])
    action = FakeActionLayered([FakeStripLegacyBag(bag)])
    check("collect_fcurves: legacy plain-property channelbag",
          len(_bpyutil.collect_fcurves(action)) == 1)

    action = FakeActionLegacy([FakeFCurve("location")] * 4)
    check("collect_fcurves: legacy direct action.fcurves",
          len(_bpyutil.collect_fcurves(action)) == 4)

    if not _bpyutil.has_bpy():
        check("version guard is a no-op outside Blender",
              _bpyutil.check_blender_version() is None)


# ---------------------------------------------------------------------------
# Blender suite (only inside Blender)
# ---------------------------------------------------------------------------

def blender_tests():
    import bpy

    check("running inside Blender %s" % (tuple(bpy.app.version),), True)
    check("version guard accepts the tested build",
          _bpyutil.check_blender_version() is None)

    original = _bpyutil.TESTED_BLENDER_VERSION
    try:
        _bpyutil.TESTED_BLENDER_VERSION = (99, 0, 0)
        check_raises("version guard stops a mismatched build",
                     _bpyutil.check_blender_version, RuntimeError)
    finally:
        _bpyutil.TESTED_BLENDER_VERSION = original

    import hybrid_studio
    check("package import + startup guard (hybrid_studio.check_environment)",
          hybrid_studio.check_environment() is None)

    # Real layered action: keyframe a cube's location.
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.object
    cube.keyframe_insert(data_path="location", frame=1)
    action = cube.animation_data.action
    fcurves = _bpyutil.collect_fcurves(action)
    check("collect_fcurves on a REAL 5.x layered action",
          len(fcurves) >= 3, "found %d fcurves" % len(fcurves))

    settings = bpy.context.scene.render.image_settings
    used = _bpyutil.set_image_format(settings, "PNG")
    check("set_image_format on REAL ImageFormatSettings",
          used == "file_format" and settings.file_format == "PNG")

    tree, source = _bpyutil.get_compositor_tree(bpy.context.scene)
    check("compositor tree resolved", tree is not None, "via %s" % source)
    node = _bpyutil.new_node(tree, "CompositorNodeComposite",
                             fallbacks=("NodeGroupOutput",))
    check("compositor output node created (probe + fallback)",
          node is not None, "type: %s" % node.bl_idname)


def main():
    print("=" * 60)
    print("Hybrid Studio runtime tests - Blender 5.2.3 compatibility")
    print("=" * 60)
    mock_tests()
    if _bpyutil.has_bpy():
        blender_tests()
    else:
        print("[SKIP] Blender-only checks (bpy not available)")
    print("-" * 60)
    if FAILURES:
        print("TEST_STUDIO_RUNTIME: FAILURES=%d (%s)"
              % (len(FAILURES), ", ".join(FAILURES)))
    else:
        print("TEST_STUDIO_RUNTIME: ALL PASS")
    return len(FAILURES)


if __name__ == "__main__":
    sys.exit(main())
