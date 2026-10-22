# Measured results: Procedure Lab repair study

All figures below are measured CPU results. The original experiment is unchanged; its final checkpoint exactly reproduced all six recorded evaluation conditions.

## Primitive-action PPO

18 training runs: six arms, three seeds each, 1,048,576 transitions per run (18,874,368 total). Each final checkpoint received 768 full-difficulty held-out episodes. Values below average six conditions and then three training seeds.

| Arm | Immediate abandon | Any abandon | Rounds | Retentions | Actual gain |
|---|---:|---:|---:|---:|---:|
| control | 99.91% | 100.00% | 0.0000 | 0.0000 | 0.000000 |
| abandon_charge | 0.00% | 0.00% | 3.0000 | 0.0000 | 0.000000 |
| no_cost | 0.00% | 0.00% | 2.9818 | 0.0000 | 0.000000 |
| feedback | 0.00% | 0.00% | 3.0000 | 0.0000 | 0.000000 |
| exploration | 0.00% | 0.09% | 2.9978 | 0.0000 | 0.000000 |
| curriculum | 0.00% | 0.04% | 2.9991 | 0.0000 | 0.000000 |

Adding an abandonment charge changes the learned behavior, but stopping abandonment is not sufficient evidence of procedural improvement. Reward scales differ across arms; final evaluator gain is the common outcome. The positive objective remains reachable, as the scripted controller demonstrates. These tests do not establish that PPO cannot learn the primitive workflow.

## Scaffolded program-selection PPO

The fixed executor supplies legal workflows. PPO chooses among 16 programs using four public contract bits. All three final checkpoints are reported; none was selected for presentation. Each seed trains for 32,768 macro episodes, with active-episode native transitions listed below.

| Training seed | Active native transitions | Learned accuracy | Learned gain | Random-target gain | Scripted gain |
|---|---:|---:|---:|---:|---:|
| 7 | 582,087 | 80.07% | 0.407884 | -0.016290 | 0.607191 |
| 19 | 586,040 | 79.97% | 0.406901 | -0.016290 | 0.607191 |
| 41 | 586,056 | 87.28% | 0.479974 | -0.016290 | 0.607191 |

The universal program is defeated by incompatible contracts. The learned selector does improve independently evaluated retained programs, but it does not discover the executor, diagnose checkers, or demonstrate generalization to unseen semantic contracts. Its compute and action abstraction differ from primitive PPO. Transition counts exclude discarded post-terminal vector-lane steps; they are not full dispatched-compute counts.

## Independent exact-budget comparison

A second held-out stream caps each baseline at the learned policy’s actual operation cost on the identical task. Baselines stop before overspending; the retained artifact is then scored without an extra action. These caps match native execution cost, not training compute.

| Training seed | Learned gain | Random native gain | Valid-random gain | Scripted gain |
|---|---:|---:|---:|---:|
| 7 | 0.395372 | 0.000000 | 0.000753 | 0.588243 |
| 19 | 0.391785 | 0.000000 | 0.000753 | 0.588243 |
| 41 | 0.468099 | 0.000000 | 0.000753 | 0.588243 |

Per-condition paired standard errors and per-episode records are in `evidence/macro-matched/`. Primitive-policy exact-budget comparisons are in `evidence/primitive-matched/`. Reused test tasks and only three training seeds limit inference; episode counts are not independent training replications.

## Verification and boundaries

- Native ASan/UBSan checks passed: 312,480 oracle comparisons, 16 pairwise incompatible contracts, 512 isolation/potential checks, and a falsified-checker regression attack.
- Four public-action-mask tests passed. The original native verification and original checkpoint replay passed unchanged.
- Source snapshots, plans, traces, portable checkpoints, raw paired observations, and hashes are included. The first-run trace-prefix label correction is disclosed in README.
- The experimental fork is opt-in. No reward or curriculum change is promoted to the default environment on the strength of eliminating abandonment alone.
- Remaining alternatives include exploration difficulty, representation and optimization choices, sparse retention credit, and task-design simplicity. This experiment does not distinguish all of them.
