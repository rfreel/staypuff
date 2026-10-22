"""Read-only replay of the preserved pilot checkpoint; never trains or overwrites it."""
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
import torch
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('pilot',HERE.parent/'ppo.py')
pilot=importlib.util.module_from_spec(spec);spec.loader.exec_module(pilot)
out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
os.chdir(ROOT);torch.set_num_threads(2)
subprocess.run(['cc','-shared','-fPIC','-O2','-fvisibility=hidden','-ffunction-sections','-fdata-sections',
                '-Wl,--gc-sections','-Wl,--no-undefined','-D_POSIX_C_SOURCE=200809L','-Isrc',
                '-I'+os.environ.get('RAYLIB_INCLUDE','raylib-5.5_linux_amd64/include'),
                str(HERE.parent/'ppo_bridge.c'),'-lm','-o',str(out/'original.so')],check=True)
lib=ctypes.CDLL(str(out/'original.so'));arr=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS')
lib.lab_create.argtypes=[ctypes.c_int]*3+[ctypes.c_uint]+[arr]*4;lib.lab_create.restype=ctypes.c_void_p
lib.lab_step.argtypes=[ctypes.c_void_p,arr];lib.lab_free.argtypes=[ctypes.c_void_p]
policy=pilot.Policy();policy.load_state_dict(torch.load(HERE.parent/'ppo-run/policy.pt',weights_only=True))
result=pilot.evaluate(policy,lib,1000,910007)
probabilities=[]
with torch.no_grad():
    for family in range(3):
        for shift in range(2):
            w=pilot.World(lib,1000,family,shift,1910007+family*10000)
            heads=policy.actor(policy.body(torch.from_numpy(w.obs))).split([10,4,5],-1)
            op,target,param=[x.softmax(-1) for x in heads]
            probabilities.append(dict(family=family,shift=shift,
                initial_abandon_probability=float((op[:,9]*target[:,1]).mean()),
                operation_probability=op.mean(0).tolist(),target_probability=target.mean(0).tolist()))
            w.close()
recorded=json.loads((HERE.parent/'ppo-run/results.json').read_text())['after']
assert result==recorded,(result,recorded)
(out/'results.json').write_text(json.dumps(dict(replay_matches_recorded_after=True,evaluation=result,held_out_reset_probabilities=probabilities),indent=2)+'\n')
print('Preserved final checkpoint exactly reproduces all six recorded evaluation conditions.')
