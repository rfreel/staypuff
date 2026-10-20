#!/usr/bin/env python3
"""Validate and summarize development Beads DAG (separate from runtime Beads)."""
import argparse, json, collections
from pathlib import Path

PATH=Path(__file__).resolve().parent.parent/'planning/beads.json'
VALID={'complete','partial','planned','blocked'}

def inspect(data):
    nodes=data['nodes']
    ids=[n['id'] for n in nodes]
    if len(set(ids)) != len(ids):raise ValueError('duplicate Beads ID')
    found={n['id']:n for n in nodes}
    for n in nodes:
        if n['status'] not in VALID:raise ValueError('invalid task status')
        if not n.get('acceptance'):raise ValueError('missing acceptance')
        for p in n['depends_on']:
            if p not in found:raise ValueError(f'unknown predecessor {p} for {n["id"]}')
    status={x:0 for x in VALID}
    color={i:0 for i in ids}
    def visit(i):
        if color[i] == 1:raise ValueError('cycle in development Beads')
        if color[i] == 2:return
        color[i]=1
        for p in found[i]['depends_on']:visit(p)
        color[i]=2
    for i in ids:visit(i)
    for n in nodes:status[n['status']]+=1
    return {'total_beads':len(nodes),'dependency_edges':sum(len(n['depends_on']) for n in nodes),
            'status':status,'groups':dict(sorted(collections.Counter(n['id'].split('.')[0] for n in nodes).items()))}

def main():
    p=argparse.ArgumentParser();p.add_argument('--json',action='store_true');args=p.parse_args()
    data=json.loads(PATH.read_text())
    summary=inspect(data)
    if args.json:print(json.dumps(summary,indent=2))
    else:
        print(f"DEVELOPMENT BEADS {summary['total_beads']} nodes / {summary['dependency_edges']} dependencies / ACYCLIC")
        for key,count in summary['status'].items():print(f'  {key:10} {count:>4}')
        print('  groups',len(summary['groups']))

if __name__=='__main__':main()
