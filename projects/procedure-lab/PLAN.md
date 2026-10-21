# Procedure Lab implementation contract

Implement a native single-agent, multi-discrete PufferLib environment. Preserve
existing environments and trainer behavior. All arrays are fixed-size; no per-step
allocation. Use the existing C Agent observation/action/reward/terminal buffers.

World: three rounds, a 96-unit shared budget, a count-at-least-threshold program,
a proposed program, a retained and proposed edit-selection strategy, four tools,
an editable in-world checker, and deterministic generated arrays. Four program
bits fix >= comparison, negative handling, duplicate handling, and last-element
handling. The separate reference counts directly from the task specification.

Episode families: missing runner (must acquire real execution), defective checker
(always-pass initially), failed transfer (narrow development cases omit important
cases). Training and evaluation configurations use separate case distributions.
Final evaluation cases are generated on reset, independent of agent action RNG.

Actions: INSPECT, REQUEST_TOOL, HYPOTHESIZE, EXECUTE, MODIFY, TEST, AUDIT, RETAIN,
REVERT, SUBMIT, each with operation-specific target and bounded parameter.
SUBMIT target 1 abandons. Every action costs budget. Invalid actions cost budget
and receive a small penalty. Tests/claims/inspection never earn positive reward.

Speculative tools never enter the real capability mask. Artifacts copy outstanding
assumptions as dependencies. Acquisition does not resolve dependencies; actual
execution does. Editing invalidates tests. Retention requires current real test
provenance and resolved dependencies. Checker failure is observable only through
inspection with an acquired auditor or actual audit. Checker edits never affect
the external evaluator. Repeated test calls use fresh cases, with explicit cost.

Strategy edits affect later proposed procedure edits and have a separate TEST
operation that executes the proposal against cases. Strategies may be retained
only after a current real strategy test, with dependencies resolved. Inspect and
results expose actual program representations and test outcomes, not hidden final
cases, seed, score tables, capability offers, or checker internals by default.

At each submission, score downstream accuracy gain over the episode's original
procedure, minus additional regressions, divided by configured round count.
Always subtract resource costs. Budget exhaustion evaluates the currently retained
procedure once and ends; abandon receives no additional task reward. No reward
for merely retaining, testing, or predicting success. Auto-reset preserves terminal
reward and exposes the next episode observation as the native API expects.

Before publication verify: direct reference vs all 16 programs on a finite
exhaustive case corpus; independent transition/reward expectations; all three
families; assumed-tool laundering attempts; stale-proof invalidation; checker
weakening; actual strategy influence; budget and submit boundaries; deterministic
replay; C++ compatibility; ASan/UBSan; full native CPU build and multi-instance
headless smoke. Measure scripted and random policies separately from RL training.
Do not claim learned transfer or PPO execution without training.
