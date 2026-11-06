# Assets — Prisma 3D pipeline

How 3D models made in **Prisma 3D** (phone app) get into this studio.

## Folders

| Folder | What goes there |
|---|---|
| `prisma3d/incoming/` | Raw exports straight from the phone: `.obj` / `.fbx` (plus `.glb` / `.gltf`). Drop files here untouched. |
| `prisma3d/processed/` | Cleaned results: one `.blend` per asset, saved by the import CLI after normalisation. |
| `prisma3d/textures/` | Texture images (`.png` / `.jpg`) that belong to the models, kept with matching base names. |

## Naming

Use the model's plain name everywhere: `tree.obj`, `tree.fbx`,
`tree.png` (texture), `tree.blend` (processed). No spaces, no dates —
the pipeline finds textures by base name.

## Importing (Blender 5.2.3)

From the repo root:

```bash
# everything waiting in the inbox, saved as one scene
blender -b --python scripts/import_prisma3d.py -- \
  --save assets/prisma3d/processed/imported.blend

# a single file, rescaled to 1.8 m tall
blender -b --python scripts/import_prisma3d.py -- \
  --target-height 1.8 assets/prisma3d/incoming/hero.fbx
```

Or from Python inside Blender:

```python
from hybrid_studio import asset_pipeline
reports = asset_pipeline.import_incoming(bpy)          # whole inbox
report = asset_pipeline.import_asset(bpy, "path/to/model.obj",
                                     target_height=1.8)
```

Imported objects land in the `Prisma3D_Imports` collection, are rested
on Z=0 (scale applied first), and each import returns a report with the
object names, mesh count, materials and final dimensions in metres.

## Large files / Git LFS

`.obj`, `.fbx`, `.glb` and `.blend` files are tracked with **Git LFS**
(see `.gitattributes`). Anyone cloning the repo to work with the actual
models needs Git LFS installed (`git lfs install`) before pulling.
