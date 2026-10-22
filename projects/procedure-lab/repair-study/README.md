# Procedure Lab: incentive and exploration repair study

This is an additive experimental fork of PR #7 at
`f76b5997a998681c78ce04a8c5d07c5eb8e75fb2`. The original native environment,
`ppo.py`, `PPO.md`, checkpoint, configuration, and recorded failure are unchanged.
Nothing here changes the default environment or claims that the original PPO
pilot succeeded. See `REPORT.md` for measured results.

## What is repaired, and what is not

1. **Cheap abandonment:** a fixed 0.5 abandonment charge removes the advantage of
   quitting over three immediate submissions in the tested tasks. It does not
   make procedure improvement inevitable. Unchanged submissions remain feasible.
2. **Universal repair:** each episode has one of 16 incompatible task contracts.
   A separate histogram reference defines the intended result. All 16 programs
   are pairwise distinguishable by executable counterexamples. Program 15 is no
   longer universally correct.
3. **Misleading success metrics:** final accuracy and change from the original
   program are measured even after abandonment, over all 192 final cases. Reward,
   completed rounds, retention calls, and actual task gain are separate fields.
4. **Exploration control:** a separate PPO selector chooses a program while a
   fixed executor handles acquisition, inspection, modification, testing,
   retention, and submission. Its result is scaffolded learning, not autonomous
   discovery of valid workflows, checker diagnosis, or strategy invention.

## Controlled primitive-action alternatives

Every arm uses the same adversarial native fork, 52 public observations, 200 joint
categorical actions, 96 cost units, and at most three rounds. The original pilot
had three independent action heads and 48 observations. Consequently `control`
is a control within this study, not a numerically identical rerun of the pilot.

| Arm | Change | Comparison |
|---|---|---|
| control | Original cost and abandonment rule | Internal reference |
| abandon_charge | Charge 0.5 on abandonment | control |
| no_cost | Remove operation costs from reward; keep budget, invalid penalties, abandonment charge | abandon_charge |
| feedback | Add discounted public-probe potential feedback; keep operation costs and abandonment charge | abandon_charge |
| exploration | Canonical action forms and observation-based validity mask | feedback |
| curriculum | Original starts one bit from the contract for first half of updates | exploration |

The mask does not use goal bits, final cases, or hidden state. Abandonment remains
available. It canonicalizes redundant parameter combinations as well as reducing
invalid actions, so this arm does not isolate entropy alone. Curriculum changes
initial programs, not final evaluation difficulty; in-flight episodes can extend
briefly past the halfway update before the next reset.

Public-probe feedback uses a fixed, separate stream of 32 public cases and the
retained incumbent, never the editable checker or final cases:

`r_shape = 0.99 * Phi(next) - Phi(current)`; terminal `Phi` is zero.

Its discounted episode total is `-Phi(initial)`, independent of the action path.
This prevents accumulating positive shaping reward by toggling, retesting,
reverting, or repeatedly retaining the same program. It also means this feedback
alone need not resolve the sparse first-retention problem. There is no bonus for
operation counts, audits, completed rounds, or test passes.

The final evaluator keeps the original round reward structure: improvement over
the original procedure minus a regression penalty. The task contract changes its
specification, not its acceptance threshold. Final case streams are generated at
reset and cannot be selected or changed through actions. As in PR #7, this is
logical separation inside trusted native code, not an OS security boundary.

## Task contracts

Four public bits specify whether to include threshold equality, negative values,
duplicate occurrences, and the final element. The candidate interpreter and the
reference implement these independently. Checker variants are defined relative
to that episode's contract, including the always-accepting checker.

The goal bits identify the optimal four-bit program directly. This is deliberately
a small learnability control with conflicting answers. It is not a hidden-contract
benchmark, held-out semantic task family, or evidence of general procedural
reasoning. Checker diagnosis and strategy edits remain optional for optimal
performance; the contract-aware executor does not need them.

## Instrumentation and comparisons

`run.py` records per-update action frequencies, abandonment probability, valid
operation rate, cost, actual final gain, reward, rounds, and retentions. Final
evaluation adds reset-state abandonment probability, operation probabilities,
immediate abandonment frequency, positive-gain rate, and valid ordered
procedure-modify → candidate-test → procedure-retain sequence counts. Retention
counts can include no-op retention; they are never treated as improvement.

