"""Exact per-task cost-cap comparisons for the scaffolded selector."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
import torch
import run
import macro
import matched

p=argparse.ArgumentParser();p.add_argument('study',type=Path);p.add_argument('--output',type=Path,required=True)
args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
(out/'plan.json').write_text(json.dumps(dict(seed=3910007,episodes=128,training_seeds=[7,19,41],
    rule='all checkpoints, identical task streams, exact per-episode native cost ceilings',
    source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),indent=2)+'\n')
_,command=run.build(out);command[command.index(str(run.HERE/'bridge.c'))]=str(run.HERE/'budget_bridge.c')
command[-1]=str(out/'budget.so');subprocess.run(command,check=True)
lib=ctypes.CDLL(str(out/'budget.so'));arr=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS')
lib.study_create.argtypes=[ctypes.c_int]*3+[ctypes.c_uint]+[ctypes.c_int]*2+[arr]*4;lib.study_create.restype=ctypes.c_void_p
lib.study_step.argtypes=[ctypes.c_void_p,arr,arr];lib.study_free.argtypes=[ctypes.c_void_p];lib.study_snapshot.argtypes=[ctypes.c_void_p,arr]
for seed in (7,19,41):
    model=macro.Selector();model.load_state_dict(torch.load(args.study/f'selector-{seed}.pt',weights_only=True))
    torch.manual_seed(3910007);rows=[];raw=[]
    for f in range(3):
        for shift in range(2):
            w=run.World(lib,128,f,shift,3910007+f*10000,1)
            with torch.no_grad():programs=model(torch.from_numpy(w.obs[:,48:52]))[0].sample().numpy()
            _,learned,_=macro.execute(w,programs);w.close()
            pairs={'learned':learned}
            for name in ('scripted','random','valid_random'):
                pairs[name]=matched.collect(lib,None,128,3910007,f,shift,1,name,learned[:,3])
            for name,d in pairs.items():
                assert np.all(d[:,3]<=learned[:,3]+1e-6)
                delta=d[:,1]-learned[:,1]
                rows.append(dict(family=f,shift=shift,policy=name,actual_gain=float(d[:,1].mean()),
                    accuracy=float(d[:,0].mean()),cost=float(d[:,3].mean()),
                    paired_gain_minus_learned=float(delta.mean()),paired_se=float(delta.std(ddof=1)/np.sqrt(len(d)))))
                raw.append(dict(family=f,shift=shift,policy=name,columns=run.NAMES,episodes=d.tolist()))
    (out/f'{seed}.json').write_text(json.dumps(dict(summary=rows,raw=raw),separators=(',',':'))+'\n')
    print(seed,'matched macro complete',flush=True)
