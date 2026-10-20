# Architecture and design contracts

## Decision from the caller inward

```python
world = HouseholdWorld(seed=7, horizon=30, weekly_budget_cents=14500)
observation = world.observe()
next_observation, reward, finished, info = world.step(3)  # LOW_WASTE
alternate_world_result = world.fork(1)  # copy; no original mutation
state = world.state()
```

The public interface is deliberately small. `HouseholdWorld` owns the **authoritative** state and physical/economic transitions; none of the user-interface, model or Beads layers may change cash, inventory or outcomes directly. A single step is a simulated day, with one household dinner attempt.

## Types and ownership

| Module | Owns | Rejects/guards |
| --- | --- | --- |
| `models.py` | Person, product, offer, recipe, nutrient, operation, money ledger | Negative mass or money; invalid product yield |
| `economics.py` | Price extension, BOGO/percentage/threshold rules, joint-basket cost | Stock and budget infeasibility |
| `inventory.py` | FEFO lot ownership, freezing, expiration, transfer and conservation | Unbacked consumption |
| `catalog.py` | Explicitly synthetic fixture values; deterministic store shock generator | Future-price leakage to observations |
| `beads.py` | Typed execution-plan graph, status projection and topology | Unresolved predecessor, self edge, duplicate ID, cycles |
| `scheduler.py` | Capacity-constrained resource scheduling and precedence bound | Missing resources, dependencies, cycles |
| `physics.py` | Educational thermal-state estimates | Invalid physical model inputs |
| `world.py` | One-day transaction boundary, person-specific portions, household state, scoring | Budget, mass, allergens, invalid step |
| `rl.py` | Eight macro-action policies, CPU PPO training and evaluation | Claims of trained benefit without evaluation |
| `api.py` | Loopback-bound HTTP session and request validation | Concurrent mutation through single RLock |
| `replay.py` | Finite, self-contained preview trajectory | Claim that replay is a live environment |

## Dynamics and timescales

- **Day:** observe current-day offers; expire foods; choose a policy; select and price a meal; purchase; consume; schedule; emit food, nutrition and finance events.
- **Minute:** plan kitchen DAG with bounded resource slots; the list schedule is an approximation to job-shop scheduling, not an exact solution.
- **Five simulated seconds:** reduced-order thermal proxy advances within the chosen operation duration. No output can certify food safety.
- **Week:** hard cash budget windows, with fixed synthetic dinner-only spending envelope.
- **Multi-day:** lot expirations, leftovers, promotions, household menu history, training credit assignment.

## Graph and causation

`BeadCompiler` compiles an ordered directed acyclic graph with typed events, person-specific branches, procurement provenance and resource reservations. A DAG edge means **must precede** or **requires completion**, not a causal assertion about physiology. Real world transitions remain in `world.step`. `DAG.run` currently allows structural node completion with default pass-through handlers. Future integration should turn those handlers into observed precondition checks tied to transaction confirmations; today's 'passed' does not mean a physical receipt was independently verified.

## Reproducibility

`offers_for_day(day,seed)` draws synthetic current offers without exposing future draws. `snapshot()` deep-copies state including PRNG state, allowing matched-randomness branch comparisons for `fork(action)`. Every episode is deterministic for a seed, policy and code version. Distribution shift tests must draw new seeds **and eventually new generative families**, not just new random seeds.

## Observations and actions

Observation vector includes normalized day, budget remainder, waste, served-rate, household dinner acceptance, inventory coverage, eight offered price signals, and prepared-food state. It intentionally does **not** expose future prices or the simulator PRNG. Actions are eight **macro strategies**: `BALANCED`, `CHEAPEST`, `PROMOTIONS`, `LOW_WASTE`, `NUTRIENT_FIRST`, `PANTRY_ONLY`, `BATCH_PREP`, `NEARBY_ONLY`. The world selects recipes/baskets using those strategies. A trained policy does not control every individual purchase, ingredient placement, appliance setting or Bead.

## Objective and constraints

Feasibility: configured food restrictions, store availability, one-week budget, prerequisite operations, resource capacities, cash/nonnegative inventory, mass conservation. Optimization: meal coverage, synthetic acceptance, waste, spending. Independent score `world.score()` remains fixed on a 0–100 scale. The step reward is a **separate but intentionally correlated** weighted signal; benchmark on score not reward.

## Alternatives considered

- **Everything as graph execution:** attractive unified representation, but confounds precedence with money and physical-state mutations; rejected.
- **Single monolithic policy controlling each utensil and purchase:** expressive but infeasible action space and difficult training signal; postponed.
- **Typed dynamic DAG + authoritative world transitions + hierarchical macro-policy:** implemented. It preserves accountable economic and material ledgers while allowing higher fidelity adapters and conditional action expansion.

## Limitations and threats to validity

- Calorie references are invented dinner allocations. Pediatric targets, health profiles and food-safety rules require appropriate sources and validation.
- Retail price and stock simulator is not calibrated against real vendors or correlated external shocks. Basket search changes strategy for >10 product requirements; see `economics.py`.
- Nutrition sums are ingredient-table approximations and do not correct for cooking nutrient losses or individual absorption.
- Physical model lacks calibrated heat-transfer coefficients and microbial lethality.
- Bead completion status is currently structural, not an externally audited success.
- A policy winning against these synthetic heuristics might exploit simulator bias; no real-world advantage is implied.
- The Ocean environment is reduced fidelity. Official PufferLib 5.0 native integration and policy training were not tested in this runtime due DNS/GPU restrictions.
