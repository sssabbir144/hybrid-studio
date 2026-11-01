"""2D/3D compositing (Blender / bpy + pure planning helpers).

Enables the compositor with a basic node chain (Render Layers -> subtle
glare/grade -> Composite) and documents the intended 2D/3D layer ordering
used by the hybrid pipeline. Defensive about Blender 5.x, where the
compositor may live either on ``scene.node_tree`` (legacy) or on
``scene.compositing_node_group`` (newer).
"""

from ._bpyutil import require_bpy
from .studio_log import get_logger

log = get_logger("hybrid_studio.compositing")

# Hybrid layer order: 3D base, 2D Grease Pencil above it, grade, output.
LAYER_ORDER = [
    {"order": 1, "layer": "3D_RENDER", "content": "Blender 3D render layer (characters + environment)"},
    {"order": 2, "layer": "2D_GREASE_PENCIL", "content": "Grease Pencil effects rendered/overlaid above 3D"},
    {"order": 3, "layer": "GRADE_GLARE", "content": "Colour grade + subtle glare for magic/emissive elements"},
    {"order": 4, "layer": "OUTPUT", "content": "Composite output to file / VSE"},
]


def layer_order_plan():
    """Return the documented 2D/3D compositing layer order."""
    return [dict(row) for row in LAYER_ORDER]


def _get_compositor_tree(scene):
    """Return (tree, flavour) for this Blender version's compositor."""
    legacy_tree = getattr(scene, "node_tree", None)
    if legacy_tree is not None:
        try:
            scene.use_nodes = True
            return scene.node_tree, "scene.node_tree"
        except Exception:
            pass
    group = getattr(scene, "compositing_node_group", None)
    if group is None:
        import bpy
        group = bpy.data.node_groups.new("Compositing", "CompositorNodeTree")
        scene.compositing_node_group = group
    return group, "scene.compositing_node_group"


def setup_compositor(scene, glare_type="FOG_GLOW", glare_threshold=0.85):
    """Build Render Layers -> Glare -> Composite. Returns node names."""
    bpy = require_bpy()
    tree, flavour = _get_compositor_tree(scene)
    tree.nodes.clear()
    rlayers = tree.nodes.new("CompositorNodeRLayers")
    rlayers.location = (-300, 0)
    glare = None
    try:
        glare = tree.nodes.new("CompositorNodeGlare")
        glare.location = (0, 0)
        try:
            glare.glare_type = glare_type
        except Exception:
            log.warning("glare_type %r unsupported; keeping default", glare_type)
        try:
            glare.threshold = float(glare_threshold)
        except Exception:
            pass
    except Exception as exc:
        log.warning("Glare node unavailable (%s); compositing without it", exc)
    composite = tree.nodes.new("CompositorNodeComposite")
    composite.location = (300, 0)
    if glare is not None:
        tree.links.new(rlayers.outputs["Image"], glare.inputs["Image"])
        tree.links.new(glare.outputs["Image"], composite.inputs["Image"])
    else:
        tree.links.new(rlayers.outputs["Image"], composite.inputs["Image"])
    names = [node.name for node in tree.nodes]
    log.info("Compositor ready via %s with nodes: %s", flavour, ", ".join(names))
    return {"tree_flavour": flavour, "nodes": names, "layer_order": layer_order_plan()}
