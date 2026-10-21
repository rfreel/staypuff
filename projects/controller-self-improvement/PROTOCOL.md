# Frozen experiment: self-applicable search controller

Claim: a bounded bit-string search controller can revise its own configuration,
and using the revised controller for the second revision improves fresh-task
performance beyond continuing to revise with the original controller.
This tests configuration-level self-improvement, not model-weight changes,
unrestricted program synthesis, or general intelligence.

## Task and exact reference
Weighted Max-Cut on 18 vertices, independent positive integer edge weights 1..9.
Graphs are equally divided across edge probabilities 0.2, 0.5, 0.8. Every graph
also has a unit-weight ring, adding weight if an edge already exists. A solution
is an 18-bit partition. Score is cut weight / exact optimum. Exhaustive enumeration
of the 2^17 partitions with vertex zero fixed establishes the optimum; complement
symmetry covers the other half. Direct edge summation independently verifies every
reported witness and calibrates the table on tiny graphs and random partitions.
The controller gets only a score callback, dimension, budget, and random seed.

## Controller and two revision cycles
The immutable generic controller is configured by 12 bits: restart patience
(8/16/32/64), maximum flip radius (1/2/3/4), acceptance rule (strict/nondecreasing/
Metropolis/threshold), random-jump probability (four values), best-state proposal probability (four
values), and temperature/tolerance (four values). All settings and their
semantics are fixed in controller.py before results. Initial configuration is 0:
one-bit strict hill climbing, restart after eight consecutive rejected moves.
A uniform random search is the additional baseline.

Each revision uses that same controller to search its own 12-bit configuration.
Each of 24 proposed configurations runs on eight development graphs, 128 scored
assignments each, with common random numbers. No cache discounts repeated trials.
Cycle 1 uses configuration 0 as the meta-controller. Cycle 2 uses the cycle-1
winner. The frozen-meta ablation starts from the same cycle-1 winner but still
uses configuration 0 to propose cycle-2 configurations. Development batches differ
between cycles. The current configuration is evaluated first and can remain winner.
No human chooses a winner or edits candidate rules after evaluation.

## Work, randomness, and controls
16 independent revision chains. Each uses disjoint development graphs. Freeze
all controllers before drawing a fresh 256-bit evaluation seed with secrets.
96 shared held-out graphs (32 per density), each with a distinct solver seed per
chain. Rotation of arm order across chain/task counters reduces timing-order bias.
No tuning on held-out outcomes; one final evaluation; no optional stopping.

Per-chain budget is 96 * 1024 = 98,304 scored graph assignments per arm, inclusive
of controller search. Each revision costs 24 * 8 * 128 = 24,576 assignments.
Thus base/random get 1024 assignments per held-out graph; generation 1 gets 768;
generation 2 and frozen-meta each get 512. Development failures and duplicate
proposals remain charged. Generation-1 work is charged to each descendant.
All arms share exact-reference construction; reference construction time is recorded.
Wall time for development plus deployment is recorded separately. Equal assignment
counts do NOT imply equal wall time, token cost, or total engineering cost. There
are zero model calls inside the loop; human/assistant design work is shared setup
and is not a measured self-improvement cost saving.

## Acceptance and inference
Four preregistered paired contrasts in normalized held-out score:
(1) gen1 - base; (2) gen2 - gen1; (3) gen2 - frozen_meta; (4) gen2 - random.
Report means, exact-optimum rates, per-chain outcomes, and full raw traces.
Use 10,000 two-way bootstrap resamples over independent chains and graphs,
stratifying graphs by edge density; preserve paired arms. Two-sided 98.75%
percentile intervals give nominal Bonferroni familywise 95% coverage for four
comparisons, subject to bootstrap approximation (16 chains limits precision).
Material threshold: interval lower bound > 0.002 (0.2 percentage points of optimum).
Self-improvement supported only if contrast 1 passes. Recursive benefit supported
only if all four pass. Full-resource benefit additionally requires summed gen2
measured development+deployment time <= summed base deployment time.
Any invalid witness, budget mismatch, or checker failure invalidates the experiment.
A negative result stays negative; no rerun with friendlier thresholds or task sizes.

## Limits and stopping
Stop after both cycles and the single held-out evaluation. Fixed finite configuration
space, narrow graph family, computationally separate checker with same authorship,
no privilege isolation, and no demonstrated transfer beyond this workload.
Reproducible stored seeds make later reruns confirmations of execution, not fresh
statistical replications. Changes after freezing must be explicit protocol deviations.
