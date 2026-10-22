"""Predeclared CPU PPO ablations on the additive native adversarial variant."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time
import numpy as np
import torch
from torch import nn
from torch.distributions import Categorical

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ACTIONS = np.array([(o,t,p) for o in range(10) for t in range(4) for p in range(5)], np.float32)
ARMS = {'control':(0,False,False), 'abandon_charge':(1,False,False),
        'no_cost':(2,False,False), 'feedback':(3,False,False),
        'exploration':(3,True,False), 'curriculum':(3,True,True)}
NAMES = ['accuracy','actual_gain','reward','cost','invalid','retained','rounds',
         'abandoned','scored_gain','shaping','last_valid','goal']

def build(output):
    path = output/'study.so'
    command = [os.environ.get('CC','cc'), '-shared','-fPIC','-O2',
               '-fvisibility=hidden','-ffunction-sections','-fdata-sections',
               '-Wl,--gc-sections','-Wl,--no-undefined','-D_POSIX_C_SOURCE=200809L',
               '-I'+str(ROOT/'src'), '-I'+os.environ.get('RAYLIB_INCLUDE',str(ROOT/'raylib-5.5_linux_amd64/include')),
               str(HERE/'bridge.c'),'-lm','-o',str(path)]
    subprocess.run(command,check=True)
    lib=ctypes.CDLL(str(path))
    arr=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS')
    lib.study_create.argtypes=[ctypes.c_int]*3+[ctypes.c_uint]+[ctypes.c_int]*2+[arr]*4
    lib.study_create.restype=ctypes.c_void_p
    lib.study_step.argtypes=[ctypes.c_void_p,arr,arr]
    lib.study_free.argtypes=[ctypes.c_void_p]
    lib.study_curriculum.argtypes=[ctypes.c_void_p,ctypes.c_int]
    return lib,command

class World:
    def __init__(self,lib,n,family,shift,seed,mode,curriculum=False):
        self.lib=lib; self.obs=np.zeros((n,52),np.float32)
        self.actions=np.zeros((n,3),np.float32)
        self.reward=np.zeros(n,np.float32);self.done=np.zeros(n,np.float32)
        self.metrics=np.zeros((n,12),np.float32);self.valid=np.zeros(n,np.float32)
        self.ptr=lib.study_create(n,family,shift,seed,mode,curriculum,self.obs,self.actions,self.reward,self.done)
    def step(self,a):
        self.actions[:]=a;self.lib.study_step(self.ptr,self.metrics,self.valid)
    def close(self):self.lib.study_free(self.ptr)

# Same canonical representation in all arms; optional exploration masks legal
# operations using public observations only. No mask depends on the goal bits.
CANONICAL = [(0,t,0) for t in range(4)]+[(1,t,0) for t in range(4)]+[(2,t,p) for t in range(4) for p in range(2)]+[(3,t,0) for t in range(4)]+[(4,t,p) for t in range(3) for p in range(4)]+[(4,0,4)]+[(5,t,p) for t in range(3) for p in range(3)]+[(6,0,0)]+[(7,t,0) for t in range(3)]+[(8,0,0),(9,0,0),(9,1,0)]
CANONICAL_IDS=[o*20+t*5+p for o,t,p in CANONICAL]

def mask(obs):
    m=torch.zeros((len(obs),200),dtype=torch.bool)
    for idx,(o,t,p) in zip(CANONICAL_IDS,CANONICAL):
        ok=torch.ones(len(obs),dtype=torch.bool)
        if o==0 and t==2:ok=obs[:,21]>0
        if o==3:ok=obs[:,18+t]>0
        if o==5:
            ok=obs[:,18]>0
            if p:ok=ok & (obs[:,18+p]>0) & (obs[:,45+p]>0)
        if o==6:ok=obs[:,21]>0
        if o==7:
            ok=(obs[:,26:30].sum(-1)==0)
            if t!=1:ok=ok & (obs[:,8]>0)
            if t!=0:ok=ok & (obs[:,9]>0)
        m[:,idx]=ok
    return m

class Policy(nn.Module):
    def __init__(self,exploration):
        super().__init__();self.exploration=exploration
        self.body=nn.Sequential(nn.Linear(52,128),nn.Tanh(),nn.Linear(128,128),nn.Tanh())
        self.actor=nn.Linear(128,200);self.critic=nn.Linear(128,1)
        for x in self.modules():
            if isinstance(x,nn.Linear):nn.init.orthogonal_(x.weight,np.sqrt(2));nn.init.zeros_(x.bias)
        nn.init.orthogonal_(self.actor.weight,.01);nn.init.orthogonal_(self.critic.weight,1)
    def forward(self,obs,action=None):
        h=self.body(obs);logits=self.actor(h)
        if self.exploration:logits=logits.masked_fill(~mask(obs),-1e9)
        d=Categorical(logits=logits)
        a=d.sample() if action is None else action
        return a,d.log_prob(a),d.entropy(),self.critic(h).squeeze(-1),d.probs

def scripted(obs,universal=False):
    result=[]
    for o in obs:
        if o[18]==0:a=(1,0,0)
        elif np.any(o[30:34]<0):a=(0,0,0)
        else:
            wrong=np.flatnonzero(o[30:34] != (np.ones(4) if universal else o[48:52]))
            if len(wrong):a=(4,0,int(wrong[0]))
            elif not o[8]:a=(5,0,0)
            elif np.any(o[34:38]<0):a=(0,1,0)
            elif np.any(o[34:38]!=o[30:34]):a=(7,0,0)
            else:a=(9,0,0)
        result.append(a)
    return np.asarray(result,np.float32)

@torch.no_grad()
def evaluate(policy,lib,n,seed,mode,baseline=None):
    rows=[]
    with torch.random.fork_rng():
        torch.manual_seed(seed); rng=np.random.default_rng(seed)
        for family in range(3):
            for shift in range(2):
                w=World(lib,n,family,shift,seed+family*10000,mode)
                alive=np.ones(n,bool);data=np.zeros((n,12));length=np.zeros(n,int)
                stages=np.zeros(n,int);sequences=np.zeros(n,int);first=np.zeros(n)
                counts=np.zeros(10,int);prob=np.zeros(10);valid=0;steps=0;examples=[]
                for t in range(96):
                    if baseline in ('scripted','universal'):a=scripted(w.obs,baseline=='universal');probs=None
                    elif baseline=='random':a=ACTIONS[rng.integers(200,size=n)];probs=None
                    elif baseline=='budget_random':
                        # Equal 96-unit cap, valid canonical choices, no privileged task information.
                        m=mask(torch.from_numpy(w.obs));a=ACTIONS[torch.multinomial(m.float(),1).squeeze(1).numpy()];probs=None
                    elif baseline=='abandon':a=np.tile([9,1,0],(n,1));probs=None
                    else:
                        ix,_,_,_,pr=policy(torch.from_numpy(w.obs));a=ACTIONS[ix.numpy()]
                        probs=pr.reshape(n,10,4,5).sum((2,3)).numpy()
                        if t==0:first[:]=pr[:,185:190].sum(-1).numpy()
                    active=alive.copy();length[active]+=1;steps+=active.sum()
                    counts+=np.bincount(a[active,0].astype(int),minlength=10)
                    if probs is not None:prob+=probs[active].sum(0)
                    if len(examples)<32:examples.append(a[0].astype(int).tolist())
                    w.step(a);valid+=((w.valid>0)&active).sum()
                    # Ordered valid modify -> test candidate -> retain candidate, invalidated by
                    # subsequent modify/revert; a checker or strategy edit is not a procedure edit.
                    for i in np.flatnonzero(active & (w.valid>0)):
                        op,target,param=a[i].astype(int)
                        if op==4:stages[i]=1 if target==0 else 0
                        elif op==8:stages[i]=0
                        elif op==5 and target==0 and stages[i]==1:stages[i]=2
                        elif op==7 and target!=1:
                            sequences[i]+=stages[i]==2;stages[i]=0
                    ended=active & (w.done>0);data[ended]=w.metrics[ended];alive[ended]=False
                    if not alive.any():break
                assert not alive.any()
                gain=data[:,1]
                row={name:float(data[:,j].mean()) for j,name in enumerate(NAMES[:10])}
                row.update(family=family,shift=shift,episodes=n,positive_gain=float((gain>0).mean()),
                           gain_se=float(gain.std(ddof=1)/np.sqrt(n)),steps=float(length.mean()),
                           immediate_abandon=float(((length==1)&(data[:,7]>0)).mean()),
                           valid_fraction=float(valid/steps),repair_sequences=float(sequences.mean()),
                           initial_abandon_probability=float(first.mean()) if baseline is None else None,
                           operation_frequency=(counts/steps).tolist(),
                           operation_probability=(prob/steps).tolist() if baseline is None else None,
                           first_lane_prefix=examples)
                rows.append(row);w.close()
    return rows

def train(lib,arm,seed,steps,out):
    mode,explore,curriculum=ARMS[arm]
    torch.manual_seed(seed);np.random.seed(seed)
    policy=Policy(explore);optimizer=torch.optim.Adam(policy.parameters(),lr=3e-4,eps=1e-5)
    n,h,epochs,mb=256,64,4,2048;batch=n*h;updates=steps//batch
    w=World(lib,n,-1,0,seed,mode,curriculum)
    obs=torch.zeros(h,n,52);actions=torch.zeros(h,n,dtype=torch.long)
    logps=torch.zeros(h,n);rewards=torch.zeros(h,n);dones=torch.zeros(h,n);values=torch.zeros(h,n)
    adv=torch.zeros(h,n);trace=[];start=time.perf_counter()
    for u in range(updates):
        # Curriculum ends halfway; every final evaluation uses full tasks.
        lib.study_curriculum(w.ptr,int(curriculum and u<updates//2))
        optimizer.param_groups[0]['lr']=3e-4*(1-u/updates)
        metrics=[];ops=np.zeros(10);abandon_probability=0;valid=0
        for t in range(h):
            obs[t].copy_(torch.from_numpy(w.obs))
            with torch.no_grad():a,lp,_,v,pr=policy(obs[t])
            actions[t],logps[t],values[t]=a,lp,v
            abandon_probability+=float(pr[:,185:190].sum())
            native=ACTIONS[a.numpy()];ops+=np.bincount(native[:,0].astype(int),minlength=10)
            w.step(native);valid+=(w.valid>0).sum()
            rewards[t].copy_(torch.from_numpy(w.reward));dones[t].copy_(torch.from_numpy(w.done))
            metrics.extend(w.metrics[w.done>0].copy())
        with torch.no_grad():
            _,_,_,nv,_=policy(torch.from_numpy(w.obs));last=torch.zeros(n)
            for t in reversed(range(h)):
                following=nv if t==h-1 else values[t+1];live=1-dones[t]
                last=rewards[t]+.99*following*live-values[t]+.99*.95*live*last;adv[t]=last
            returns=adv+values
        bo,ba,bl,badv,br=obs.reshape(-1,52),actions.flatten(),logps.flatten(),adv.flatten(),returns.flatten()
        for _ in range(epochs):
            perm=torch.randperm(batch)
            for s in range(0,batch,mb):
                ix=perm[s:s+mb];_,lp,ent,v,_=policy(bo[ix],ba[ix]);ratio=(lp-bl[ix]).exp()
                advantage=(badv[ix]-badv[ix].mean())/(badv[ix].std(unbiased=False)+1e-8)
                loss=torch.maximum(-advantage*ratio,-advantage*ratio.clamp(.8,1.2)).mean()+.25*((v-br[ix])**2).mean()-.01*ent.mean()
                assert torch.isfinite(loss);optimizer.zero_grad();loss.backward()
                nn.utils.clip_grad_norm_(policy.parameters(),.5);optimizer.step()
        d=np.asarray(metrics)
        row=dict(update=u+1,transitions=(u+1)*batch,episodes=len(d),seconds=time.perf_counter()-start,
                 abandon_probability=abandon_probability/batch,operation_frequency=(ops/batch).tolist(),valid_fraction=float(valid/batch))
        if len(d):row.update({name:float(d[:,j].mean()) for j,name in enumerate(NAMES[:10])})
        trace.append(row)
        if u%16==0:print(arm,seed,u,row.get('actual_gain'),flush=True)
    w.close();torch.save(policy.state_dict(),out/f'{arm}-{seed}.pt')
    (out/f'{arm}-{seed}-trace.json').write_text(json.dumps(trace,indent=2)+'\n')
    return policy,time.perf_counter()-start

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--steps',type=int,default=1048576);p.add_argument('--seeds',type=int,nargs='+',default=[7,19,41])
    p.add_argument('--episodes',type=int,default=128);p.add_argument('--arms',nargs='+',choices=ARMS,default=list(ARMS))
    args=p.parse_args();assert args.steps>0 and args.steps%16384==0
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    sources=[HERE/'variant.h',HERE/'bridge.c',HERE/'run.py',ROOT/'ocean/procedure_lab/procedure_lab.h']
    plan=dict(steps=args.steps,seeds=args.seeds,episodes_per_condition=args.episodes,arms={k:ARMS[k] for k in args.arms},
              evaluation_seed=910007,evaluation='final checkpoint only, full difficulty, six conditions, no selection',
              gamma=.99,gae_lambda=.95,entropy=.01,lr=.0003,clip=.2,epochs=4,minibatch=2048,
              environments=256,horizon=64,threads=2,torch=torch.__version__,numpy=np.__version__,platform=platform.platform(),
              sources={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sources})
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    lib,command=build(out);(out/'build.json').write_text(json.dumps(command,indent=2)+'\n')
    results={}
    for name in ['scripted','universal','random','budget_random','abandon']:
        results[name]=evaluate(None,lib,args.episodes,910007,0,name)
    (out/'baselines.json').write_text(json.dumps(results,indent=2)+'\n')
    for arm in args.arms:
        for seed in args.seeds:
            policy,seconds=train(lib,arm,seed,args.steps,out)
            data=dict(arm=arm,seed=seed,seconds=seconds,conditions=evaluate(policy,lib,args.episodes,910007,ARMS[arm][0]))
            (out/f'{arm}-{seed}-results.json').write_text(json.dumps(data,indent=2)+'\n')
            print(json.dumps({k:v for k,v in data.items() if k!='conditions'}),flush=True)

if __name__=='__main__':main()
