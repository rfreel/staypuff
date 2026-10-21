# Household World / Staypuff integration

Source lives in `projects/household-world/`; native adapter in `ocean/household/household.h`.
The shared native PufferVis entrypoint `src/puffervis.h` (at the Staypuff repository root) forwards to `projects/household-world/native/puffervis.h`.

## Browser graphics

```sh
cd projects/household-world
python -m pip install -e '.[web,test]'
python -m household.cli serve --port 8765
```

Open `http://127.0.0.1:8765` and select `Live world`. It runs the real deterministic synthetic Python simulator, not an imported RL model.

## Native CPU PufferLib viewer

```sh
# From the Staypuff root:
./build.sh household --cpu
./household
```

If Raylib is unavailable, the standalone C stub checks syntax and executes `puf_render`:

```sh
cd projects/household-world
bash scripts/build_native.sh
```

See `docs/PUFFERVIS.md` for a scene protocol, warehouse example, replay, constraints, and renderer limitations.
