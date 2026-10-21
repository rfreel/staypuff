# PufferVis v1 · Rendering Ocean environments without training-time graphics

PufferVis is a passive visualization layer for **stateful games and RL environments**. It does not define a reward, agent observation, physical transition, or training control. The authoritative simulator remains the only owner of state changes.

## What is implemented

- `household/scene.py` transforms a serializable state snapshot into `puffervis.scene.v1` with stable entities, zones, semantic flow links, inspection metadata, and source/provenance labels.
- `schemas/puffervis.scene.v1.json` defines the wire format. `examples/puffervis_warehouse.json` demonstrates another environment producing the same protocol without any household-specific fields.
- `web/puffervis.js` is a standalone Canvas 2D isometric renderer. It accepts the scene protocol alone, uses no external assets or dependencies, and implements camera pan/zoom, layer filters, entity picking/inspection, readable HUD, and procedural animated effects.
- `web/index.html`, `web/app.js`, and `web/style.css` embed the viewer as the primary dashboard view, with automatic daily stepping and an explicit pause control. All existing analytics tabs remain available.
- `native/puffervis.h` provides header-only Raylib-compatible primitives for the native Ocean viewer. Installed Staypuff entrypoint: `src/puffervis.h` forwards to the vendored implementation; `ocean/household/household.h` calls the primitives in `puf_render` only.
- `household/replay.py` embeds both the renderer and all state/scene snapshots into a portable, standalone HTML replay. This **replays recorded states**; it does not run policy actions on the user's machine.

## Get graphics running

```bash
cd projects/household-world
python -m pip install -e '.[web]'
python -m household.cli serve --port 8765
# Open http://127.0.0.1:8765 and select Live world
```

Offline, without any backend or external libraries:

```bash
python -m household.cli preview --help  # command help
python -m household.replay             # Python importable generator; see below
python - <<'PY'
from household.replay import build_preview
print(build_preview('artifacts/puffervis-preview.html', days=21))
PY
# Open artifacts/puffervis-preview.html in a normal browser
```

Native `Ocean` viewer uses the installed `src/puffervis.h` shim:

```bash
# Run at the root of staypuff; requires upstream Raylib build dependencies.
./build.sh household --cpu
./household
```

The vendored minimal-build test can run without Raylib:

```bash
cd projects/household-world
bash scripts/build_native.sh
python -m pytest -q
```

## Emit a scene from an unrelated game

A visual adapter should return a declarative scene, not pixel output. For example:

```json
{
  "schema": "puffervis.scene.v1",
  "scene_id": "warehouse.example",
  "revision": 0,
  "provenance": "synthetic_game_state",
  "layout_provenance": "authored_layout",
  "camera": {"projection": "isometric", "target": [4, 0, 4], "zoom": 1},
  "world": {"width": 8, "depth": 8},
  "zones": [{"id":"floor","label":"FLOOR","x":0,"z":0,"width":8,"depth":8,"material":"slate"}],
  "entities": [{"id":"agent:1","visual":"robot","position":[3,0,3],"label":"Agent 1","facts":{"health":100},"signal":"active"}],
  "connections": [],
  "hud": {"score": 0}
}
```

Initialize `new PufferVis.Renderer(canvas)` and call `.setScene(scene)`. Entity IDs must remain stable between state transitions so inspection persists. Unknown visual types render as fallback boxes rather than crashing. Images, sprites, and graphical materials can be added later behind the same protocol without modifying the RL algorithm.

## Five critical invariants

1. **State ownership:** Graphics do not execute Beads, spend money, control appliances, or modify a Python/C simulator state.
2. **No privileged information:** The observation array seen by the RL policy is unchanged. Rendering may expose privileged simulator state to the human observer, but never feed it back to the policy.
3. **No synthetic movement inference:** The scene's geometry is illustrative. It depicts *stations and state*; it does not claim simulated people physically walked to those locations.
4. **No training overhead:** In headless runs, the Canvas viewer is never initialized; native PufferVis functions are invoked only from `puf_render`, not `puf_step`.
5. **Reproducibility:** `project_household_scene` is deterministic and pure with respect to the world state and PRNG; replay snapshots include scenes at each recorded day.

## Known limitations

- Isometric Canvas drawing is 2.5D (not a full physically lit 3D engine). Some objects are procedural primitives, and the geometry is a conceptual stage.
- Household Python simulation and native C Ocean adapter remain **different fidelity models**. The graphical native adapter does not make their state transitions equivalent.
- PufferLib's full Raylib/WASM link and GPU trainer were not available for independent verification in the local runtime. A standalone C stub compiles, executes, and exercises render code.
- The browser viewer uses discrete daily snapshots, not continuous motion-capture trajectories. Food steam and dashed flow particles are **illustrative effects**, never physical data.
- No live retailer pricing, purchasing, personalized medical guidance, validated food-safety solver, training-dashboard websocket stream, or general GLTF/texture pipeline is included.
- `puffervis.scene.v1` is a proposed project-local protocol, not an upstream PufferLib feature.

## Tests and evidence

`tests/test_scene.py` verifies purity, stable IDs, deterministic projections, linked entities, explicit provenance, read-only observation behavior, API consistency, generic scene compatibility, and asset existence. `native/test_ocean.c` exercises `puf_render` with a Raylib API stub. End-to-end screenshots were generated with headless Chromium using Playwright from the self-contained offline replay (the runtime's managed browser blocks direct URL navigation by policy). Mobile was tested at 390×844 CSS pixels and desktop at 1440×940; mobile horizontal overflow was absent after layout fixes.
