"""Story and storyboard management.

Data model: Story -> Scene -> Shot. JSON save/load with strict validation,
plus a storyboard manifest export that computes frame ranges from the fps.
Pure Python (no Blender required).
"""

import json
import os

from .studio_log import get_logger

log = get_logger("hybrid_studio.story_manager")

CAMERA_MOVES = (
    "STATIC", "PUSH_IN", "PULL_OUT", "PAN", "TRACK", "ORBIT", "CRANE", "HANDHELD",
)


def _require_str(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be a non-empty string" % field)
    return value.strip()


class Shot:
    def __init__(self, shot_id, name, duration_frames, camera="STATIC", notes=""):
        self.shot_id = _require_str(shot_id, "shot_id")
        self.name = _require_str(name, "shot name")
        if not isinstance(duration_frames, int) or duration_frames <= 0:
            raise ValueError(
                "shot %r: duration_frames must be a positive integer, got %r"
                % (shot_id, duration_frames)
            )
        self.duration_frames = duration_frames
        camera = (camera or "STATIC").upper()
        if camera not in CAMERA_MOVES:
            raise ValueError(
                "shot %r: unknown camera move %r (allowed: %s)"
                % (shot_id, camera, ", ".join(CAMERA_MOVES))
            )
        self.camera = camera
        self.notes = notes or ""

    def to_dict(self):
        return {
            "shot_id": self.shot_id,
            "name": self.name,
            "duration_frames": self.duration_frames,
            "camera": self.camera,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("shot entry must be an object, got %r" % type(data).__name__)
        return cls(
            data.get("shot_id"), data.get("name"), data.get("duration_frames"),
            data.get("camera", "STATIC"), data.get("notes", ""),
        )


class Scene:
    def __init__(self, scene_id, name, shots=None):
        self.scene_id = _require_str(scene_id, "scene_id")
        self.name = _require_str(name, "scene name")
        self.shots = list(shots or [])

    def add_shot(self, shot):
        if not isinstance(shot, Shot):
            raise ValueError("add_shot expects a Shot instance")
        if any(s.shot_id == shot.shot_id for s in self.shots):
            raise ValueError("duplicate shot_id %r in scene %r" % (shot.shot_id, self.scene_id))
        self.shots.append(shot)
        return shot

    @property
    def duration_frames(self):
        return sum(s.duration_frames for s in self.shots)

    def to_dict(self):
        return {
            "scene_id": self.scene_id,
            "name": self.name,
            "shots": [s.to_dict() for s in self.shots],
        }

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("scene entry must be an object")
        scene = cls(data.get("scene_id"), data.get("name"))
        for raw in data.get("shots", []):
            scene.add_shot(Shot.from_dict(raw))
        return scene


class Story:
    def __init__(self, title, scenes=None):
        self.title = _require_str(title, "story title")
        self.scenes = list(scenes or [])

    def add_scene(self, scene):
        if not isinstance(scene, Scene):
            raise ValueError("add_scene expects a Scene instance")
        if any(s.scene_id == scene.scene_id for s in self.scenes):
            raise ValueError("duplicate scene_id %r" % scene.scene_id)
        self.scenes.append(scene)
        return scene

    @property
    def duration_frames(self):
        return sum(s.duration_frames for s in self.scenes)

    def duration_seconds(self, fps=24):
        if not isinstance(fps, int) or fps <= 0:
            raise ValueError("fps must be a positive integer")
        return self.duration_frames / float(fps)

    def to_dict(self):
        return {"title": self.title, "scenes": [s.to_dict() for s in self.scenes]}

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict):
            raise ValueError("story data must be an object")
        story = cls(data.get("title"))
        for raw in data.get("scenes", []):
            story.add_scene(Scene.from_dict(raw))
        return story


def save_story(story, path):
    if not isinstance(story, Story):
        raise ValueError("save_story expects a Story instance")
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(story.to_dict(), fh, indent=2, sort_keys=True)
    log.info("Saved story '%s' (%d frames) to %s", story.title, story.duration_frames, path)
    return path


def load_story(path):
    if not os.path.isfile(path):
        raise FileNotFoundError("story file not found: %s" % path)
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    story = Story.from_dict(data)
    log.info("Loaded story '%s' (%d scenes)", story.title, len(story.scenes))
    return story


def storyboard_manifest(story, fps=24):
    """Flat storyboard rows with computed start/end frames (1-based)."""
    if not isinstance(story, Story):
        raise ValueError("storyboard_manifest expects a Story instance")
    rows = []
    cursor = 1
    for scene in story.scenes:
        for shot in scene.shots:
            end = cursor + shot.duration_frames - 1
            rows.append({
                "scene_id": scene.scene_id,
                "scene_name": scene.name,
                "shot_id": shot.shot_id,
                "shot_name": shot.name,
                "camera": shot.camera,
                "start_frame": cursor,
                "end_frame": end,
                "duration_frames": shot.duration_frames,
                "duration_seconds": round(shot.duration_frames / float(fps), 3),
                "notes": shot.notes,
            })
            cursor = end + 1
    return rows


def export_storyboard(story, path, fps=24):
    rows = storyboard_manifest(story, fps=fps)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"story": story.title, "fps": fps, "shots": rows}, fh, indent=2)
    log.info("Exported storyboard manifest (%d shots) to %s", len(rows), path)
    return path
