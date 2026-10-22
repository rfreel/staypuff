"""Exploration control: PPO selects a program; a fixed executor performs legal edits.
This is scaffolded policy learning, not end-to-end operation discovery.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical
import run

class Selector(nn.Module):
    def __init__(self):
        super().__init__();self.body=nn.Sequential(nn.Linear(4,64),nn.Tanh())
        self.actor=nn.Linear(64,16);self.critic=nn.Linear(64,1)
    def forward(self,o):
        h=self.body(o);return Categorical(logits=self.actor(h)),self.critic(h).squeeze(-1)

@torch.no_grad()
def execute(w,programs):
    n=len(programs);alive=np.ones(n,bool);metrics=np.zeros((n,12));returns=np.zeros(n)
    transitions=0
    for t in range(96):
        o=w.obs.copy();o[:,48:52]=(programs[:,None]>>np.arange(4))&1
        actions=run.scripted(o)
        active=alive.copy();transitions+=int(active.sum());w.step(actions)
        returns[active]+=(.99**t)*w.reward[active]
        ended=active & (w.done>0);metrics[ended]=w.metrics[ended];alive[ended]=False
        if not alive.any():break
    assert not alive.any()
    return returns,metrics,transitions

@torch.no_grad()
def evaluate(lib,policy,n,seed,baseline=None):
    torch.manual_seed(seed);rng=np.random.default_rng(seed);rows=[]
    for f in range(3):
        for shifted in range(2):
            w=run.World(lib,n,f,shifted,seed+f*10000,1)
            if baseline=='random_target':programs=rng.integers(16,size=n)
            elif baseline=='scripted':programs=(w.obs[:,48:52]*(2**np.arange(4))).sum(-1).astype(int)
            else:programs=policy(torch.from_numpy(w.obs[:,48:52]))[0].sample().numpy()
            _,d,transitions=execute(w,programs)
            rows.append(dict(family=f,shift=shifted,episodes=n,actual_gain=float(d[:,1].mean()),
                accuracy=float(d[:,0].mean()),reward=float(d[:,2].mean()),cost=float(d[:,3].mean()),
                retained=float(d[:,5].mean()),rounds=float(d[:,6].mean()),
                native_transitions=transitions,positive_gain=float((d[:,1]>0).mean())))
            w.close()
    return rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    plan=dict(seeds=[7,19,41],updates=128,episodes_per_update=256,epochs=4,lr=.003,
        entropy=.01,clip=.2,gamma=.99,eval_episodes=128,eval_seed=2910007,
        method='PPO over 16 program choices; fixed public-observation legal executor; final checkpoint only',
        limitation='4 public contract bits identify the optimal program; not end-to-end discovery or held-out contracts',
        sources={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (Path(__file__),run.HERE/'run.py',run.HERE/'variant.h',run.HERE/'bridge.c')})
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n');lib,_=run.build(out)
    for seed in plan['seeds']:
        torch.manual_seed(seed);model=Selector();optim=torch.optim.Adam(model.parameters(),lr=.003)
        trace=[];start=time.perf_counter();total=0
        for u in range(plan['updates']):
            w=run.World(lib,256,-1,0,seed+u*100003,1)
            obs=torch.from_numpy(w.obs[:,48:52].copy())
            with torch.no_grad():
                dist,value=model(obs);a=dist.sample();oldlog=dist.log_prob(a)
            ret,data,transitions=execute(w,a.numpy());total+=transitions;w.close()
            returns=torch.tensor(ret,dtype=torch.float32);adv=returns-value
            adv=(adv-adv.mean())/(adv.std(unbiased=False)+1e-8)
            for _ in range(4):
                dist,v=model(obs);ratio=(dist.log_prob(a)-oldlog).exp()
                loss=torch.maximum(-adv*ratio,-adv*ratio.clamp(.8,1.2)).mean()+.25*((v-returns)**2).mean()-.01*dist.entropy().mean()
                assert torch.isfinite(loss);optim.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),.5);optim.step()
            trace.append(dict(update=u+1,transitions=total,actual_gain=float(data[:,1].mean()),accuracy=float(data[:,0].mean())))
        torch.save(model.state_dict(),out/f'selector-{seed}.pt')
        results=dict(seed=seed,seconds=time.perf_counter()-start,native_transitions=total,
                     learned=evaluate(lib,model,128,2910007),random_target=evaluate(lib,None,128,2910007,'random_target'),
                     scripted=evaluate(lib,None,128,2910007,'scripted'))
        (out/f'{seed}-results.json').write_text(json.dumps(results,indent=2)+'\n')
        (out/f'{seed}-trace.json').write_text(json.dumps(trace,indent=2)+'\n')
        print(seed,results['seconds'],sum(x['actual_gain'] for x in results['learned'])/6,flush=True)

if __name__=='__main__':main()
