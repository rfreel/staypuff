# Evidence register — 2026-10-20

## Source attribution

- Official upstream: PufferAI/PufferLib tag/branch `5.0`.
- API/interface inspected: `ocean/minimal/minimal.h` and `src/pufferenv.h` through a connected GitHub fetch.
- Upstream Minimal directory listed and checked; this runtime's direct `git clone` failed: `Could not resolve host: github.com`.
- `ocean/household/household.h` is an authored derivative targeting the inspected interface, **not** a proven upstream compilation. `vendor/upstream-reference/minimal.h` is a source excerpt for reference, not a complete vendored upstream checkout.

## Automated evidence

Run from repository root:

```sh
python -m pytest -q --disable-warnings
bash scripts/build_native.sh
python -m household.cli benchmark --steps 1000
python scripts/browser_check.py
```

`pytest`: **66 passed**, current local source. Includes domain money calculations, per-person restrictions, inventory mass conservation, DAG typing/dependency tests, scheduler precedence/resources, repeatability, episode score, API and PPO smoke checks.

`build_native.sh`: builds standalone C heat kernel and Ocean-compatible C header using **a test stub** for the upstream `pufferenv.h`. Successfully runs its deterministic smoke test. Neither this nor GCC alone proves complete PufferLib compatibility.

`browser_check.py`: Chromium verified self-contained recorded replay rendering on desktop and mobile; advanced day, opened Beads and kitchen views, compared eight alternatives, checked market rows, and captured five actual screenshots with no JavaScript exceptions. Chromium policy blocked direct browser navigation to the loopback API; API routes are verified separately in FastAPI test clients. `browser_check_live.py` additionally executes the actual FastAPI API from rendered Chromium via a locally injected fetch transport, verifying household configuration, reset, step and counterfactual selection end-to-end.

## PPO experiment

The initial CPU PPO run: 2,304 agent decisions and one saved checkpoint, held-out mean score **83.371** vs stronger `LOW_WASTE` **86.776** (eight synthetic seeds); the policy was inferior.

The revised CPU PPO run: 70 updates × 6 environments × 12 steps = **5,040** simulated decisions, 64-unit 2-layer shared MLP with discrete categorical actor and critic, clipped PPO/GAE. Reward changed to align its primary terms with independent score. Preserved weights at `artifacts/household_ppo.pt` and log at `artifacts/train-log.json`.

A fresh final comparison uses 12 previously unevaluated synthetic seeds **20,001–20,012** and 30 days per scenario. `LOW_WASTE` and PPO both score **86.873** on average; the paired difference is **0.000** with bootstrap interval **[0.000, 0.000]**. See `artifacts/final-heldout.json` for all scores and confidence interval.

**Result: PPO equals the strongest `LOW_WASTE` baseline, and improvement is not demonstrated.** The generated simulator currently makes that heuristic particularly strong. Matching one heuristic is useful evidence that the learner is functional, but does not validate cross-domain adaptation.

## Limits on claims

| Claim | Status | Grounding |
| --- | --- | --- |
| Synthetic household simulation executes | Verified | Python tests + episode CLI |
| Budget/inventory ledgers conserve values | Verified in modeled conditions | Invariants + tests |
| Interactive recorded desktop/mobile HTML works | Verified | Browser tests + actual images |
| API supports configurable people and actions | Verified | FastAPI test client |
| Standalone C native thermal code compiles | Verified | GCC smoke test |
| Reduced Ocean header compiles with local stub | Verified | GCC smoke test |
| Full PufferLib 5.0 build works | **Unverified** | Upstream clone blocked, no CUDA |
| Learned policy beats scripted baseline | **Not demonstrated** | Fresh held-out comparison |
| Nutritionally/medically appropriate personalized diet | **Not established** | Synthetic dinner references only |
| Safe cooking temperatures / edible food safety | **Not established** | Educational thermal proxy only |
| Current real-store pricing or purchases | **Not implemented** | Entirely synthetic market |
| Full household daily caloric coverage | **Not implemented** | Dinner only |
