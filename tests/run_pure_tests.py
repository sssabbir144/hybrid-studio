"""Pure-Python tests for the hybrid studio (NO Blender required).

Run:  python3 tests/run_pure_tests.py
Prints PASS/FAIL per test and exits non-zero if any test fails.
"""

import json
import os
import sys
import tempfile

STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if STUDIO_ROOT not in sys.path:
    sys.path.insert(0, STUDIO_ROOT)

from hybrid_studio import (  # noqa: E402
    audio_video, character_manager, config, project_manager, quality_control,
    render_manager, story_manager,
)
from hybrid_studio.controller import StudioController  # noqa: E402

PNG_BYTES = render_manager.PNG_SIGNATURE + b"\x00" * 200


def _write_png(path):
    with open(path, "wb") as fh:
        fh.write(PNG_BYTES)


# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------

def test_config_loads_and_validates():
    cfg = config.load_config()
    assert config.get_fps(cfg) == 24
    for name in ("preview", "production", "final"):
        preset = config.get_preset(cfg, name)
        assert preset["width"] > 0 and preset["height"] > 0
    preview = config.get_preset(cfg, "preview")
    assert (preview["width"], preview["height"]) == (320, 180)
    final = config.get_preset(cfg, "final")
    assert (final["width"], final["height"]) == (1920, 1080)


def test_config_rejects_eevee_next_and_bad_fps():
    bad = json.loads(json.dumps(config.DEFAULT_CONFIG))
    bad["resolution_presets"]["preview"]["engine"] = "BLENDER_EEVEE_NEXT"
    try:
        config.validate_config(bad)
    except config.ConfigError:
        pass
    else:
        raise AssertionError("BLENDER_EEVEE_NEXT was not rejected")
    bad2 = json.loads(json.dumps(config.DEFAULT_CONFIG))
    bad2["fps"] = 0
    try:
        config.validate_config(bad2)
    except config.ConfigError:
        return
    raise AssertionError("fps=0 was not rejected")


# ----------------------------------------------------------------------
# Project manager
# ----------------------------------------------------------------------

def test_project_structure_in_temp_dir():
    with tempfile.TemporaryDirectory() as tmp:
        manifest = project_manager.create_project(tmp, "demo proj")
        for sub in project_manager.PROJECT_DIRS:
            assert os.path.isdir(os.path.join(manifest["path"], sub)), sub
        assert os.path.isfile(manifest["manifest_file"])
        # Idempotent rerun returns the same manifest.
        again = project_manager.create_project(tmp, "demo proj")
        assert again["created_utc"] == manifest["created_utc"]
        delivery = project_manager.delivery_package_list(manifest)
        assert delivery and all(item["exists"] for item in delivery)
    try:
        project_manager.create_project(tmp, "bad/name")
    except ValueError:
        return
    raise AssertionError("path separator in project name was not rejected")


# ----------------------------------------------------------------------
# Story manager
# ----------------------------------------------------------------------

def test_story_roundtrip_and_manifest():
    story = story_manager.Story("Test Film")
    scene = story.add_scene(story_manager.Scene("SC01", "Opening"))
    scene.add_shot(story_manager.Shot("SH010", "Wide", 24, camera="PUSH_IN"))
    scene.add_shot(story_manager.Shot("SH020", "Close", 12))
    assert story.duration_frames == 36
    rows = story_manager.storyboard_manifest(story, fps=24)
    assert rows[0]["start_frame"] == 1 and rows[0]["end_frame"] == 24
    assert rows[1]["start_frame"] == 25 and rows[1]["end_frame"] == 36
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "story.json")
        story_manager.save_story(story, path)
        loaded = story_manager.load_story(path)
        assert loaded.title == "Test Film"
        assert loaded.duration_frames == 36


def test_story_validation_errors():
    for make in (
        lambda: story_manager.Shot("S1", "x", 0),
        lambda: story_manager.Shot("S1", "x", 10, camera="FLY"),
        lambda: story_manager.Shot("", "x", 10),
    ):
        try:
            make()
        except ValueError:
            continue
        raise AssertionError("invalid shot was accepted: %r" % (make,))


# ----------------------------------------------------------------------
# Character manager
# ----------------------------------------------------------------------

def test_character_registry_roundtrip():
    reg = character_manager.CharacterRegistry()
    reg.add(character_manager.Character(
        "Hero", palette={"body": "#3E7CB1"}, proportions={"height": 1.9}))
    assert reg.names() == ["Hero"]
    assert character_manager.hex_to_rgba("#FF0000") == (1.0, 0.0, 0.0, 1.0)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "chars.json")
        character_manager.save_registry(reg, path)
        loaded = character_manager.load_registry(path)
        assert loaded.get("Hero").palette["body"] == "#3E7CB1"
    for make in (
        lambda: character_manager.Character("Bad", palette={"body": "blue"}),
        lambda: character_manager.Character("Bad", proportions={"height": -1}),
        lambda: reg.add(character_manager.Character("Hero")),
    ):
        try:
            make()
        except (ValueError, KeyError):
            continue
        raise AssertionError("invalid character data was accepted")


# ----------------------------------------------------------------------
# Render manager (pure logic)
# ----------------------------------------------------------------------

