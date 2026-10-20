# Two distinct Beads DAGs

**Runtime Beads** are generated each simulation day by `household/beads.py` and serialized into `world.state()['beads']`. Their edges are operation-precedence dependencies. Node types include information, goal, decision, procurement, physical control, allocation, verification, cleanup, and learning. `run()` projects completion states, but currently has pass-through handlers. An actual grocery payment or thermal verification must not be inferred from the passed status alone.

**Engineering Beads** are machine-readable backlog and verification tasks in [`planning/beads.json`](../planning/beads.json). They are a separate **development DAG**, with statuses `complete`, `partial`, `planned`, and `blocked`. A typed task may depend on several other tasks. The DAG can be inspected and checked with:

```sh
python scripts/inspect_backlog.py
python scripts/inspect_backlog.py --json
```

The ontology in `docs/ontology.yaml` is a **proposed universe of possible concepts**, not a statement that every element is implemented in current runtime code.

## Priorities

1. Preserve verified conservation and transaction invariants as features are added.
2. Replace pass-through Bead handlers with atomic, observed world mutations and executed verifiers.
3. Introduce person-specific clinical-source validation and age-appropriate hard constraints, without prescribing calories based on sex/age alone.
4. Add true food-safety and temperature-history models only after calibration and expert validation.
5. Extend from one dinner per day to all eating occasions, household expenses and shopping logistics.
6. Connect reliable price/stock feeds with freshness, provenance, promotion and locality semantics.
7. Establish Python vs C step-level parity; then build against the full official PufferLib 5.0 checkout and train/evaluate policies.
8. Demonstrate an RL policy beating classical, heuristic and model-predictive controls on family-disjoint, market-disjoint, held-out domains.

## Validity invariant

A `complete` development Bead means **the named bounded capability and its local evidence exist**; it does not mean the entire domain is solved. `partial` describes actual partial runtime code or experimental validation. `planned` is design only. `blocked` names an external dependency.
