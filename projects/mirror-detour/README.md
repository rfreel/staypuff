# Mirror detour

A small PufferLib 5.0 native environment for testing temporary symmetry-breaking
reward shaping. The implementation follows the repository's SKILL_ISSUES.md.
It does not claim endorsement by Joseph Suarez, a new RL algorithm, or evidence
of nonlinear amplification. Read PLAN.md for the prewalk and EVIDENCE.md for results.

The 11x11 grid has a centered rectangular obstacle (y=3..7), goal (5,0), and
paired starts (4,10)/(6,10). Actions are left/right/up/down. Success pays 1;
timeout at 80 transitions pays 0. Observations are normalized x, y, episode
clock, route, obstacle half-width, and start radius. Left/right reflection maps
x to 10-x, swaps actions 0/1, and negates route. Up/down are unchanged.

The first crossing to y<3 records route=-1 or +1 and emits the optional odd
feature exactly once. This deliberately replaces an every-step horizontal
bonus: repeated wall-pushing and route loops cannot farm the shaping event.

| Config | Meaning |
| --- | --- |
| `mode=0` | Baseline |
| `mode=1` | Odd route-choice feature |
| `mode=2` | Fixed hashed state/action perturbation at the same event |
| `mode=3` | Goal Manhattan-distance potential difference |
| `mode=4` | Equal positive bonus for either first route crossing |
| `sign=-1,0,1` | Reverse, disable, or preserve feature |
| `schedule=0,1` | Linearly decaying or persistent coefficient |
| `strength` | Nonnegative shaping scale |
| `anneal_steps` | Transitions **per instance**, not vector-wide steps |
| `step_offset` | Explicit initial per-instance schedule position |
| `evaluate=1` | Disable every shaping mode |
| `half_width` | Obstacle half-width, 1..3 |
| `start_radius` | Paired start offset from center, 0..3 |

`perf`/`score` always count original-task success. `length`, `left`, `right`,
`bonus` are separate episode aggregates; `n` is last as required by the trainer.
The shaped reward is assigned to `env->agents[0].rewards[0]` every step. Terminal
reward and terminal flag survive autoreset; observations describe the next start.
The route feature does not consume RNG. Starts alternate in balanced pairs.

Mode 2 is a generic perturbation control, not guaranteed orthogonal to the odd
feature on this finite task. Mode 3's time-varying multiplier does NOT carry the
usual stationary potential-based policy-invariance guarantee. Persistent mode 3
has the standard gamma*Phi(next)-Phi(current) form with terminal Phi=0, provided
its shaping_gamma matches the learner's discount.

## Build and verify

From repository root, with the normal PufferLib build dependencies installed:

```sh
./build.sh mirror_detour mirror_view --cpu --debug
bash projects/mirror-detour/verify.sh
./mirror_view --headless --eval_episodes=10 --env.evaluate=1
MIRROR_CPU_BINARY=./mirror_view python3 projects/mirror-detour/test_runners.py -v
```

Tests use the real src/pufferenv.h and raylib headers, not an API stub. The
headless test linker discards unused renderer functions; the runtime smoke uses
the actual src/puffercpu.c and raylib library. On a ptrace-restricted host only,
LeakSanitizer may need `ASAN_OPTIONS=detect_leaks=0`; ASan and UBSan remain enabled.
CI uses the normal sanitizer settings. The runner tests cover partial-file and
late-write collisions, executable identity, and retained evaluation metrics.
On CUDA hardware, set `MIRROR_CUDA_BINARY=./mirror_puffer` for the additional
training-initialization regression: it compares initial self-play checkpoint
bytes with supplied weights, with zero rollouts or optimizer updates. That test
is skipped explicitly on CPU-only CI; it is not a trained-policy result.

## Executed CPU diagnostic

```sh
python3 projects/mirror-detour/run.py --binary /tmp/staypuff-mirror-detour/diagnostic --output /tmp/mirror-original.json
```

This is tabular Q-learning over the actual C environment, NOT PuffeRL/PPO.
The table includes position, route, and episode time; it is deliberately a
simple diagnostic. Alpha=.3, gamma=.99, epsilon=.2, random tie-breaking.

The script freezes a manifest, runs four candidates per family on seeds 1..4,
selects by training-start curve success then length, and confirms on seeds
101..108. Selection never reads held-out-start results. Evaluation has shaping
disabled; starts (3,10)/(7,10) are unseen as resets, but their cells can be visited
in training. This tests reset-distribution transfer, not unseen geometry.
Each evaluation uses 64 episodes; the eight seeds, not the repeated episodes,
are the independent confirmation units. The initial hand-run smoke used seed 1
and is not independent confirmation evidence.

