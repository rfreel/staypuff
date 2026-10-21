# PPO pilot: learned immediate abandonment

On October 21, 2026, a CPU PPO run completed 1,048,576 transitions and 64 updates
against the unchanged native C environment. Training took 29.28 seconds, excluding
compilation and evaluation. The parameter change had L2 norm 3.894. This was actual
policy-gradient training, using PyTorch through `ppo_bridge.c`; it was not the
repository's native CUDA PuffeRL trainer.

The normal native training build failed because `ccache` was unavailable. The host
also had neither `nvcc` nor a CUDA device. The build output is preserved in
`ppo-run/native-attempt.txt`. CPU PyTorch 2.14.1+cpu was available, so the pilot
compiled a small shared library around the existing `puf_init`, `puf_reset`, and
`puf_step`. No reward, action, or transition logic was changed.

The plan was written before training. It fixed one training seed (7), 256 parallel
environments, horizon 64, four PPO epochs, minibatches of 2,048, learning rate
0.0003 annealed linearly, clipping 0.2, discount 0.99, GAE lambda 0.95, and entropy
coefficient 0.01. The policy is a two-layer 128-unit tanh MLP with independent
categorical action heads and a scalar critic. PPO uses the joint action log
probability. Terminal transitions cut GAE and value bootstrapping; rollout horizons
bootstrap normally. This feedforward pilot has no recurrent memory.

Evaluation used seed 910007 and 1,000 episodes in each of the three families and
two case distributions, both before and after training. Only the final checkpoint
was evaluated after training. No hyperparameters were changed in response to the
results. Policies sample actions during evaluation. Evaluation RNG is isolated
from training RNG. The episode streams are distribution comparisons, not paired
identical trajectories, because policies terminate at different times.

| Metric, equal-weight mean across six conditions | Before | After |
|---|---:|---:|
| Episode reward | -0.355915 | -0.002000 |
| Completed rounds per episode | 0.8945 | 0 |
| Episodes completing all three rounds | 11.22% | 0% |
| Retentions per episode | 0.02133 | 0 |
| External task gain | approximately 0 | 0 |

Every reported final evaluation episode abandoned immediately. The final policy
paid only the one-unit abandonment cost. Logged accuracy is zero by convention
when no round is submitted; it does not measure a newly damaged procedure.

The reward increase comes from avoiding operation costs and invalid actions, not
from improving a procedure. The run demonstrates a readily learned abandonment
strategy under this configuration. It does not establish that PPO cannot solve
the environment: insufficient exploration, the sparse multi-action repair path,
the feedforward policy, and the reward structure remain competing explanations.
No reward changes or post-result retraining were made in this pilot.

## Reproduce

Install NumPy and CPU PyTorch, and make the repository's Raylib headers available.
Run from the repository root, using a fresh output directory:

```bash
python3 projects/procedure-lab/ppo.py --output /tmp/procedure-ppo-repeat
```

The script requires a C compiler and builds the bridge automatically. It writes
its plan, per-update trace, evaluation results, and checkpoint. Exact numeric
repeatability is only expected with the same platform and dependencies.
`ppo-run/plan.json` includes the source hashes and configuration used here.
`ppo-run/policy.pt` is a PyTorch state dictionary, not a native PuffeRL `.bin`.
`ppo-run/results.json` preserves all condition-level results; `trace.jsonl`
preserves all 64 updates. Compiled libraries and the redundant JSON checkpoint
export are excluded from git.
