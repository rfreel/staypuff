# Procedure Lab

A native PufferLib environment for choosing tools, revising executable procedures,
testing changes, and deciding what to retain. This is a bounded synthetic task,
not evidence of recursive model improvement or transfer to real development work.

The environment header is `ocean/procedure_lab/procedure_lab.h`. It uses the native
Agent buffers, 48 float observations, three action heads `[10, 4, 5]`, fixed-size
state, and no allocation during reset or step. Each instance has one agent.

## World and episode families

The task is to count array elements greater than or equal to a threshold. Programs
are executable four-bit configurations. Bits enable inclusive comparison, negative
values, repeated values, and the last element, respectively. Program 15 is correct.
An edit toggles one behavior; it does not award an improvement score by itself.
Arrays contain up to eight integers. Initial programs vary between episodes.

| Family | Initial obstacle | Useful discovery |
|---|---|---|
| 0: missing capability | No runner | Request and actually use the runner |
| 1: defective checker | Checker accepts every output | Acquire an auditor, audit, repair, retest |
| 2: failed transfer | Program 8 passes narrow development cases | Generate boundary/transfer cases or inspect defects |

`family=-1` mixes the families. Family identity is public. Checker identity and
individual tool offers are initially hidden. Tools are runner (0), boundary-case
generator (1), transfer-case generator (2), and auditor (3). The optional transfer
generator is unavailable in approximately one third of episodes; other tools can
always be requested. Tool IDs have fixed meanings, so discovery concerns
availability and usefulness, not an unknown API mapping.

Development tests use fresh generated cases. Family 2 initially uses four distinct
positive values and threshold zero. Boundary tests emphasize equal and repeated
values; transfer tests emphasize negatives and longer arrays. Final cases mix all
three generators, always without the narrow override. `evaluate=1` changes the
random-case lengths from 0..8 to 5..8, expands the value range, and scales values
by nine. This is a distribution perturbation within the same task, not a new
program language or a proof of generalization. Separate seeds should be reserved
for final learned-policy evaluation; do not tune against those results.

## Actions

All three action heads must contain in-range integers. Unused parameters are
ignored. Semantic errors consume the operation cost and incur a 0.02 penalty.
There is no conditional action mask; invalid choices are part of the learning task.

| ID / operation | Target | Parameter | Cost |
|---|---|---|---:|
| 0 INSPECT | 0 candidate, 1 incumbent, 2 checker, 3 catalog | Ignored | 1 |
| 1 REQUEST_TOOL | Tool ID | Ignored | 4 |
| 2 HYPOTHESIZE | Tool ID | 1 assumes an output is usable; 0 leaves branch unchanged | 1 |
| 3 EXECUTE | Tool ID | Ignored | 2 |
| 4 MODIFY | 0 procedure, 1 strategy, 2 checker | Procedure: toggle bit 0..3 or apply proposal 4; others: ID 0..3 | 2 |
| 5 TEST | 0 candidate, 1 incumbent, 2 strategy proposal | 0 development, 1 boundary, 2 transfer | 4 |
| 6 AUDIT | Ignored | Ignored | 4 |
| 7 RETAIN | 0 procedure, 1 strategy, 2 both | Ignored | 1 |
| 8 REVERT | Ignored | Ignored | 1 |
| 9 SUBMIT | 0 finish round, 1 abandon episode | Ignored | 1 |

Checker inspection and AUDIT require an acquired auditor. EXECUTE runner actually
runs the candidate and exposes the output, length, and threshold; it does not
certify correctness. Executing a generator materializes access to its test family.
TEST requires a real runner and, for boundary/transfer cases, an acquired and
executed generator. Each test runs 16 cases. AUDIT compares all possible outputs
0..8 on a distinguishing case against the reference. This exactly distinguishes
the four built-in checkers: correct, strict comparison, deduplicating, always-pass.
It is not a general checker-verification algorithm.

HYPOTHESIZE records a speculative dependency, never a measured pass. Subsequent
edits inherit all outstanding assumptions, including assumptions about tools
already acquired. Requesting a tool does not clear these dependencies. Executing
it does; actual candidate/strategy tests also resolve the runner and relevant
case-generator dependencies. Testing the incumbent cannot certify the candidate.
The model is a dependency bitset for one speculative branch, not a general DAG.
REVERT discards candidate dependencies but leaves outstanding assumptions visible.

Edits to the procedure, strategy, or checker invalidate both test certificates.
Retention requires current real tests for the retained object and no unresolved
dependencies. It does not require a passing score: a real failed test is evidence,
and retaining a known bad candidate remains a policy decision. A later incumbent
test replaces the displayed program test result and clears its candidate certificate.

