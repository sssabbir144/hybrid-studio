# MEMORY BANK — Ss Animation Project

_Living context for every agent/developer session on this project. Owner: Sabbir Hossin (sssabbir144). Created 2026-11-06 (Step 2). Keep this file updated whenever structure, API rules, or roadmap change._

## 1. Project structure (4 repositories)

| Repo | Purpose | Stack |
|---|---|---|
| `sssabbir144.github.io` | Portfolio website + **Ss Animation Studio** web app (in `studio/`) | Static HTML/CSS/JS, GitHub Pages |
| `hybrid-studio` | **Hybrid Animation Studio** — Blender-based 2D/3D production toolkit | Python (`bpy`), Blender |
| `hybrid-studio-fixes` | Blender **5.2.3** API-compatibility fixes for the toolkit, kept separate from the original codebase | Python (`bpy`) |
| `sssabbir144` | GitHub profile README | Markdown |

**Website / Studio (`sssabbir144.github.io`)**
- Root: service pages (`2d-animation`, `3d-animation`, `ghibli-style-animation`, `stick-figure-animation`, `kids-youtube-animation`, `hire-a-freelance-animator`, `animation-process`), coloring pages + `bedtime-stories`, `sitemap.xml`, `portfolio-manifest.md`, shared CSS (`styles.css`, `site-*.css`), `assets/`.
- `studio/`: Ss Animation Studio — `index.html`, `studio.js` (~171 KB, the editor), `studio.css`, `sw.js` (service worker), PWA manifest + icons, logo assets. Phases: P1 live, P2 final 2026-11-04, P3 in progress (Layers, pose keyframes/IK, motion path + easing, Camera track). Later phases open only on the owner's word.

**Hybrid toolkit (`hybrid-studio`)**
- Package `hybrid_studio/`: `story_manager`, `character_manager`, `rigging`, `modeling`, `grease_pencil`, `animation`, `cinematography`, `lighting_materials`, `compositing`, `render_manager`, `audio_video`, `project_manager`, `quality_control`, `controller`, `config`, `_bpyutil` (shared bpy helpers), `studio_log`.
- `studio_bootstrap.py` rebuilds the full project structure anywhere; `studio_config.json` holds config; `scripts/integration_test.py`; `tests/`.

**Fixes (`hybrid-studio-fixes`)**
- Corrected `animation.py`, `compositing.py`, `render_manager.py`, plus `api_diagnostic.py` (headless probe of the real 5.2 API surface), `benchmark/`, `qa/`.

## 2. Blender 5.2.3 API rules (hard-won — follow in ALL new code)

1. **Layered Actions — never touch `action.fcurves` directly.** Actions are layered: traverse `action.layers[i].strips[j]`. On 5.2.3, `strip.channelbag` is a **method** that must be called with an Action Slot, and `strip.channelbags` is the collection. Correct order: (a) `strip.channelbags` collection, (b) `channelbag(slot)` per Action Slot, (c) legacy plain-property / direct `action.fcurves` fallback. If an action has layered strips but no fcurves are reachable, **log a warning — never fail silently**. (Old code died with `AttributeError: 'bpy_func' object has no attribute 'fcurves'`.)
2. **`ImageFormatSettings` uses `file_format`, not `format`.** The pre-2.8 attribute `format` was renamed in Blender ≥ 2.8 (incl. 5.x). Always set it through a helper that tries `file_format` → `format` → any introspected non-callable attribute whose name contains `format`, and raises a clear `RuntimeError` listing the available attributes if none exists.
3. **Compositor location is not guaranteed.** It may live on `scene.node_tree` (legacy) or on a `CompositorNodeTree` node group (`bpy.data.node_groups.new("Compositing", "CompositorNodeTree")`). In 5.2.3 background mode `CompositorNodeComposite` can be **undefined** — probe every `nodes.new()` call and fall back (Composite → `NodeGroupOutput`) instead of assuming a node type exists.
4. **General defensive pattern (house style):** probe before use (`getattr` + callable checks), order fallbacks new-API → legacy, wrap probes in try/except so diagnostics always run to completion, and when an API surface is unknown, run `api_diagnostic.py` **inside Blender headless first** (`blender -b --python api_diagnostic.py`) and read the real structure before writing the fix.
5. **Compatibility pledge:** every new module or edit is written **Blender 5.2.3-compatible first**, using the patterns above — no bare direct access to version-sensitive attributes.

## 3. Roadmap — features to add next (owner-approved direction)

- Merge `hybrid-studio-fixes` modules back into `hybrid-studio` once validated, so there is one codebase.
- Studio web app: finish P3 → P4 library panels → P5 lip-sync / Talk / walk + moods (each phase opens only on the owner's word).
- First full hybrid 2D+3D short produced end-to-end with the toolkit (post-benchmark).
- Automation: CI compatibility gate + runtime version guard (see §4 — prepared, not yet applied).

## 4. Prepared suggestions (automation + fewer bugs) — NOT yet applied

### Suggestion 1 — CI compatibility gate (GitHub Actions)
Runs the headless diagnostic + integration test on every push/PR touching the toolkit, so a Blender API break fails the build before it reaches production.

```yaml
# .github/workflows/blender-compat.yml  (place in hybrid-studio)
name: blender-compat
on:
  push: { paths: ["hybrid_studio/**", "scripts/**"] }
  pull_request: { paths: ["hybrid_studio/**", "scripts/**"] }
jobs:
  compat:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install Blender 5.2.3 (pinned)
        run: |
          curl -L -o blender.tar.xz https://download.blender.org/release/Blender5.2/blender-5.2.3-linux-x64.tar.xz
          tar -xf blender.tar.xz && echo "$PWD/blender-5.2.3-linux-x64" >> $GITHUB_PATH
      - name: API diagnostic (real 5.2 surface)
        run: blender -b --python ../hybrid-studio-fixes/api_diagnostic.py
      - name: Integration test
        run: blender -b --python scripts/integration_test.py
```

### Suggestion 2 — Runtime version guard + one compat layer
Pin the tested Blender version in `studio_config.json` and fail early with a clear message on an untested build; route ALL version-sensitive `bpy` access through `hybrid_studio/_bpyutil.py` shims (new-API → legacy fallback), so a future API change is fixed in exactly one file.

```python
# hybrid_studio/__init__.py — version guard (skeleton)
import bpy

TESTED_BLENDER = (5, 2, 3)  # keep in sync with studio_config.json

def check_blender_version():
    v = bpy.app.version
    if v[:2] != TESTED_BLENDER[:2]:
        raise RuntimeError(
            f"Hybrid Studio is tested on Blender {TESTED_BLENDER}; "
            f"running build is {v}. Run api_diagnostic.py before use."
        )
```
