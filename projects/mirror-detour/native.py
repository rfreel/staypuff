#!/usr/bin/env python3
"""Preview or execute seven fixed native PuffeRL arms. No diagnostic-to-PPO claims."""
import argparse
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--seed', type=int, default=101)
    parser.add_argument('--steps', type=int, default=10_485_760)
    parser.add_argument('--strength', type=float, default=0.1)
    parser.add_argument('--anneal-fraction', type=float, default=0.25)
    parser.add_argument('--output', type=Path, default=ROOT / 'logs' / 'mirror-native')
    args = parser.parse_args()
    assert args.steps > 0 and args.steps % (1024 * 64) == 0
    assert 0 <= args.anneal_fraction <= 1 and args.strength >= 0
    anneal = int(args.steps / 1024 * args.anneal_fraction)
    arms = [('baseline', 0, 0, 0), ('odd_plus', 1, 1, 0), ('odd_minus', 1, -1, 0),
            ('persistent_plus', 1, 1, 1), ('persistent_minus', 1, -1, 1),
            ('hash', 2, 1, 0), ('potential', 3, 1, 0)]
    output = args.output.resolve()
    common = [f'--base.seed={args.seed}', '--base.async=0',
              '--vec.total_agents=1024', '--policy.hidden_size=64', '--policy.num_layers=2',
              '--env.half_width=2', '--env.start_radius=1', '--env.step_offset=0',
              '--train.gamma=0.99', '--env.shaping_gamma=0.99']
    plan = []
    for name, mode, sign, schedule in arms:
        run_id = f'{name}_seed{args.seed}'
        command = ['./mirror_puffer', 'train', *common, f'--base.run_id={run_id}',
                   f'--base.checkpoint_dir={output / "checkpoints"}',
                   f'--base.log_dir={output / "logs"}', f'--train.total_timesteps={args.steps}',
                   f'--env.mode={mode}', f'--env.sign={sign}', '--env.evaluate=0',
                   f'--env.schedule={schedule}', f'--env.strength={args.strength}',
                   f'--env.anneal_steps={anneal}']
        plan.append(dict(arm=name, run_id=run_id, command=command))
    manifest = dict(status='planned', seed=args.seed, steps=args.steps,
                    anneal_steps_per_instance=anneal, arms=plan,
                    evaluation='explicit saved weights, evaluate=1, 256 episodes on each start set')
    if not args.execute:
        print(json.dumps(manifest, indent=2))
        return
    # A fresh directory prevents accidental checkpoint reuse or evidence overwrite.
    for binary in ('mirror_puffer', 'mirror_view'):
        if not (ROOT / binary).is_file():
            raise SystemExit(f'Missing {binary}; follow the two README build commands')
    output.mkdir(parents=True, exist_ok=False)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    results = []
    for item in plan:
        started = time.monotonic()
        with (output / f'{item["arm"]}.train.log').open('w') as log:
            subprocess.run(item['command'], cwd=ROOT, stdout=log,
                           stderr=subprocess.STDOUT, check=True)
        checkpoints = output / 'checkpoints' / 'mirror_detour' / item['run_id']
        weights = max(checkpoints.glob('*.bin'), key=lambda path: int(path.stem))
        assert int(weights.stem) == args.steps, 'expected final training checkpoint is missing'
        scores = []
        for radius in (1, 2):
            cmd = ['./mirror_view', str(weights), '--headless', '--eval_episodes=256',
                   f'--base.seed={args.seed + 10000}', '--env.evaluate=1',
                   f'--env.start_radius={radius}', '--env.half_width=2',
                   '--policy.hidden_size=64', '--policy.num_layers=2']
            result = subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT)
            (output / f'{item["arm"]}.radius{radius}.eval.log').write_text(result)
            line = next(line for line in result.splitlines() if line.startswith('CPU_EVAL '))
            values = dict(field.split('=', 1) for field in line.split()[1:])
            assert values['untrained'] == '0' and float(values['n']) == 256
            scores.append(dict(radius=radius, metrics=values))
        results.append(dict(arm=item['arm'], checkpoint=str(weights), scores=scores,
                            train_and_eval_seconds=time.monotonic() - started))
        (output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    manifest['status'] = 'completed'
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
