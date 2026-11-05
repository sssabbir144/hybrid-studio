"""Main plugin integration for the Hybrid Animation Studio.

This module is the Blender-facing entry point of the package. It wires
together, in one place:

- the **Runtime Version Guard** (``hybrid_studio.check_environment`` /
  ``_bpyutil.check_blender_version``) — registration refuses to proceed
  on an untested Blender build, with a clear error, before any UI or
  tool code runs;
- the studio's **UI panels** (3D Viewport sidebar, "Hybrid Studio"
  category): pipeline, animation-tools and render/compositor panels;
- the **animation tools** (``controller.StudioController`` pipeline,
  easing via the compatibility layer, compositor setup, render format) —
  every version-sensitive ``bpy`` access inside the operators goes
  through :mod:`hybrid_studio._bpyutil`, the Blender 5.2.3
  compatibility layer (layered-action channelbags, ``file_format``
  fallback, compositor probing).

House rules kept: importing this module outside Blender is safe (all
``bpy`` access is lazy, classes are built on first ``register()``), and
``register()`` outside Blender raises ``BlenderRequiredError`` with an
actionable message.

Inside Blender, enable it like any addon module::

    import hybrid_studio.plugin as plugin
    plugin.register()      # ... work ...
    plugin.unregister()
"""

from . import _bpyutil
from ._bpyutil import require_bpy
from .studio_log import get_logger

log = get_logger("hybrid_studio.plugin")

bl_info = {
    "name": "Hybrid Animation Studio",
    "author": "Sabbir Hossin (Ss Animation)",
    "version": (2, 0, 0),
    "blender": (5, 2, 3),
    "location": "View3D > Sidebar > Hybrid Studio",
    "description": "Hybrid 2D+3D cartoon studio: pipeline, animation "
                   "tools, compositor and render - Blender 5.2.3 ready.",
    "category": "Animation",
}

_CLASSES = None


def _build_classes():
    """Define the bpy UI classes (only callable inside Blender)."""
    bpy = require_bpy()
    from bpy.types import Operator, Panel

    class HYBRID_OT_build_demo_scene(Operator):
        """Run the full studio pipeline (controller.build_demo_scene)."""
        bl_idname = "hybrid.build_demo_scene"
        bl_label = "Build Demo Scene"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            from .controller import StudioController
            ctrl = StudioController()
            root = ctrl.config.get("paths", {}).get("projects_root", "projects")
            name = ctrl.config.get("project_name", "hybrid_studio_project")
            ctrl.create_project(root, name)
            ctrl.register_demo_character()
            ctrl.create_demo_story()
            report = ctrl.build_demo_scene()
            failed = report.get("failed_steps", [])
            if failed:
                self.report({"ERROR"}, "Pipeline FAIL: %s" % ", ".join(failed))
                return {"CANCELLED"}
            self.report({"INFO"}, "Pipeline PASS - blend: %s"
                        % report.get("blend_path"))
            return {"FINISHED"}

    class HYBRID_OT_apply_easing(Operator):
        """Apply easing to the active object's action via _bpyutil.

        Fcurves are collected with ``_bpyutil.collect_fcurves`` so
        Blender 5.x layered actions (channelbags / channelbag(slot))
        work - the old direct ``action.fcurves`` path does not.
        """
        bl_idname = "hybrid.apply_easing"
        bl_label = "Apply Easing (Active Action)"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            obj = context.object
            action = obj.animation_data.action if obj and obj.animation_data else None
            if action is None:
                self.report({"ERROR"}, "No active object with an action")
                return {"CANCELLED"}
            count = 0
            for fcurve in _bpyutil.collect_fcurves(action):
                for point in fcurve.keyframe_points:
                    point.interpolation = "BEZIER"
                    point.handle_left_type = "AUTO_CLAMPED"
                    point.handle_right_type = "AUTO_CLAMPED"
                    count += 1
            self.report({"INFO"}, "Easing applied to %d keyframe points" % count)
            return {"FINISHED"}

    class HYBRID_OT_set_render_format(Operator):
        """Set the render file format through the compat layer."""
        bl_idname = "hybrid.set_render_format_png"
        bl_label = "Set Render Format: PNG"
        bl_options = {"REGISTER"}

        def execute(self, context):
            settings = context.scene.render.image_settings
            used = _bpyutil.set_image_format(settings, "PNG")
            self.report({"INFO"}, "Render format set via %r attribute" % used)
            return {"FINISHED"}

    class HYBRID_OT_setup_compositor(Operator):
        """Build the studio compositor setup for the current scene."""
        bl_idname = "hybrid.setup_compositor"
        bl_label = "Setup Compositor"
        bl_options = {"REGISTER", "UNDO"}

        def execute(self, context):
            from . import compositing
            tree, source = _bpyutil.get_compositor_tree(context.scene)
            log.info("Compositor tree via %s", source)
            result = compositing.setup_compositor(context.scene)
            self.report({"INFO"}, "Compositor ready: %s" % result["nodes"])
            return {"FINISHED"}

    class HYBRID_PT_main(Panel):
        """Main Hybrid Studio panel (pipeline + guard status)."""
        bl_idname = "HYBRID_PT_main"
        bl_label = "Hybrid Studio"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Hybrid Studio"

        def draw(self, context):
            layout = self.layout
            tested = ".".join(map(str, _bpyutil.TESTED_BLENDER_VERSION))
            running = bpy.app.version_string
            layout.label(text="Blender %s (tested: %s)" % (running, tested))
            layout.operator("hybrid.build_demo_scene", icon="SCENE_DATA")

    class HYBRID_PT_animation_tools(Panel):
        """Animation tools sub-panel."""
        bl_idname = "HYBRID_PT_animation_tools"
        bl_label = "Animation Tools"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Hybrid Studio"
        bl_parent_id = "HYBRID_PT_main"
        bl_options = {"DEFAULT_CLOSED"}

        def draw(self, context):
            self.layout.operator("hybrid.apply_easing", icon="GRAPH")

    class HYBRID_PT_render(Panel):
        """Render & compositor sub-panel."""
        bl_idname = "HYBRID_PT_render"
        bl_label = "Render & Compositor"
        bl_space_type = "VIEW_3D"
        bl_region_type = "UI"
        bl_category = "Hybrid Studio"
        bl_parent_id = "HYBRID_PT_main"
        bl_options = {"DEFAULT_CLOSED"}

        def draw(self, context):
            layout = self.layout
            layout.operator("hybrid.set_render_format_png", icon="IMAGE_DATA")
            layout.operator("hybrid.setup_compositor", icon="NODETREE")

    return (
        HYBRID_OT_build_demo_scene,
        HYBRID_OT_apply_easing,
        HYBRID_OT_set_render_format,
        HYBRID_OT_setup_compositor,
        HYBRID_PT_main,
        HYBRID_PT_animation_tools,
        HYBRID_PT_render,
    )


def _classes():
    global _CLASSES
    if _CLASSES is None:
        _CLASSES = _build_classes()
    return _CLASSES


def register():
    """Register the plugin: runtime guard first, then the UI classes.

    Raises RuntimeError immediately on an untested Blender build (the
    guard), and BlenderRequiredError outside Blender.
    """
    _bpyutil.check_blender_version()  # Runtime Version Guard
    bpy = require_bpy()
    for cls in _classes():
        bpy.utils.register_class(cls)
    log.info("Hybrid Studio plugin registered (Blender %s)",
             bpy.app.version_string)


def unregister():
    bpy = require_bpy()
    for cls in reversed(_classes()):
        bpy.utils.unregister_class(cls)
    log.info("Hybrid Studio plugin unregistered")
