# S-Expression Repository World (experimental PufferLib Ocean environment)

The simulator turns **code transformations** and **repository-maintenance work** into compact, bounded, verifiable RL actions. `ocean/sexpr_repo/sexpr_repo.h` provides `puf_init`, `puf_reset`, `puf_step`, `puf_log`, `puf_render`, and `puf_close`. `sexpr_core.h` is a standalone C11 simulation kernel for rapid transitions.

## Action vocabulary

`SQUARE_MUL`, `FUSE_DOT`, `ELIM_ZERO`, `COMMUTE`, `REPLACE_ADD_SUB` (adversarial invalid rewrite), `REPAIR_IMPORT`, `REGISTER_ENV`, `ADD_TEST`, `DEDUP_FILE`, `RUN_TESTS`, `COMMIT`, `ROLLBACK`, `WAIT`, `STOP`.

## Semantics and scientific boundary

* Expressions are **typed integer-valued mini-programs**, not arbitrary Common Lisp or general-purpose source. Two seeded source shapes are compared to an independently pinned reference across 81 bounded input pairs. This is exhaustive only for the specified finite domain; no general semantic equivalence is claimed.
* Repository operations mutate a **synthetic dependency graph**, not real GitHub. Required imports, registrations, tests and duplicates are held in read-only verifier state.
* `COMMIT` succeeds only after checks pass, and the episode terminates. The verifier is not editable through the policy action space. This prevents several trivial reward hacks, not all forms of Goodharting.
* The current reward uses incremental graph health, small computational-cost proxies, penalties for failed edits and a final verified completion bonus. No claim is made that proxy cost equals real-world wall-clock performance.
* The CPU simulator can be used in PufferLib Ocean; native Puffer training has **not** been run for this change. Run `./build.sh sexpr_repo --cpu` from a full Staypuff checkout to compile the interactive viewer if build dependencies are installed.

## Standalone verification

```bash
bash projects/sexpr-repo-rl/scripts/check.sh
```

## Next benchmark gates

1. Report random, shortest-repair deterministic, greedy and PPO policies on **disjoint seeds**; score complete verified commits, action count and graph health independently.
2. Add held-out grammars, functions and repository fault patterns. Verify graph and reward-instrument integrity against adversarial policy mutations.
3. Export proposals as Git diffs only after isolated `git worktree` compilation/tests and explicit approval of consequential changes. Never give an RL policy unrestricted write access to its evaluator.
4. Replace bounded integer expression checks with domain-appropriate static proof, SMT or differential tests before claiming real-code equivalence.

**Do not conflate simulator steps/second with actual compiler or GitHub operations/second.**

## Interactive native REPL

```bash
bash projects/sexpr-repo-rl/scripts/repl.sh 42
# sr> help
# sr> show
# sr> square_mul
# sr> fuse_dot
# sr> repair_import
# sr> run_tests
# sr> commit
```

The REPL prints the executable S-expression and the simulated repository's imports, registrations, tests and duplicate count after each action. It never edits real files.

## Ocean adapter

Use `./build.sh sexpr_repo --cpu` or `./build.sh sexpr_repo` in a complete Staypuff/PufferLib toolchain. The `projects/validation` test uses a lightweight header stub and is **not** full trainer integration evidence.
