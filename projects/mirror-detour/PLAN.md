# Prewalk: temporary symmetry-breaking reward

Base: rfreel/staypuff 5.0 at 69e27dacd9a7930d768b10ea2fda1f386bb1ff40.

## Inspected before editing
- SKILL_ISSUES.md: compact C, inline single-use logic, preserve determinism.
- ocean/minimal/minimal.h and src/pufferenv.h: native Agent buffers and lifecycle.
- src/ini.h, config/default.ini, build.sh: configuration and native build integration.
- No AGENTS.md files in the base tree. No CUDA toolkit/GPU on the execution host.

## Execute in order
1. Add one header-only native environment and config. A fixed 11x11 arena has a
   centered obstacle, mirrored starts, and a centered goal. Four cardinal actions.
2. Reward success with 1. Give the optional odd bonus only at the first crossing
   above the obstacle, preventing repeated wall-pushing or looping bonus harvest.
   Track original success independently. Include baseline, +/- odd, fixed hashed
   action perturbation, and goal-distance shaping controls. Use an independent
   start RNG; reward controls must consume no environment RNG.
3. Count annealing in transitions per environment, never episode ticks. Expose
   a step_offset for weights-only native checkpoint continuation. Evaluation
   disables shaping explicitly. Do not claim native checkpoints save Env state.
4. Compile against real src/pufferenv.h and raylib headers. Exhaustively check
   mirror transitions, action/state involution, oddness, rewards, terminal/reset
   semantics, no-bias parity, schedule boundaries, and valid observations.
5. Run a small CPU tabular Q-learning diagnostic against the same C environment.
   This is actual learning, not PuffeRL/PPO evidence. Separate discovery and
   confirmation seeds; preserve complete results, timing, and source identity.
6. Provide native GPU experiment commands and CI. Validate native CPU build if
   dependencies permit; report the CUDA training limitation explicitly.
7. Commit implementation, plan, and measured evidence to a feature branch and
   open a PR. Do not merge or modify the trainer.

## Claim gate
A directional preference is not task improvement. Compare unshaped held-out
success and speed after bonus removal. A diagnostic result cannot establish
PPO transfer, broad generalization, or nonlinear amplification. Equal tuning
budgets and wall-clock costs are required for stronger claims.

## Follow-up prewalk: equal-route progress control

The first matrix cannot distinguish odd structure from subgoal reward. Add mode=4,
abs(route_event), so either first crossing earns the same bonus. It matches the
odd condition's event, maximum absolute magnitude, and schedule, but not signed
reward mean. That remaining difference must be reported, not called isolated
causality. Keep the old experiment untouched.

Freeze five families (baseline, odd +, odd -, hash, even), four magnitude/duration
candidates each, discovery seeds 201..204, confirmation seeds 301..316, and two
million transitions per run. Select using the same training-start curve metric.
Primary contrast: average of the two odd-sign curve-success scores minus even,
paired by confirmation seed. Report mean delta and a fixed-seed 20,000-resample
percentile bootstrap interval across seeds. No equivalence or broad RL claim.
Secondary outcomes: unshaped held-out success, route length, and route fraction.
Test even reflection invariance, one-time payout, and evaluation disabling.
Stop after this comparison and verification; do not search until a desired result.