## Recursion, reward, and termination

A retained strategy selects the proposed bit for later rounds: always bit zero,
round-robin, first observed failing-case category, or an offset round-robin.
Failure categories are observed input properties, not privileged diagnoses.
TEST strategy runs the candidate with that strategy's proposed edit. Retaining
a strategy changes the proposal at the next round. MODIFY procedure with parameter
4 applies it; explicit edits remain available. Procedure and strategy retention
are separate decisions. Strategy testing measures a proposal in the current
context, not its performance on every future round.

Default episodes have three rounds and a shared budget of 96. SUBMIT evaluates
the retained procedure, then carries it and the retained strategy into the next
round. Each round uses a separate batch of 64 cases generated at episode reset.
Action/test RNG consumption cannot change those cases. Every step subtracts
`0.002 * resource_cost`. At submission add:

```text
(correct_retained - correct_original - 0.5 * new_regressions) / (64 * rounds)
```

The original program is the episode baseline for every round. This scores the
benefit of using an improved procedure repeatedly without giving direct reward
for claims, tests, or retention. Regressions are cases previously correct and now
wrong. Exhaustion evaluates the retained procedure once and ends immediately;
an unaffordable action is not executed. Abandon ends with no additional task
reward. Terminal steps auto-reset while preserving terminal and reward buffers.

The final scorer uses a separate direct reference and never the editable checker.
No action can edit the reference or final cases. This separation is enforced by
the simulator API, not by operating-system process isolation. Positive task reward
at submission necessarily reveals aggregate performance, but never the cases.

## Observation layout

Unavailable scores/inspections use -1. Booleans are 0/1.

| Index | Value |
|---|---|
| 0..2 | Family / 2, round / configured rounds, remaining / initial budget |
| 3..5 | Retained strategy / 3, candidate strategy / 3, proposed bit / 3 |
| 6..9 | Latest program score, strategy score, current candidate test, current strategy test |
| 10..12 | Audit result, known checker / 3 or -1, operation status (-1 invalid, 1 valid) |
| 13..17 | Last output / 8, expected output / 8 (-1/8 if unknown), length / 8, threshold / 36, operation / 9 |
| 18..21 | Acquired tools |
| 22..25 | Assumed tool outputs |
| 26..29 | Candidate dependencies |
| 30..33 | Candidate program bits if inspected |
| 34..37 | Incumbent program bits if inspected |
| 38..41 | Observed failure categories: equality, negative, duplicate, nonempty |
| 42..45 | Known tool availability or -1 |
| 46..47 | Materialized boundary and transfer generators |

Logs: `perf` averages final accuracy over completed rounds (zero if abandoned
before any submission); `score` is episode return; `cost`, `invalid`, `retained`,
and `rounds` are episode totals. The native logger aggregates these using `n`.

## Run and verify

From the repository root, with the repository's normal Clang/Raylib dependencies:

```bash
./build.sh procedure_lab procedure_lab_view --cpu --debug
bash projects/procedure-lab/verify.sh
./procedure_lab_view --headless --eval_episodes=10 --env.evaluate=1
```

For native GPU policy training, on a CUDA-capable machine:

```bash
./build.sh procedure_lab procedure_lab_train
./procedure_lab_train train
```

The environment itself is CPU C; the normal native trainer uses GPU policy
learning. GPU compilation and PPO training were not run in the implementation
session. Do not treat the scripted baseline as a trained policy.

`test.c` checks all 16 programs on 19,530 finite-domain cases against a histogram
oracle independent of both executable implementations; each incorrect program
must have a counterexample. It also checks provenance, checker repair, score
independence, stale tests, strategy influence, budgets, reset, observation hiding,
80,000 deterministic replay steps, and 128,000 steps across 128 separate instances
with buffer guards. C with ASan/UBSan and optimized C++ must emit identical results.

`results.json` contains 1,000 episodes per family/distribution/policy combination.
The scripted policy reads only observations, inspects the program, enables the
four known-correct behaviors, repairs the defective checker, tests, retains, and
submits all rounds. Random actions can abandon and frequently select invalid
combinations; their accuracy is therefore not a matched-effort learning baseline.

The scripted policy solves every submitted case. This proves the environment is
solvable through its public interface. It also exposes the main limitation: one
universal four-bit repair can bypass strategy learning and checker diagnosis.
Audit and recursion are available and tested, but are not necessary for optimal
behavior in this initial task family. A stronger benchmark needs competing
procedures, tasks with incompatible optimal edits, and held-out strategy tasks.
