"""CPU PPO pilot using the unchanged native Procedure Lab transition function."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


class World:
    def __init__(self, lib, count, family, evaluate, seed):
        self.lib = lib
        self.obs = np.zeros((count, 48), np.float32)
        self.actions = np.zeros((count, 3), np.float32)
        self.rewards = np.zeros(count, np.float32)
        self.done = np.zeros(count, np.float32)
        self.metrics = np.zeros((count, 6), np.float32)
        self.ptr = lib.lab_create(count, family, evaluate, seed,
                                 self.obs, self.actions, self.rewards, self.done)
        assert self.ptr

    def step(self, actions):
        self.actions[:] = actions
        self.lib.lab_step(self.ptr, self.metrics)

    def close(self):
        self.lib.lab_free(self.ptr)


class Policy(nn.Module):
    def __init__(self):
        super().__init__()
        self.body = nn.Sequential(nn.Linear(48, 128), nn.Tanh(),
                                  nn.Linear(128, 128), nn.Tanh())
        self.actor = nn.Linear(128, 19)
        self.critic = nn.Linear(128, 1)
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.orthogonal_(module.weight, np.sqrt(2))
                nn.init.zeros_(module.bias)
        nn.init.orthogonal_(self.actor.weight, .01)
        nn.init.orthogonal_(self.critic.weight, 1)

    def forward(self, obs, actions=None):
        hidden = self.body(obs)
        distributions = [Categorical(logits=x)
                         for x in self.actor(hidden).split([10, 4, 5], -1)]
        if actions is None:
            actions = torch.stack([d.sample() for d in distributions], -1)
        logp = sum(d.log_prob(actions[:, i]) for i, d in enumerate(distributions))
        entropy = sum(d.entropy() for d in distributions)
        return actions, logp, entropy, self.critic(hidden).squeeze(-1)


@torch.no_grad()
def evaluate(policy, lib, episodes, seed):
    results = []
    # Preserve training RNG; test feedback never changes the training schedule.
    with torch.random.fork_rng():
        torch.manual_seed(seed)
        for family in range(3):
            for shifted in range(2):
                world = World(lib, 64, family, shifted, seed + family*10000)
                completed = []
                while len(completed) < episodes:
                    actions, _, _, _ = policy(torch.from_numpy(world.obs))
                    world.step(actions.numpy())
                    completed.extend(world.metrics[world.done != 0].copy())
                data = np.asarray(completed[:episodes])
                gain = data[:, 1] + .002*data[:, 2] + .02*data[:, 3]
                results.append(dict(family=family, evaluate=shifted, episodes=episodes,
                                    accuracy=float(data[:, 0].mean()),
                                    reward=float(data[:, 1].mean()),
                                    task_gain=float(gain.mean()),
                                    invalid=float(data[:, 3].mean()),
                                    retained=float(data[:, 4].mean()),
                                    rounds=float(data[:, 5].mean()),
                                    all_rounds=float((data[:, 5] == 3).mean())))
                world.close()
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--steps', type=int, default=1048576)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--eval-episodes', type=int, default=1000)
    parser.add_argument('--output', type=Path, default=HERE / 'ppo-run')
    args = parser.parse_args()
    os.chdir(ROOT)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    torch.set_num_threads(2)
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    torch.use_deterministic_algorithms(True)
    count, horizon, epochs, minibatch = 256, 64, 4, 2048
    batch = count*horizon
    assert args.steps > 0 and args.steps % batch == 0
    updates = args.steps // batch
    sources = ['ocean/procedure_lab/procedure_lab.h',
               'projects/procedure-lab/ppo_bridge.c', 'projects/procedure-lab/ppo.py']
    plan = dict(algorithm='clipped PPO with GAE', device='cpu', seed=args.seed,
                steps=args.steps, environments=count, horizon=horizon,
                epochs=epochs, minibatch=minibatch, gamma=.99, gae_lambda=.95,
                clip=.2, entropy=.01, value_weight=.5, max_grad_norm=.5,
                learning_rate=.0003, anneal_learning_rate=True,
                evaluation_seed=910007, eval_episodes=args.eval_episodes,
                selection='final checkpoint only; no tuning on evaluation',
                torch_version=torch.__version__,
                source_sha256={p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
                               for p in sources})
    (output / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    library = output / 'lab.so'
    subprocess.run([os.environ.get('CC', 'cc'), '-shared', '-fPIC', '-O2',
                    '-fvisibility=hidden', '-ffunction-sections', '-fdata-sections',
                    '-Wl,--gc-sections', '-Wl,--no-undefined',
                    '-D_POSIX_C_SOURCE=200809L', '-Isrc',
                    '-Iraylib-5.5_linux_amd64/include',
                    str(HERE / 'ppo_bridge.c'), '-lm', '-o', str(library)], check=True)
    lib = ctypes.CDLL(str(library))
    array = np.ctypeslib.ndpointer(dtype=np.float32, flags='C_CONTIGUOUS')
    lib.lab_create.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int,
                              ctypes.c_uint, array, array, array, array]
    lib.lab_create.restype = ctypes.c_void_p
    lib.lab_step.argtypes = [ctypes.c_void_p, array]
    lib.lab_step.restype = None
    lib.lab_free.argtypes = [ctypes.c_void_p]
    lib.lab_free.restype = None
    policy = Policy()
    initial = torch.cat([p.detach().flatten() for p in policy.parameters()]).clone()
    before = evaluate(policy, lib, args.eval_episodes, 910007)
    print(json.dumps({'before': before}), flush=True)
    world = World(lib, count, -1, 0, args.seed)
    optimizer = torch.optim.Adam(policy.parameters(), lr=.0003, eps=1e-5)
    obs = torch.zeros(horizon, count, 48)
    actions = torch.zeros(horizon, count, 3, dtype=torch.long)
    logps = torch.zeros(horizon, count)
    rewards = torch.zeros(horizon, count)
    dones = torch.zeros(horizon, count)
    values = torch.zeros(horizon, count)
    advantages = torch.zeros(horizon, count)
    started = time.perf_counter()
    trace = []
    for update in range(updates):
        optimizer.param_groups[0]['lr'] = .0003*(1 - update/updates)
        episode_metrics = []
        for t in range(horizon):
            obs[t].copy_(torch.from_numpy(world.obs))
            with torch.no_grad():
                action, logp, _, value = policy(obs[t])
            actions[t], logps[t], values[t] = action, logp, value
            world.step(action.numpy())
            rewards[t].copy_(torch.from_numpy(world.rewards))
            dones[t].copy_(torch.from_numpy(world.done))
            episode_metrics.extend(world.metrics[world.done != 0].copy())
        with torch.no_grad():
            _, _, _, next_value = policy(torch.from_numpy(world.obs))
            last_adv = torch.zeros(count)
            for t in reversed(range(horizon)):
                following = next_value if t == horizon - 1 else values[t + 1]
                live = 1 - dones[t]
                delta = rewards[t] + .99*following*live - values[t]
                last_adv = delta + .99*.95*live*last_adv
                advantages[t] = last_adv
            returns = advantages + values
        bobs, bact = obs.reshape(-1, 48), actions.reshape(-1, 3)
        blog, badv, bret = logps.flatten(), advantages.flatten(), returns.flatten()
        kls, clips = [], []
        for _ in range(epochs):
            permutation = torch.randperm(batch)
            for start in range(0, batch, minibatch):
                idx = permutation[start:start + minibatch]
                _, newlog, entropy, value = policy(bobs[idx], bact[idx])
                logratio = newlog - blog[idx]
                ratio = logratio.exp()
                adv = badv[idx]
                adv = (adv - adv.mean()) / (adv.std(unbiased=False) + 1e-8)
                actor = torch.maximum(-adv*ratio, -adv*ratio.clamp(.8, 1.2)).mean()
                critic = .5*((value - bret[idx])**2).mean()
                loss = actor + .5*critic - .01*entropy.mean()
                assert torch.isfinite(loss)
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(policy.parameters(), .5)
                optimizer.step()
                kls.append(float(((ratio - 1) - logratio).detach().mean()))
                clips.append(float(((ratio - 1).abs() > .2).float().mean()))
        metrics = np.asarray(episode_metrics)
        row = dict(step=(update + 1)*batch, seconds=time.perf_counter() - started,
                   episodes=len(metrics), reward=float(metrics[:, 1].mean()),
                   accuracy=float(metrics[:, 0].mean()), rounds=float(metrics[:, 5].mean()),
                   retained=float(metrics[:, 4].mean()), approx_kl=float(np.mean(kls)),
                   clip_fraction=float(np.mean(clips)))
        trace.append(row)
        with (output / 'trace.jsonl').open('a') as stream:
            stream.write(json.dumps(row) + '\n')
        if update % 8 == 0 or update == updates - 1:
            print(json.dumps(row), flush=True)
    world.close()
    training_seconds = time.perf_counter() - started
    final = torch.cat([p.detach().flatten() for p in policy.parameters()])
    after = evaluate(policy, lib, args.eval_episodes, 910007)
    torch.save(policy.state_dict(), output / 'policy.pt')
    # Plain arrays provide a portable, reviewable checkpoint in the git repository.
    checkpoint = {k: v.detach().tolist() for k, v in policy.state_dict().items()}
    (output / 'policy.json').write_text(json.dumps(checkpoint, separators=(',', ':')))
    result = dict(before=before, after=after, training_seconds=training_seconds,
                  weight_change_l2=float((final - initial).norm()),
                  updates=updates, transitions=args.steps)
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
