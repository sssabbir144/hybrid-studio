# =====================================================================
# HYBRID STUDIO WORKFLOW: "শালিক পাখির দুঃখ আর বুড়ি মা" (30s Shorts)
# Target Environment: Blender 5.2.3 LTS (Pinned Version)
# Style Reference: Cinematic Stylized, Dramatic Lighting, Emotional Mood
# Fixed against the real hybrid_studio API (Steps 2-5) - Super Agent
# =====================================================================

import bpy
from hybrid_studio import check_environment, _bpyutil

def setup_shalik_story_pipeline():
    print("=== Initializing Hybrid Studio: Shalik & Buri Ma Pipeline ===")

    # ১. এনভায়রনমেন্ট এবং ভার্সন গার্ড চেক (Runtime Version Guard)
    # check_environment() নিজেই ভুল ভার্সনে RuntimeError দিয়ে থামায় -
    # কোনো মান ফেরত দেয় না, তাই if দিয়ে যাচাই করা যাবে না।
    check_environment()

    # ২. সিন এবং ক্যামেরা সেটআপ (Cinematic Lighting & Composition)
    scene = bpy.context.scene
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920  # Vertical Shorts Format (9:16)
    scene.render.resolution_percentage = 100

    # রেন্ডার ফরম্যাট পিএনজি সেট করা (Compat Layer ব্যবহার করে)
    # set_image_format চায় image_settings অবজেক্ট, পুরো scene নয়।
    used_attr = _bpyutil.set_image_format(scene.render.image_settings, 'PNG')
    print(f"Render format set via attribute: {used_attr}")

    # ৩. কম্পোসিটর ট্রি এবং ড্রামাটিক কালার গ্রেডিং সেটআপ (Emotional Color Palette)
    # 5.2.3-তে ট্রি scene.node_tree-তেও থাকতে পারে, Node Group-এও -
    # compat layer দিয়েই নিতে হয়।
    tree, source = _bpyutil.get_compositor_tree(scene)
    print(f"Compositor tree via: {source}")

    # পুরনো নোড পরিষ্কার করে নতুন নোড গ্রুপিং তৈরি
    for node in list(tree.nodes):
        tree.nodes.remove(node)

    render_node = _bpyutil.new_node(tree, 'CompositorNodeRLayers')
    output_node = _bpyutil.new_node(
        tree, 'CompositorNodeComposite', fallbacks=('NodeGroupOutput',))
    output_node.location = (400, 0)

    tree.links.new(render_node.outputs['Image'], output_node.inputs[0])

    # ৪. শালিক পাখি ও বুড়ি মার অ্যানিমেশন ডেটা (Layered Action & FCurves Collection)
    # _bpyutil.collect_fcurves ব্যবহার করে নিখুঁত টাইমিং মেইনটেইন করা
    actions = [obj.animation_data.action for obj in scene.objects
               if obj.animation_data and obj.animation_data.action]
    for action in actions:
        fcurves = _bpyutil.collect_fcurves(action)
        print(f"Collected {len(fcurves)} fcurves for action: {action.name}")

    print("=== Workflow Ready: Shalik Bird & Buri Ma Scene Successfully Configured! ===")

if __name__ == "__main__":
    setup_shalik_story_pipeline()
