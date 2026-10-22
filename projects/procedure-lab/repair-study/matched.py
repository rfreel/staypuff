"""Replay final policies and match each baseline's per-task operation-cost cap.

Stops baselines before overspending, scores the retained procedure without adding
an action or reward, and uses identical task seeds. No baseline sees final cases.
"""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
import torch
import run

COSTS=np.array([1,4,1,2,2,4,4,1,1,1])

@torch.no_grad()
def collect(lib,policy,n,seed,family,shift,mode,baseline=None,caps=None):
    torch.manual_seed(seed);rng=np.random.default_rng(seed)
    w=run.World(lib,n,family,shift,seed+family*10000,mode)
    alive=np.ones(n,bool);spent=np.zeros(n);data=np.zeros((n,12))
    for _ in range(97):
        if baseline=='scripted':a=run.scripted(w.obs)
        elif baseline=='random':a=run.ACTIONS[rng.integers(200,size=n)]
        elif baseline=='valid_random':
            a=run.ACTIONS[torch.multinomial(run.mask(torch.from_numpy(w.obs)).float(),1).squeeze(1).numpy()]
        else:
            ix,*_=policy(torch.from_numpy(w.obs));a=run.ACTIONS[ix.numpy()]
        cost=np.minimum(COSTS[a[:,0].astype(int)],96-spent)
        if caps is not None:
            stop=alive & (spent+cost>caps)
            if stop.any():
                snapshot=np.zeros((n,12),np.float32);lib.study_snapshot(w.ptr,snapshot)
                data[stop]=snapshot[stop];alive[stop]=False
        if not alive.any():break
        active=alive.copy();spent[active]+=cost[active];w.step(a)
        ended=active & (w.done>0);data[ended]=w.metrics[ended];alive[ended]=False
        if not alive.any():break
    assert not alive.any();w.close()
    return data

def main():
    p=argparse.ArgumentParser();p.add_argument('study',type=Path);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    plan=json.loads((args.study/'plan.json').read_text())
    (out/'plan.json').write_text(json.dumps(dict(evaluation_seed=1910007,episodes=plan['episodes_per_condition'],
        rule='all final checkpoints; per-episode cost caps from policy on identical seeds; read-only final scoring',
        sources={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__),run.HERE/'budget_bridge.c',run.HERE/'run.py',run.HERE/'bridge.c',run.HERE/'variant.h')}),indent=2)+'\n')
    _,command=run.build(out);command[command.index(str(run.HERE/'bridge.c'))]=str(run.HERE/'budget_bridge.c')
    command[-1]=str(out/'budget.so');subprocess.run(command,check=True)
    lib=ctypes.CDLL(str(out/'budget.so'))
    arr=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS')
    lib.study_create.argtypes=[ctypes.c_int]*3+[ctypes.c_uint]+[ctypes.c_int]*2+[arr]*4;lib.study_create.restype=ctypes.c_void_p
    lib.study_step.argtypes=[ctypes.c_void_p,arr,arr];lib.study_free.argtypes=[ctypes.c_void_p]
    lib.study_snapshot.argtypes=[ctypes.c_void_p,arr]
    for arm in plan['arms']:
        for seed in plan['seeds']:
            policy=run.Policy(run.ARMS[arm][1]);policy.load_state_dict(torch.load(args.study/f'{arm}-{seed}.pt',weights_only=True))
            rows=[];raw=[]
            for family in range(3):
                for shift in range(2):
                    evaluated=collect(lib,policy,plan['episodes_per_condition'],1910007,family,shift,run.ARMS[arm][0])
                    pairs={'learned':evaluated}
                    for baseline in ('scripted','random','valid_random'):
                        pairs[baseline]=collect(lib,None,len(evaluated),1910007,family,shift,run.ARMS[arm][0],baseline,evaluated[:,3])
                    for name,d in pairs.items():
                        assert np.all(d[:,3]<=evaluated[:,3]+1e-6)
                        delta=d[:,1]-evaluated[:,1]
                        rows.append(dict(family=family,shift=shift,policy=name,actual_gain=float(d[:,1].mean()),
                                         accuracy=float(d[:,0].mean()),cost=float(d[:,3].mean()),
                                         paired_gain_minus_learned=float(delta.mean()),paired_se=float(delta.std(ddof=1)/np.sqrt(len(d)))))
                        raw.append(dict(family=family,shift=shift,policy=name,columns=run.NAMES,episodes=d.tolist()))
            (out/f'{arm}-{seed}.json').write_text(json.dumps(dict(summary=rows,raw=raw),separators=(',',':'))+'\n')
            print(arm,seed,'matched evaluation complete',flush=True)

if __name__=='__main__':main()