New manifests record the resolved diagnostic executable path and SHA-256 as
well as source hashes. This identifies the supplied binary; it does not certify
that it was built from those sources. Interrupted runs retain their manifest or
selection file, and retries require a fresh output path. Past evidence is unchanged.

Every family receives the same candidate count and training-step budget.
Baseline candidates and persistent duration candidates intentionally duplicate
behavior. Timing includes periodic evaluation; total wall time includes all
runs and process overhead. These subsecond runs are not reliable performance
benchmarks. General algorithm hyperparameters are fixed, not competitively tuned.

## Native PuffeRL experiment

Requires CUDA training hardware. CPU evaluation alone cannot train PuffeRL 5.0.

```sh
./build.sh mirror_detour mirror_puffer
./build.sh mirror_detour mirror_view --cpu
python3 projects/mirror-detour/native.py
python3 projects/mirror-detour/native.py --execute --output logs/mirror-native-seed101
```

The first Python command prints the eight-arm plan without training. Execution
uses isolated checkpoint/log paths, verifies that evaluation loaded trained
weights, evaluates both start sets with shaping disabled, and records raw logs.
Use a fresh output directory and repeat with different `--seed` values. Use
`--strength` and `--anneal-fraction` for separately budgeted discovery sweeps;
do not treat the CPU diagnostic's selected parameters as PPO-tuned parameters.
The native script is a fixed-arm runner, not an automatic discovery selector.
It has been syntax/plan checked here; CUDA execution remains unmeasured.

The annealing clock is local to each environment and survives episode reset.
At a complete synchronous rollout boundary, global steps / total_agents gives
per-instance progress. Native checkpoints save weights, NOT this clock, optimizer
state, RNG, or episode state. Training loads `base.load_model_path` into the
trainable policy before the first rollout or initial self-play checkpoint. For
manual weights-only continuation, explicitly supply
`--env.step_offset=...` and the same original `--env.anneal_steps=...` with
`--base.load_model_path=...`. This restores the reward phase only, not an exact
training resume: optimizer, RNG, learning-rate schedule, episode state and
training/checkpoint step counters restart. `train.total_timesteps` is the new
run budget, not a cumulative target; use a fresh run ID/output path. The native runner starts fresh and uses async=0; it does not
pretend to restore a complete training checkpoint.

## Interpretation

Orientation selection alone is expected. An improvement needs original-task
results after removal, comparisons to both signs and simpler shaping controls,
new seeds, and comparable tuning/compute budgets. A successful toy diagnostic
cannot establish PPO transfer or broad RL usefulness.

## Equal-route follow-up

```sh
python3 projects/mirror-detour/run.py --study even-control --binary /tmp/staypuff-mirror-detour/diagnostic --output /tmp/mirror-even.json
```

Existing evidence files are never overwritten. The original study is retained
with its original source hashes and is reproducible at commit
38c166955545c5da9c1320581138213cdf94b094. The follow-up compares baseline, both
odd signs, the hash perturbation, and an equal-route event reward. It uses new
discovery seeds 201..204 and confirmation seeds 301..316. The primary contrast
and bootstrap procedure were specified in PLAN.md before running.

The even control matches event timing, maximum absolute reward magnitude, and
schedule, but has a different signed mean reward. It tests whether asymmetric
rewards are necessary here; it does not isolate every statistical property of
the reward. Geometry remains unchanged. See EVIDENCE.md for the actual results.

## Independently computed expected answers

Run after installing the same Raylib headers used by the native build:

```sh
python3 projects/mirror-detour/oracle.py --output /tmp/mirror-oracle.json
```

The reference graph comes from explicit obstacle cells in `oracle-spec.json`,
not the candidate collision function. Python computes legal transitions and BFS
shortest paths, checks Bellman identities, and compares distances with an analytic
geometric bound. A C adapter runs the actual environment on 24,660 specified
cases. Nine deliberately faulty variants must compile and then fail the same
oracle. Each rejection records a concrete counterexample; compilation failures
never earn detection credit.

CI pins the specification hash. Evidence records hashes of the specification,
checker, adapter, and candidate. Change the task specification only as an explicit
reviewed task change, not to make a candidate pass. Evidence files cannot be
overwritten by the runner.

This separates computations, not authorship or permissions. The same author can
still modify the checker and CI. The tests cover selected state/configuration
combinations, not all behavior, and mutation detection does not prove absence of
other defects. Independent enforcement requires a reviewer or protected evaluator
outside the candidate author's write access.
