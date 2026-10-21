# Evidence

## Executed on this implementation

- Base repository: `69e27dacd9a7930d768b10ea2fda1f386bb1ff40`.
- 242,880 paired transition combinations across three obstacle widths, all
  nonterminal traversable positions, all four actions, every episode tick,
  and route states (excluding unreachable route=0 positions above the obstacle).
  Assertions check mirrored transitions/observations, coupled resets, original
  rewards, opposite-sign shaped rewards, terminal flags, and finite observations.
- Zero-mode/sign/strength/evaluation parity: 40,000 steps, exact buffer and log
  equality. One-time bonus, schedule endpoint, zero duration, persistent controls,
  config offset, terminal reward preservation, and log export also pass.
- GCC ASan+UBSan tests pass. LeakSanitizer disabled locally because this host
  cannot inspect /proc tasks under its tracing restrictions, not because a leak
  was detected. CI retains default LeakSanitizer behavior.
- Environment header passes GNU C++17 syntax checking for the CUDA host dialect.
- Actual `src/puffercpu.c` runtime compiled and completed 10 untrained headless
  episodes: `n=10 perf=0 score=0 steps=800 untrained=1`. This is integration
  evidence only; it is not trained-policy evidence. GCC emitted an existing
  checkpoint-path truncation warning in src/puffercpu.c.
- CPU tabular diagnostic repeats exactly except timing for the same seed.
- Python scripts compile and native seven-arm command plan generates correctly.
- No CUDA hardware/toolkit here: PuffeRL training, GPU numerics, and native
  trained-policy rendering have NOT been executed. Renderer is compiled, not
  visually verified. Remote CI status belongs to GitHub, not this local record.

## Frozen CPU diagnostic

The manifest was written before the matrix ran. Four candidates x four discovery
seeds x seven families, plus eight confirmation seeds x seven selected families:
168 actual Q-learning runs, each 2,000,000 C environment transitions (336 million
total). Discovery seeds 1..4; confirmation seeds 101..108. Fixed alpha=.3,
gamma=.99, epsilon=.2. Full per-seed curves and source SHA-256 hashes are retained
in results/diagnostic.json. No significance claim is made from these eight seeds.

All evaluations disable shaping. Held-out reset locations are two cells not used
as training resets; they may be visited during training. Every mean below is
across the eight confirmation seeds. Curve success is the mean of ten periodic
unshaped evaluations on training-distribution starts, not held-out accuracy.

| Condition | Final held-out success | Mean episode length | Mean curve success |
| --- | ---: | ---: | ---: |
| baseline | 100.00% | 65.79 | 0.8971 |
| odd_plus | 100.00% | 54.75 | 1.0000 |
| odd_minus | 100.00% | 52.62 | 1.0000 |
| persistent_plus | 100.00% | 52.96 | 1.0000 |
| persistent_minus | 100.00% | 49.00 | 1.0000 |
| hash | 99.80% | 54.99 | 1.0000 |
| potential | 100.00% | 59.82 | 0.8500 |

The whole diagnostic sweep took 14.08 seconds on this host.
Individual runs are too short and sequentially ordered for robust wall-clock
comparisons; timing includes periodic evaluation. Baseline and persistent-duration
candidates include intentional duplicates to keep candidate/step budgets equal.
The learning algorithm itself was not separately tuned for each family.

## What the observations distinguish

Both odd signs select the intended orientation (100% matching route among these
held-out evaluation episodes), and their learning-curve success exceeds the
baseline in this diagnostic. However, the hashed perturbation has the same
average curve success. Final success is saturated. Persistent bias also works.
There is no demonstrated special benefit from odd symmetry or from removing the
bonus. Average routes remain much longer than a shortest route, exposing a weak
and incomplete diagnostic learner despite high success. These observations do
not establish nonlinear amplification, PPO transfer, or broad superiority.

Next evidence gate: run the native GPU matrix with matched tuning budgets,
independent seeds, unshaped evaluation, and multiple layouts/tasks. Native runner
and config are supplied; those results remain unmeasured.

## Local dependency and runtime

Raylib 5.5 official Linux archive SHA-256:
`3d95ef03d5b38dfa55c0a16ca122d382134b078f0e5b270b52fe7eae0549c000`.
Dependencies and build binaries are not committed. Tests use the actual repository
API headers and official raylib headers; no substitute PufferLib API is used.

## Follow-up: equal-route control (new seeds)

The new mode=4 pays the same positive bonus for either route's first crossing.
It matches event timing, maximum absolute reward magnitude, and schedule, but
NOT signed reward mean. All prior results above remain historical; their source
hashes correspond to commit 38c166955545c5da9c1320581138213cdf94b094.

The follow-up plan was recorded before execution. Four candidates x four new
discovery seeds x five families, plus sixteen confirmation seeds x five selected
families: 160 actual runs, 320 million additional C transitions. Discovery seeds
201..204 and confirmation seeds 301..316 do not overlap the first experiment.
The complete frozen manifest, selected settings, per-seed curves, and source
hashes are in results/even-control*.json. The original files were not overwritten.

| Family | Mean sampled curve success | Final held-out success | Mean episode length |
| --- | ---: | ---: | ---: |
| baseline | 0.9018 | 99.90% | 65.17 |
| odd_plus | 1.0000 | 100.00% | 52.50 |
| odd_minus | 1.0000 | 99.90% | 52.30 |
| hash | 1.0000 | 100.00% | 48.62 |
| even | 1.0000 | 100.00% | 48.25 |

Execution wall time: 13.29 seconds including all runs and
analysis. These short timings remain diagnostic, not throughput benchmarks.

The prespecified primary contrast, average odd-sign curve success minus even,
was 0 on every confirmation seed. Its paired percentile bootstrap interval is
[0,0] because every shaped condition scored 1 at every sampled checkpoint. This
is endpoint saturation, NOT proof of equivalence or zero uncertainty. The first
checkpoint is at 200,000 transitions; differences before then are unmeasured.

The even control's mean route length was 48.25, compared with 52.50 for positive
odd and 52.30 for negative odd. This is a secondary descriptive observation,
not a statistically confirmed dominance claim. The even control has aggregate
left/right proportions .5/.5; it did not require a directional reward to succeed.
Its reset-distribution test still does not establish unseen-geometry transfer.

The useful update is narrower: a direction-independent intermediate reward
suffices for the observed sampled success in this diagnostic. Neither a unique
benefit of mirror structure nor a special amplification mechanism is supported.
The remaining alternatives include ordinary subgoal shaping and different reward
means. Native PPO remains unmeasured.

Follow-up verification: the prior 242,880 mirrored-transition checks still pass,
plus added even-control reflection/equal-payout, no-repeat-payout, persistent-mode,
and evaluation-disable checks. The actual CPU runtime builds with ASan/UBSan and
accepts mode=4. The native GPU runner now includes eight arms. CI runs both study
modes with a smaller smoke budget; those CI runs are not the frozen experiment.
