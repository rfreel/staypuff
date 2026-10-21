#!/usr/bin/env python3
"""Frozen CPU diagnostic sweep over the actual native environment."""
import argparse
import hashlib
import json
import random
from pathlib import Path
import statistics
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
PROJECT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', choices=('original', 'even-control'), default='original')
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--steps', type=int, default=2_000_000)
    parser.add_argument('--output', type=Path, default=None)
    args = parser.parse_args()
    assert args.steps >= 100
    if args.output is None:
        name = 'diagnostic.json' if args.study == 'original' else 'even-control.json'
        args.output = PROJECT / 'results' / name
    if args.output.exists():
        raise SystemExit(f'Refusing to overwrite evidence: {args.output}')
    discovery_seeds = [1, 2, 3, 4]
    confirmation_seeds = list(range(101, 109))
    binary = args.binary.resolve()
    configs = []
    families = [('baseline', 0, 0, 0), ('odd_plus', 1, 1, 0),
                ('odd_minus', 1, -1, 0), ('persistent_plus', 1, 1, 1),
                ('persistent_minus', 1, -1, 1), ('hash', 2, 1, 0),
                ('potential', 3, 1, 0)]
    if args.study == 'even-control':
        families = [('baseline', 0, 0, 0), ('odd_plus', 1, 1, 0),
                    ('odd_minus', 1, -1, 0), ('hash', 2, 1, 0), ('even', 4, 1, 0)]
        discovery_seeds = list(range(201, 205))
        confirmation_seeds = list(range(301, 317))
    # Every family gets four discovery candidates. Baseline duplicates are
    # intentional: same run count/step budget, no extra tuning for shaped arms.
    for family, mode, sign, schedule in families:
        for strength in (0.05, 0.2):
            for fraction in (0.1, 0.5):
                configs.append(dict(family=family, mode=mode, sign=sign,
                                    schedule=schedule, strength=strength,
                                    anneal_steps=int(args.steps * fraction)))
    source_paths = ['ocean/mirror_detour/mirror_detour.h', 'config/mirror_detour.ini',
                    'projects/mirror-detour/diagnostic.c', 'projects/mirror-detour/run.py',
                    'src/pufferenv.h', 'src/ini.h']
    manifest = dict(backend='CPU tabular Q-learning, not PuffeRL/PPO',
                    alpha=0.3, gamma=0.99, epsilon=0.2, total_steps=args.steps,
                    discovery_seeds=discovery_seeds, confirmation_seeds=confirmation_seeds,
                    study=args.study,
                    primary_contrast="mean odd signs minus even curve success"
                    if args.study == "even-control" else None,
                    selection='mean discovery curve success, then shorter curve length',
                    training_starts=[4, 6], heldout_starts=[3, 7],
                    evaluation='64 episodes, stochastic greedy ties, shaping disabled',
                    source_sha256={p: digest(ROOT / p) for p in source_paths},
                    configs=configs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Freeze the design on disk before any discovery runs.
    args.output.with_suffix('.manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    started = time.monotonic()
    runs = []

    def execute(config, seed, phase):
        cmd = [str(binary), str(seed), str(config['mode']), str(config['sign']),
               str(config['strength']), str(config['anneal_steps']), str(args.steps),
               str(config['schedule'])]
        result = json.loads(subprocess.check_output(cmd, cwd=ROOT, text=True))
        result.update(family=config['family'], phase=phase)
        runs.append(result)
        return result

    selected = {}
    for family, _, _, _ in families:
        candidates = []
        for config in (c for c in configs if c['family'] == family):
            batch = [execute(config, seed, 'discovery') for seed in manifest['discovery_seeds']]
            score = statistics.mean(p['success'] for r in batch for p in r['curve'])
            length = statistics.mean(p['length'] for r in batch for p in r['curve'])
            candidates.append(((score, -length), config))
        selected[family] = max(candidates, key=lambda item: item[0])[1]
    # No selection using held-out starts or confirmation seeds.
    args.output.with_suffix('.selected.json').write_text(json.dumps(selected, indent=2) + '\n')
    summary = {}
    for family, config in selected.items():
        batch = [execute(config, seed, 'confirmation') for seed in manifest['confirmation_seeds']]
        summary[family] = {
            'heldout_success_mean': statistics.mean(r['heldout']['success'] for r in batch),
            'heldout_success_by_seed': [r['heldout']['success'] for r in batch],
            'heldout_length_mean': statistics.mean(r['heldout']['length'] for r in batch),
            'curve_success_mean': statistics.mean(p['success'] for r in batch for p in r['curve']),
            'seconds_mean': statistics.mean(r['seconds_including_curve_eval'] for r in batch),
            'left_mean': statistics.mean(r['heldout']['left'] for r in batch),
            'right_mean': statistics.mean(r['heldout']['right'] for r in batch),
        }
    contrast = None
    if args.study == 'even-control':
        curves = {(r['family'], r['seed']): statistics.mean(p['success'] for p in r['curve'])
                  for r in runs if r['phase'] == 'confirmation'}
        deltas = [(curves['odd_plus', seed] + curves['odd_minus', seed])/2
                  - curves['even', seed] for seed in confirmation_seeds]
        rng = random.Random(731)
        bootstrap = sorted(statistics.mean(rng.choices(deltas, k=len(deltas)))
                           for _ in range(20000))
        contrast = dict(odd_minus_even_mean=statistics.mean(deltas), by_seed=deltas,
                        percentile_interval_95=[bootstrap[500], bootstrap[19499]],
                        method='paired seed bootstrap, 20000 resamples, RNG seed 731',
                        caveat='conditional on discovery-selected settings; not an equivalence test')
    output = dict(primary_contrast=contrast, manifest=manifest, selected=selected, summary=summary, runs=runs,
                  total_wall_seconds=time.monotonic() - started,
                  limitation='Diagnostic only; no PPO runs, causal amplification claim, or broad transfer.')
    args.output.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'runs': len(runs), 'primary_contrast': contrast, 'summary': summary,
                      'total_wall_seconds': output['total_wall_seconds']}, indent=2))


if __name__ == '__main__':
    main()