The `first_lane_prefix` diagnostic is a maximum 32-step prefix from one vector
lane and may span resets. The frozen first-run source/results called this field
`first_episode_prefix`; that label was corrected afterward without changing the
training or its recorded numeric measurements. Use `repair_sequences` for
within-episode valid sequence counts.

Baselines include immediate abandonment, uniform random native actions, random
valid canonical actions, a contract-aware scripted repair, and the old universal
repair. All receive the same native cap. `matched.py` adds a stricter comparison:
for each policy and held-out task, baseline cost cannot exceed that policy's
actual spending. It stops before an over-budget action and uses a read-only
snapshot to score the retained procedure, without an extra submit or reward.
Caps are ceilings, not forced equal expenditure; a baseline may terminate early.

The macro selector is also compared against random program selection using the
same fixed executor and against native scripted/random baselines under its exact
per-task spending cap. It has a different action abstraction and training budget;
its result cannot be attributed to reward changes alone.

## Reproduce

Requirements: Linux CPU, C compiler, Python 3.12, NumPy 2.3.5, CPU PyTorch
2.14.1+cpu, and the Raylib 5.5 header. No graphics library is linked; unreachable
render functions are removed by the linker. Set `RAYLIB_INCLUDE` to the directory
containing `raylib.h`. Exact dependency versions are recorded in each run plan.

From the repository root, use fresh output directories:

```bash
export RAYLIB_INCLUDE=/path/to/raylib/include
bash projects/procedure-lab/repair-study/verify.sh
python projects/procedure-lab/repair-study/test_python.py
python projects/procedure-lab/repair-study/original_diagnostics.py /tmp/pilot-replay
python projects/procedure-lab/repair-study/run.py --output /tmp/primitive-study
python projects/procedure-lab/repair-study/matched.py /tmp/primitive-study --output /tmp/primitive-matched
python projects/procedure-lab/repair-study/macro.py --output /tmp/selector-study
python projects/procedure-lab/repair-study/matched_macro.py /tmp/selector-study --output /tmp/selector-matched
```

Each runner refuses an existing output directory, writes its plan before training
or evaluation, uses final checkpoints only, and never tunes on held-out results.
The macro study was added after early primitive runs showed unchanged submissions;
its schedule was fixed before its own training. It is an explicitly disclosed
follow-up, not part of the initial six-arm plan. No seed was dropped or rerun for
selection.

Primitive training uses 3 seeds × 6 arms × 1,048,576 transitions, 64 updates each.
Evaluation uses 128 episodes × 6 conditions per checkpoint on seed 910007; exact
cost matching uses a separate root seed 1910007. The selector uses 3 seeds × 128
updates × 256 macro episodes; active-episode native transition counts are reported rather
than assumed equal. Macro `native_transitions` excludes discarded steps in
vector lanes that have already finished while other lanes remain active; it is
not a count of every dispatched C step or a hardware-compute measure. Its evaluation roots are 2910007 and 3910007. All final
evaluations use full-difficulty originals, both case distributions, and all three
families. These are held-out seed streams, not held-out contracts.

## Verification and evidence

- 312,480 program/reference comparisons across exhaustive small cases.
- Every pair of contracts has a distinguishing executable witness.
- All 16 contracts occur in a 512-seed coverage check.
- 512 checker-tampering/final-case isolation checks and discounted feedback checks.
- An always-accepting checker certifies a damaged program while final gain and
  reward remain negative.
- Public mask tests verify no goal-dependent action selection and evidence gates.
- The preserved pilot checkpoint exactly reproduces its six recorded final results.
- Original native ASan/UBSan and optimized C++ checks also pass unchanged.

Local ASan/UBSan used `ASAN_OPTIONS=detect_leaks=0`; leak detection was not verified
locally. CI uses default sanitizer settings. CPU smoke testing is included in
`.github/workflows/procedure-repair-study.yml`; CI status is separate from local
verification. GPU execution and native PuffeRL integration of this experimental
fork were not tested.

`evidence/` contains plans, all traces and condition-level results, checkpoint
arrays, raw paired evaluations, source snapshots, and a SHA-256 manifest. Native
shared libraries are excluded. Checkpoint arrays are NumPy `.npz` with tensor names
as keys, avoiding pickle for the committed portable copies. Use `restore.py` to
restore the `.pt` files expected by the evaluation scripts.
