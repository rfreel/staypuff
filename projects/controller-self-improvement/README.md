# A self-applicable search controller: measured result

The first configuration revision improved fresh-task performance at an equal
assignment-evaluation budget including development. A second revision did not
establish recursive benefit. No production controller is replaced.

## What was actually revised

A fixed Python search procedure searches bit strings. Twelve configuration bits
control restart patience, mutation radius, acceptance, random jumps, proposals
from the best incumbent, and temperature. The same procedure searches its own
configuration, scored by its performance on development Max-Cut instances.
Generation 1 then controls the search for generation 2. A frozen-meta ablation
uses the original search controller for the second revision instead. Both start
that second revision at the same generation-1 configuration.

This is executable, autonomous configuration-level self-modification. It is not
LLM weight training, arbitrary source-code invention, or a Dream-RSI reproduction.
There are no model calls inside the experiment. The immutable search procedure
and finite configuration space were designed by the assistant.

## Frozen comparison

See PROTOCOL.md for the before-run rules. There are 16 independent development
chains, each with two batches of eight development graphs. Controllers were
frozen before generating the held-out seed. Final evaluation uses 96 fresh
18-vertex graphs, balanced across three edge densities, with independent solver
randomness per chain. No held-out tuning or rerun occurred.

Each arm is charged 1,572,864 assignment evaluations across the 16 chains:

| Arm | Development evaluations per chain | Attempts per held-out graph |
| --- | ---: | ---: |
| Original / uniform random | 0 | 1,024 |
| Generation 1 | 24,576 | 768 |
| Generation 2 / frozen-meta | 49,152 | 512 |

The descendant arms each pay for generation 1. Failed and duplicate candidate
configurations are charged. Exact-reference construction is shared evaluation
infrastructure; its timing is recorded separately. Equal assignment counts are
not equal wall time or total engineering effort.

## Held-out results

| Arm | Mean percentage of exact optimum | Exact-optimum hit rate | Search-loop seconds, including development |
| --- | ---: | ---: | ---: |
| Original | 97.2551% | 14.45% | 3.252 |
| Uniform random | 93.9956% | 0.78% | 0.727 |
| Generation 1 | 98.6894% | 47.07% | 3.512 |
| Generation 2 | 98.3317% | 40.36% | 3.556 |
| Frozen-meta revision | 98.3104% | 40.69% | 3.593 |

Mean score is the primary metric. Intervals below are paired two-way bootstrap
98.75% intervals over chains and density-stratified tasks, with 10,000 resamples.
The four intervals implement the preregistered nominal Bonferroni correction.
The acceptance threshold was lower bound > 0.2 percentage points of optimum.

| Contrast | Gain in percentage points | Interval | Gate |
| --- | ---: | --- | --- |
| Generation 1 minus original | +1.4343 | [+1.1320, +1.7321] | PASS |
| Generation 2 minus generation 1 | -0.3577 | [-0.6420, -0.0835] | FAIL |
| Generation 2 minus frozen-meta | +0.0213 | [-0.3556, +0.5287] | FAIL |
| Generation 2 minus random | +4.3361 | [+3.8841, +4.8172] | PASS |

All 16 chains changed configuration in cycle 1; 14 changed again in cycle 2.
Eight generation-2 configurations differed from the frozen-meta counterpart.
Thus the recursive treatment actually executed, but its additional benefit was
not established. The near-zero comparison does not prove equivalence.

The second cycle may have insufficiently useful development data, a mismatched
meta-search objective, or too much development cost relative to deployment.
This experiment does not distinguish these explanations. Its reduced deployment
budget is deliberate: judging only final-controller quality would hide that cost.
Search-loop wall time also increased. No wall-time or full-resource improvement
is established. The recorded short timings are descriptive, not a separate
well-powered timing study; reference construction, audit, analysis, and shared
assistant design work are not represented as algorithmic savings.

## Verification and evidence

The exact checker enumerates 2^17 partitions per graph, using complement symmetry.
A separate direct edge sum checks reported witnesses. Calibration checks 3,048
partitions on small graphs. The audit additionally checks known complete-graph
and ring optima, reconstructs all 96 held-out references, verifies 7,680 deployment
and 9,216 development witnesses, replays all 48 controller revision sequences,
and confirms identical charged assignment counts per arm.

The result archive retains all candidate configurations and scores, successful
solution witnesses, seeds, frozen source hashes, execution times, and confidence
intervals. It does not retain every rejected graph partition explored inside a
search call; those are reproducible from the frozen source and seeds.

```sh
python -m pip install numpy==2.3.5
python projects/controller-self-improvement/audit.py projects/controller-self-improvement/results
```

To run a new statistical replication, select a new output directory. Development
seeds stay fixed in this implementation; a new deployment seed is drawn after
controllers are frozen. For new independent development chains, explicitly
version a new protocol and development seeds first.

```sh
python projects/controller-self-improvement/experiment.py develop --out /tmp/controller-replication
python projects/controller-self-improvement/experiment.py evaluate --out /tmp/controller-replication
```

Existing experiment outputs refuse overwrite. Evaluation rejects modified source
or controller hashes. These are integrity checks, not protection against an actor
who can modify both the evaluator and the checks. The evidence supports one
bounded configuration-level improvement on this graph distribution; the declared
recursive-benefit and full-resource gates both fail.
