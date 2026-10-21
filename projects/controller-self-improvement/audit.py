#!/usr/bin/env python3
"""Verify stored witnesses, score arithmetic, budgets, and deterministic replay."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from controller import search
from experiment import ARMS, BUDGETS, CHAINS, TASKS, N, Oracle, graph, direct, hashes

out = Path(sys.argv[1])
manifest = json.loads((out/'manifest.json').read_text())
assert manifest['hashes'] == hashes()
seed = json.loads((out/'evaluation-seed.json').read_text())
assert seed['controllers_sha256'] == hashlib.sha256((out/'controllers.json').read_bytes()).hexdigest()
chains = json.loads((out/'controllers.json').read_text())
tasks = json.loads((out/'tasks.json').read_text())
summary = json.loads((out/'summary.json').read_text())
# Closed-form optima on two different graph families.
assert Oracle([(i,j,1) for i in range(N) for j in range(i+1,N)]).optimum == N*N//4
assert Oracle([(i,(i+1)%N,1) for i in range(N)]).optimum == N
worlds = [Oracle(graph(s,tasks['densities'][t])) for t,s in enumerate(tasks['task_seeds'])]
seen, totals = set(), {a:0 for a in ARMS}
scores = np.zeros((CHAINS,TASKS,len(ARMS)))
for line in (out/'evaluation.jsonl').read_text().splitlines():
    r = json.loads(line)
    key = (r['chain'],r['task'],r['arm'])
    assert key not in seen
    seen.add(key)
    world = worlds[r['task']]
    value = direct(r['witness'],world.edges)
    assert 0 <= r['witness'] < (1 << N)
    assert value == r['cut'] and world.optimum == r['optimum']
    assert r['score'] == value/world.optimum
    assert r['calls'] == BUDGETS[r['arm']]
    totals[r['arm']] += r['calls']
    scores[r['chain'],r['task'],ARMS.index(r['arm'])] = r['score']
assert len(seen) == CHAINS*TASKS*len(ARMS)
dev_witnesses = 0
for c in chains:
    for rec in c['cycles']:
        cycle = rec['cycle']-1
        refs = [Oracle(graph(31415926+c['chain']*1000+cycle*100+k,(.2,.5,.8)[k%3])) for k in range(8)]
        assert len(rec['attempts']) == 24 and rec['calls'] == 24576
        for attempt in rec['attempts']:
            for k,(x,s) in enumerate(zip(attempt['witnesses'],attempt['scores'])):
                assert 0 <= x < (1 << N)
                assert direct(x,refs[k].edges)/refs[k].optimum == s
                dev_witnesses += 1
            assert sum(attempt['scores'])/8 == attempt['score']
        # Replay controller decisions from saved outcomes, including every proposal.
        cursor = [0]
        def recorded_score(config):
            row = rec['attempts'][cursor[0]]
            assert row['config'] == config
            cursor[0] += 1
            return row['score']
        replay = search(rec['meta'],12,24,recorded_score,
                        700000+c['chain']*100+cycle,initial=rec['initial'])
        assert replay['config'] == rec['winner'] and replay['score'] == rec['score']
        assert cursor[0] == 24
    one,two,fixed = c['cycles']
    assert one['meta'] == 0 and two['meta'] == one['winner'] and fixed['meta'] == 0
    assert two['initial'] == fixed['initial'] == one['winner']
    assert (c['gen1'],c['gen2'],c['frozen_meta']) == (one['winner'],two['winner'],fixed['winner'])
    totals['gen1'] += one['calls']
    totals['gen2'] += one['calls']+two['calls']
    totals['frozen_meta'] += one['calls']+fixed['calls']
for i,a in enumerate(ARMS):
    assert totals[a] == CHAINS*TASKS*1024 == summary['arms'][a]['total_assignment_calls']
    assert float(scores[:,:,i].mean()) == summary['arms'][a]['mean_score']
    assert float((scores[:,:,i]==1).mean()) == summary['arms'][a]['optimum_rate']
print(json.dumps(dict(deployment_witnesses=len(seen),development_witnesses=dev_witnesses,
    exact_reference_graphs=len(worlds),controller_replays=CHAINS*3,
    closed_form_reference_checks=2,assignment_calls_per_arm=totals,
    result='PASS'),indent=2))