def test_missing_frame_detection():
    with tempfile.TemporaryDirectory() as tmp:
        for frame in (1, 2, 4):
            _write_png(os.path.join(tmp, render_manager.frame_filename(frame)))
        missing = render_manager.find_missing_frames(tmp, 1, 4)
        assert missing == [3], missing
        bad = os.path.join(tmp, render_manager.frame_filename(2))
        with open(bad, "wb") as fh:
            fh.write(b"not a png")
        assert render_manager.find_missing_frames(tmp, 1, 4) == [2, 3]


def test_checkpoint_manifest_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        for frame in (1, 2, 3):
            _write_png(os.path.join(tmp, render_manager.frame_filename(frame)))
        manifest = render_manager.write_checkpoint_manifest(tmp, 1, 3, "preview")
        assert manifest["valid_count"] == 3 and manifest["missing"] == []
        loaded = render_manager.load_checkpoint_manifest(tmp)
        assert loaded["expected_count"] == 3


def test_engine_verification_outside_blender():
    assert render_manager.verify_engine("BLENDER_EEVEE") == "BLENDER_EEVEE"
    try:
        render_manager.verify_engine("BLENDER_EEVEE_NEXT")
    except render_manager.RenderConfigError:
        pass
    else:
        raise AssertionError("BLENDER_EEVEE_NEXT was not rejected")
    devices = render_manager.detect_devices()
    assert devices["bpy"] is False and devices["gpu_available"] is False


# ----------------------------------------------------------------------
# Audio / video (pure)
# ----------------------------------------------------------------------

def test_ffmpeg_command_builder():
    cmd = audio_video.build_ffmpeg_command(
        "renders/frame_%04d.png", "out/final.mp4", fps=24,
        audio_path="audio/music.wav")
    assert cmd.startswith("ffmpeg")
    assert "frame_%04d.png" in cmd and "libx264" in cmd and "final.mp4" in cmd
    assert "music.wav" in cmd
    try:
        audio_video.build_ffmpeg_command("renders/frame.png", "x.mp4")
    except ValueError:
        return
    raise AssertionError("pattern without %04d was accepted")


def test_sequence_plan():
    plan = audio_video.build_sequence_plan(1, 24, fps=24, audio_files={"music": "m.wav"})
    assert plan["duration_frames"] == 24 and plan["duration_seconds"] == 1.0
    slots = {s["slot"]: s["type"] for s in plan["audio_strips"]}
    assert slots == {"music": "SOUND", "dialogue": "EMPTY_SLOT", "sfx": "EMPTY_SLOT"}


# ----------------------------------------------------------------------
# Quality control (pure) + controller data side
# ----------------------------------------------------------------------

def test_qc_pure_checks_and_report():
    with tempfile.TemporaryDirectory() as tmp:
        manifest = project_manager.create_project(tmp, "qcproj")
        render_dir = os.path.join(manifest["path"], "renders", "preview")
        os.makedirs(render_dir, exist_ok=True)
        for frame in (1, 2):
            _write_png(os.path.join(render_dir, render_manager.frame_filename(frame)))
        render_manager.write_checkpoint_manifest(render_dir, 1, 2, "preview")
        report = quality_control.run_qc(manifest["path"], render_dir=render_dir)
        assert report["overall"] == "PASS", report
        out = quality_control.write_qc_report(report, os.path.join(manifest["path"], "reports"))
        assert os.path.isfile(out["json"]) and os.path.isfile(out["markdown"])
        blend_check = quality_control.check_blend_opens("whatever.blend")
        assert blend_check[0]["status"] == "SKIP"  # no bpy in the test env


def test_controller_data_side():
    with tempfile.TemporaryDirectory() as tmp:
        controller = StudioController()
        controller.create_project(tmp, "ctrlproj")
        reg_path = controller.register_demo_character()
        assert os.path.isfile(reg_path)
        paths = controller.create_demo_story()
        assert os.path.isfile(paths["story"]) and os.path.isfile(paths["storyboard"])
        story = story_manager.load_story(paths["story"])
        assert story.duration_frames == 24


TESTS = [
    ("config_loads_and_validates", test_config_loads_and_validates),
    ("config_rejects_eevee_next_and_bad_fps", test_config_rejects_eevee_next_and_bad_fps),
    ("project_structure_in_temp_dir", test_project_structure_in_temp_dir),
    ("story_roundtrip_and_manifest", test_story_roundtrip_and_manifest),
    ("story_validation_errors", test_story_validation_errors),
    ("character_registry_roundtrip", test_character_registry_roundtrip),
    ("missing_frame_detection", test_missing_frame_detection),
    ("checkpoint_manifest_roundtrip", test_checkpoint_manifest_roundtrip),
    ("engine_verification_outside_blender", test_engine_verification_outside_blender),
    ("ffmpeg_command_builder", test_ffmpeg_command_builder),
    ("sequence_plan", test_sequence_plan),
    ("qc_pure_checks_and_report", test_qc_pure_checks_and_report),
    ("controller_data_side", test_controller_data_side),
]


def main():
    failures = 0
    for name, fn in TESTS:
        try:
            fn()
            print("PASS %s" % name)
        except Exception as exc:
            failures += 1
            print("FAIL %s -> %s: %s" % (name, type(exc).__name__, exc))
    print("-" * 60)
    print("%d/%d tests passed" % (len(TESTS) - failures, len(TESTS)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
