"""Master controller for the Hybrid Animation Studio.

Creates/loads a project, dispatches to the production modules, and
collects a structured run report. The data-side methods (project, story,
characters) work outside Blender; the scene-building pipeline
(:meth:`StudioController.build_demo_scene`) runs inside Blender and is
what the integration test drives.
"""

import os

from .config import load_config, get_fps
from . import project_manager, story_manager, character_manager
from ._bpyutil import require_bpy
from .studio_log import get_logger, step

log = get_logger("hybrid_studio.controller")

DEMO_CHARACTER_PALETTE = {
    "body": "#3E7CB1",
    "head": "#F2C094",
    "limbs": "#2F6690",
    "eyes": "#1A1A1A",
    "accent": "#E4572E",
}


class StudioController:
    def __init__(self, config_path=None):
        self.config = load_config(config_path)
        self.manifest = None

    # ------------------------------------------------------------------
    # Data side (pure Python)
    # ------------------------------------------------------------------
    def create_project(self, projects_root, name):
        self.manifest = project_manager.create_project(
            projects_root, name, config=self.config
        )
        return self.manifest

    def register_demo_character(self):
        """Register the demo 'Hero' character in characters/characters.json."""
        self._require_project()
        reg_path = os.path.join(self.manifest["path"], "characters", "characters.json")
        reg = character_manager.CharacterRegistry()
        if os.path.isfile(reg_path):
            reg = character_manager.load_registry(reg_path)
        if "Hero" not in reg.names():
            reg.add(character_manager.Character(
                name="Hero",
                proportions={"height": 1.9, "head_ratio": 0.30,
                             "shoulder_width": 0.55, "hip_width": 0.36},
                palette=dict(DEMO_CHARACTER_PALETTE),
                asset_paths={"blend": "blend_projects/demo_scene.blend"},
                notes="Original demo character for the Phase 2 integration test.",
            ))
        character_manager.save_registry(reg, reg_path)
        project_manager.register_asset(self.manifest, "characters", "Hero")
        project_manager.save_manifest(self.manifest)
        return reg_path

    def create_demo_story(self):
        """Create a one-scene, one-shot demo story + storyboard manifest."""
        self._require_project()
        story = story_manager.Story("Demo Shot")
        scene = story.add_scene(story_manager.Scene("SC01", "Demo Scene"))
        scene.add_shot(story_manager.Shot(
            "SH010", "Hero bounce and wave", 24, camera="TRACK",
            notes="Benchmark shot: character bounce + wave, GP sparkle, camera move.",
        ))
        story_path = os.path.join(self.manifest["path"], "shots", "story.json")
        story_manager.save_story(story, story_path)
        board_path = os.path.join(self.manifest["path"], "shots", "storyboard.json")
        story_manager.export_storyboard(story, board_path, fps=get_fps(self.config))
        project_manager.register_asset(self.manifest, "shots", "SH010")
        project_manager.save_manifest(self.manifest)
        return {"story": story_path, "storyboard": board_path}

    # ------------------------------------------------------------------
    # Scene side (Blender)
    # ------------------------------------------------------------------
    def build_demo_scene(self, frame_start=1, frame_end=24, preset="preview"):
        """Build + render the demo scene inside Blender.

        Steps: character + environment modeling, rigging, wave/bounce
        animation, Grease Pencil sparkle, camera + tracking move,
        three-point lighting, world, compositor, preview render with
        checkpoint manifest, save .blend. Returns a step-report dict;
        individual step failures are captured with their error text.
        """
        bpy = require_bpy()
        self._require_project()
        from . import (modeling, rigging, animation as anim, grease_pencil,
                       cinematography, lighting_materials, compositing,
                       render_manager)

        report = {"steps": {}, "project": self.manifest["path"]}
        scene = bpy.context.scene

        def run(step_name, fn):
            try:
                result = fn()
                report["steps"][step_name] = {"status": "PASS", "detail": str(result)}
                log.info("[%s] PASS", step_name)
                return result
            except Exception as exc:
                report["steps"][step_name] = {
                    "status": "FAIL", "detail": "%s: %s" % (type(exc).__name__, exc),
                }
                log.error("[%s] FAIL: %s", step_name, exc)
                return None

        step(log, "modeling: character + environment")
        parts = run("modeling_character",
                    lambda: modeling.build_simple_character("Hero", DEMO_CHARACTER_PALETTE))
        run("modeling_environment", lambda: modeling.build_simple_environment("ENV"))

        step(log, "rigging")
        rig_holder = {}
        def _rig():
            rig = rigging.create_simple_armature("HeroRig")
            rigging.attach_character(rig, "Hero")
            rigging.create_placeholder_actions(rig, frames=frame_end)
            rig_holder["rig"] = rig
            return rig.name
        run("rigging", _rig)

        step(log, "animation: bounce + wave (single performance action)")
        def _animate():
            import math
            rig = rig_holder["rig"]
            anim.set_frame_range(scene, frame_start, frame_end)
            scene.frame_set(frame_start)
            total = frame_end - frame_start + 1
            # One action holds BOTH the body bounce (object location) and
            # the arm wave (pose bone), so the preview render shows both.
            action = anim.get_or_create_action(bpy, rig, "Hero_Performance")
            bounce_keys = [
                (frame_start, 0.0),
                (frame_start + total // 4, 0.22),
                (frame_start + total // 2, 0.0),
                (frame_start + (3 * total) // 4, 0.13),
                (frame_end, 0.0),
            ]
            for frame, z in bounce_keys:
                anim.keyframe_transform(rig, frame, location=(0.0, 0.0, z))
            lift = math.radians(115.0)
            sway = math.radians(25.0)
            wave_keys = [
                (frame_start, (0.0, 0.0, 0.0)),
                (frame_start + total // 6, (0.0, 0.0, -lift)),
                (frame_start + total // 2, (sway, 0.0, -lift)),
                (frame_start + (3 * total) // 4, (-sway, 0.0, -lift)),
                (frame_end, (0.0, 0.0, -lift * 0.85)),
            ]
            for frame, rot in wave_keys:
                anim.keyframe_pose_bone(rig, "arm.R", frame, rotation_euler=rot)
            anim.apply_easing(action)
            return "single action 'Hero_Performance': bounce + wave, %d frames" % total
        run("animation", _animate)

        step(log, "grease pencil sparkle")
        run("grease_pencil",
            lambda: grease_pencil.create_sparkle_effect(
                "GP_Sparkle", center=(0.0, 0.0, 2.6)).name)

        step(log, "camera + lighting + world")
        def _camera():
            cam = cinematography.create_camera("Camera", (4.5, -6.0, 2.2), 38.0)
            cinematography.look_at(cam, (0.0, 0.0, 1.1))
            cinematography.animate_tracking_move(
                cam, (4.5, -6.0, 2.2), (2.6, -4.6, 1.7), frame_start, frame_end)
            return cam.name
        run("cinematography", _camera)
        run("lighting", lambda: lighting_materials.three_point_lighting("LGT"))
        run("world", lambda: lighting_materials.set_world_background("#1B2A3A", 0.55).name)

        step(log, "compositing")
        run("compositing", lambda: compositing.setup_compositor(scene)["nodes"])

        step(log, "render: preview with checkpoint manifest")
        render_dir = os.path.join(self.manifest["path"], "renders", "preview")
        def _render():
            manifest = render_manager.render_frames(
                scene, render_dir, frame_start, frame_end, self.config, preset)
            if manifest["missing"]:
                raise RuntimeError("missing frames after render: %s" % manifest["missing"])
            return "%d/%d frames valid" % (manifest["valid_count"],
                                           manifest["expected_count"])
        run("render_preview", _render)
        report["render_dir"] = render_dir

        step(log, "save blend project")
        blend_path = os.path.join(
            self.manifest["path"], "blend_projects", "demo_scene.blend")
        def _save():
            os.makedirs(os.path.dirname(blend_path), exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=blend_path)
            return blend_path
        run("save_blend", _save)
        report["blend_path"] = blend_path

        failed = [s for s, r in report["steps"].items() if r["status"] == "FAIL"]
        report["overall"] = "PASS" if not failed else "FAIL"
        report["failed_steps"] = failed
        return report

    # ------------------------------------------------------------------
    def _require_project(self):
        if self.manifest is None:
            raise RuntimeError(
                "no project loaded: call create_project(projects_root, name) first"
            )
