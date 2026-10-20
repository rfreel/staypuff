# Frontier Kombat: 20 synthetic OOD fighting-control games

A corrected and audited implementation of the **20 E01–E20 concepts** supplied in chat, spanning four challenge groups: nonstationary physics, input grammars, partial observation and long-horizon resource games. This now also ships a source-level native Ocean C adapter at `ocean/frontier_kombat/frontier_kombat.h`, not yet verified against the full upstream PufferLib build; it is not a faithful Street Fighter / Mortal Kombat reproduction. It provides the `reset/step/close` interface to facilitate wrapping/adaptation. No policy training is claimed.

## Run

```sh
python -m pip install numpy pytest
python projects/frontier-kombat/frontier_kombat_puffer.py --envs-per-spec 8 --steps 200 --json-out /tmp/frontier-kombat.json
python -m pytest -q projects/frontier-kombat/tests
```

GCC and OpenMP are required. The native engine compiles from the checked-in `frontier_kombat_kernel.c` and loads with `ctypes`. By default, each instance uses one POSIX shared-memory slab containing separate **truly contiguous NumPy** arrays for state, observations `(N,24)`, actions `(N,)`, rewards, terminals and truncations. There are no per-frame Python copies of these I/O buffers. The C loop processes all states directly.

## Audit of original submission

* **Original AoS field views were strided.** `slots['obs']` and `slots['action_p1']` did not have the `C_CONTIGUOUS` property. This version uses separate SoA buffers and checks every C struct field offset, not only total `sizeof`.
* **Original fighter timing and collision contradicted claims:** immediate damage was applied at attack initiation, regardless of startup/active frames or range. This version evaluates hits during active frames and checks reach; still simplified.
* **Original 20 OOD laws were mostly button-selection predicates**, not the listed governing physics or algorithms. This version implements distinctive proxy dynamics across 20 tasks, but does not claim actual Lorentz relativity, homotopy invariants, cryptographic compilers or GGPO rollback.
* **Original RNG was regenerated from per-step formulas**, and parts of per-episode return were overwritten on reset. This version uses a mutable seeded RNG and exposes `last_episode_return` separately. Ongoing `cumulative` is still reset at new episodes; full-run returns require aggregating rewards outside the state.
* **Original adaptive policy used hidden internal state and hard-coded rules.** The supplied rule-informed heuristic has been retained only as a benchmark; it is explicitly **not learned**. Meaningful OOD evaluation requires held-out parameters/seeds and stronger independent baselines.
* OpenMP speed is a **measured local throughput**, not a promise of 1M/second on another CPU or a measure of actual language-model coding operations.

## Remaining validation work

We still need statistical uncertainty intervals, behavior-specific tests for every OOD mechanism, real two-agent self-play, randomized domain parameters, adversarial exploit checks, calibrated performance, full upstream build/trainer compatibility checks for the included Ocean wrapper. The 20 tasks are experimental games, not independently established elite benchmarks.

## Native Ocean adapter

The same checked-in C kernel is included by `ocean/frontier_kombat/frontier_kombat.h` with a PufferLib 5.0-shaped one-agent environment. Each vectorized environment samples an E01–E20 task on reset; the Python shared-memory wrapper can pin a particular task and compare ID/OOD modes. Use `./build.sh frontier_kombat --cpu` in a complete Staypuff checkout. No CUDA training or full compiler integration is claimed by the local stub test.
