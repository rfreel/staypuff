#!/usr/bin/env python3
"""One-shot, cost-accounted controller self-configuration experiment."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import random
import secrets
import subprocess
import sys
import time
import numpy as np
from controller import search, random_search

HERE = Path(__file__).resolve().parent
ARMS = ['base', 'random', 'gen1', 'gen2', 'frozen_meta']
BUDGETS = dict(base=1024, random=1024, gen1=768, gen2=512, frozen_meta=512)
CHAINS, TASKS, N = 16, 96, 18


def dump(path, data):
    with path.open('x') as out:
        json.dump(data, out, indent=2)
        out.write('\n')


def hashes():
    return {p: hashlib.sha256((HERE / p).read_bytes()).hexdigest()
            for p in ['PROTOCOL.md', 'controller.py', 'experiment.py']}


def graph(seed, density, n=N):
    rng = random.Random(seed)
    edges = {(i, j): rng.randint(1, 9) for i in range(n) for j in range(i+1, n)
             if rng.random() < density}
    for i in range(n):
        pair = tuple(sorted((i, (i+1) % n)))
        edges[pair] = edges.get(pair, 0) + 1
    return [(i, j, w) for (i, j), w in sorted(edges.items())]


def direct(x, edges):
    return sum(w for i, j, w in edges if bool(x & (1 << i)) != bool(x & (1 << j)))


class Oracle:
    def __init__(self, edges, n=N):
        self.edges, self.n, self.calls = edges, n, 0
        states = np.arange(1 << (n-1), dtype=np.uint32) << 1
        values = np.zeros(len(states), dtype=np.int32)
        for i, j, w in edges:
            values += (((states >> i) ^ (states >> j)) & 1).astype(np.int32) * w
        self.values = values
        self.optimum = int(values.max())
        self.optimum_witness = int(values.argmax()) << 1
        if direct(self.optimum_witness, edges) != self.optimum:
            raise RuntimeError('invalid optimum witness')

    def score(self, x):
        if not 0 <= x < (1 << self.n):
            raise ValueError('invalid partition')
        self.calls += 1
        canonical = x ^ ((1 << self.n)-1) if x & 1 else x
        return int(self.values[canonical >> 1]) / self.optimum

    def check(self, result):
        x = result['config']
        actual = direct(x, self.edges)
        if not 0 <= x < (1 << self.n) or actual / self.optimum != result['score']:
            raise RuntimeError('witness mismatch')
        return actual


def calibrate():
    count = 0
    for n in range(3, 10):
        for density in (.2, .5, .8):
            edges = graph(1000+n, density, n)
            ref = Oracle(edges, n)
            exhaustive = [direct(x, edges) for x in range(1 << n)]
            if max(exhaustive) != ref.optimum:
                raise RuntimeError('optimum disagreement')
            for x, value in enumerate(exhaustive):
                if ref.score(x) != value / ref.optimum:
                    raise RuntimeError('score disagreement')
                count += 1
    return count


def develop(out):
    if out.exists():
        raise RuntimeError('Refusing to overwrite experiment')
    out.mkdir()
    manifest = dict(hashes=hashes(), base_commit=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=HERE, text=True).strip(),
        python=sys.version, numpy=np.__version__, platform=platform.platform(),
        chains=CHAINS, tasks=TASKS, budgets=BUDGETS, development_seed=31415926)
    dump(out / 'manifest.json', manifest)
    print('Manifest frozen', manifest['hashes'], flush=True)
    calibration = calibrate()
    dump(out / 'calibration.json', dict(partitions_checked=calibration))
    chains = []
    reference_seconds = 0
    for chain in range(CHAINS):
        entry = dict(chain=chain, cycles=[])
        winner = 0
        for cycle in range(2):
            started = time.perf_counter()
            worlds = [Oracle(graph(31415926 + chain*1000 + cycle*100 + k,
                                   (.2, .5, .8)[k % 3])) for k in range(8)]
            reference_seconds += time.perf_counter() - started
            seed = 700000 + chain*100 + cycle
            frozen_start = winner
            treatments = [('adaptive', winner if cycle else 0)]
            if cycle:
                treatments.append(('frozen_meta', 0))
            for treatment, meta in treatments:
                for world in worlds:
                    world.calls = 0
                records = []
                def fitness(config):
                    scores, witnesses = [], []
                    for k, world in enumerate(worlds):
                        result = search(config, N, 128, world.score, seed*100+k)
                        world.check(result)
                        scores.append(result['score'])
                        witnesses.append(result['config'])
                    value = sum(scores)/len(scores)
                    records.append(dict(config=config, score=value, scores=scores,
                                        witnesses=witnesses))
                    return value
                started = time.perf_counter()
                result = search(meta, 12, 24, fitness, seed, initial=frozen_start,
                                trace=True)
                seconds = time.perf_counter()-started
                calls = sum(w.calls for w in worlds)
                if calls != 24576 or len(records) != 24:
                    raise RuntimeError('development budget mismatch')
                record = dict(cycle=cycle+1, treatment=treatment, meta=meta,
                              initial=frozen_start, winner=result['config'],
                              score=result['score'], calls=calls, seconds=seconds,
                              attempts=records)
                entry['cycles'].append(record)
                if treatment == 'adaptive':
                    winner = result['config']
                    entry['gen'+str(cycle+1)] = winner
                else:
                    entry['frozen_meta'] = result['config']
            print('chain', chain, 'cycle', cycle+1, 'winner', winner, flush=True)
        chains.append(entry)
    # The complete controller set is written BEFORE the held-out seed exists.
    dump(out / 'controllers.json', chains)
    dump(out / 'development.json', dict(reference_seconds=reference_seconds,
                                       calibration_partitions=calibration))
    seed = secrets.randbits(256)
    dump(out / 'evaluation-seed.json', dict(seed=str(seed),
         controllers_sha256=hashlib.sha256((out/'controllers.json').read_bytes()).hexdigest()))


def evaluate(out):
    manifest = json.loads((out/'manifest.json').read_text())
    if manifest['hashes'] != hashes():
        raise RuntimeError('source differs from frozen manifest')
    seed_record = json.loads((out/'evaluation-seed.json').read_text())
    if seed_record['controllers_sha256'] != hashlib.sha256((out/'controllers.json').read_bytes()).hexdigest():
        raise RuntimeError('controllers changed after evaluation seed')
    if (out/'evaluation.jsonl').exists():
        raise RuntimeError('Refusing to repeat held-out evaluation')
    chains = json.loads((out/'controllers.json').read_text())
    rng = random.Random(int(seed_record['seed']))
    task_seeds = [rng.getrandbits(128) for _ in range(TASKS)]
    solver_seeds = [[rng.getrandbits(128) for _ in range(TASKS)] for _ in range(CHAINS)]
    dump(out/'tasks.json', dict(task_seeds=task_seeds, solver_seeds=solver_seeds,
                               densities=[(.2,.5,.8)[t%3] for t in range(TASKS)]))
    started = time.perf_counter()
    worlds = [Oracle(graph(seed, (.2,.5,.8)[t%3])) for t, seed in enumerate(task_seeds)]
    reference_seconds = time.perf_counter()-started
    scores = np.zeros((CHAINS,TASKS,len(ARMS)))
    times = {a:0.0 for a in ARMS}
    with (out/'evaluation.jsonl').open('x') as stream:
        for c, entry in enumerate(chains):
            for t, world in enumerate(worlds):
                shift = (c+t) % len(ARMS)
                order = ARMS[shift:]+ARMS[:shift]
                for arm in order:
                    world.calls = 0
                    started = time.perf_counter()
                    if arm == 'random':
                        result = random_search(N, BUDGETS[arm], world.score, solver_seeds[c][t])
                    else:
                        config = 0 if arm == 'base' else entry[arm]
                        result = search(config, N, BUDGETS[arm], world.score, solver_seeds[c][t])
                    seconds = time.perf_counter()-started
                    value = world.check(result)
                    if world.calls != BUDGETS[arm]:
                        raise RuntimeError('deployment budget mismatch')
                    scores[c,t,ARMS.index(arm)] = result['score']
                    times[arm] += seconds
                    stream.write(json.dumps(dict(chain=c,task=t,arm=arm,
                        witness=result['config'],cut=value,optimum=world.optimum,
                        score=result['score'],calls=world.calls,seconds=seconds))+'\n')
            stream.flush()
            print('evaluated chain', c, flush=True)
    development_times = {a:0.0 for a in ARMS}
    for entry in chains:
        one,two,fixed = entry['cycles']
        development_times['gen1'] += one['seconds']
        development_times['gen2'] += one['seconds']+two['seconds']
        development_times['frozen_meta'] += one['seconds']+fixed['seconds']
    # Crossed resampling: independent chains and density-stratified shared graphs.
    contrasts = [('gen1','base'),('gen2','gen1'),('gen2','frozen_meta'),('gen2','random')]
    delta = np.stack([scores[:,:,ARMS.index(a)]-scores[:,:,ARMS.index(b)]
                      for a,b in contrasts],axis=2)
    boot = np.empty((10000,4))
    brng = np.random.default_rng(987654321)
    for b in range(len(boot)):
        cs = brng.integers(CHAINS,size=CHAINS)
        ts = np.concatenate([brng.choice(np.arange(d,TASKS,3),TASKS//3) for d in range(3)])
        boot[b] = delta[cs][:,ts].mean(axis=(0,1))
    ci = np.quantile(boot,[.00625,.99375],axis=0)
    contrast_report = {a+'-'+b:dict(mean=float(delta[:,:,i].mean()),
        interval_98_75=ci[:,i].tolist(),passes=bool(ci[0,i]>.002))
        for i,(a,b) in enumerate(contrasts)}
    total_seconds = {a:times[a]+development_times[a] for a in ARMS}
    recursive = all(v['passes'] for v in contrast_report.values())
    report = dict(arms={a:dict(mean_score=float(scores[:,:,i].mean()),
        optimum_rate=float((scores[:,:,i]==1).mean()),
        per_chain_mean=scores[:,:,i].mean(axis=1).tolist(),
        deployment_seconds=times[a],development_seconds=development_times[a],
        total_seconds=total_seconds[a],total_assignment_calls=CHAINS*TASKS*1024)
        for i,a in enumerate(ARMS)},contrasts=contrast_report,
        self_improvement=contrast_report['gen1-base']['passes'],
        recursive_benefit=recursive,
        full_resource_gate=bool(recursive and total_seconds['gen2']<=total_seconds['base']),
        common_heldout_reference_seconds=reference_seconds,
        source_hashes=hashes(),limits='Configuration search only; shared authorship; no weight updates; fixed narrow workload; wall time includes search not common setup/checking.')
    dump(out/'summary.json', report)
    print(json.dumps(report,indent=2),flush=True)


if __name__ == '__main__':
    if not __debug__:
        raise RuntimeError('Run without Python optimization flags')
    parser = argparse.ArgumentParser()
    parser.add_argument('phase',choices=['develop','evaluate'])
    parser.add_argument('--out',type=Path,required=True)
    args = parser.parse_args()
    (develop if args.phase == 'develop' else evaluate)(args.out)
