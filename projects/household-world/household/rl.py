"""CPU PPO baseline trained against the authoritative Python household world.

This is a research baseline, NOT a trained universal household assistant.
No PufferLib CUDA toolchain is required. Checkpoints contain ordinary torch tensors.
"""
from __future__ import annotations
import json, math, random, statistics
from dataclasses import dataclass,asdict
from pathlib import Path
import numpy as np
from .world import HouseholdWorld,ACTIONS


def torch_module():
    try:
        import torch
        return torch
    except ImportError as e:
        raise RuntimeError('Install the optional rl extra (torch and numpy)') from e

class ActorCritic:
    def __init__(self,obs_dim:int,n_actions:int,hidden:int=64):
        torch=torch_module()
        self.model=torch.nn.Sequential(
            torch.nn.Linear(obs_dim,hidden),torch.nn.Tanh(),
            torch.nn.Linear(hidden,hidden),torch.nn.Tanh())
        self.actor=torch.nn.Linear(hidden,n_actions)
        self.critic=torch.nn.Linear(hidden,1)
    def parameters(self):
        return list(self.model.parameters())+list(self.actor.parameters())+list(self.critic.parameters())
    def forward(self,x):
        z=self.model(x)
        return self.actor(z),self.critic(z).squeeze(-1)
    def state_dict(self):
        return {'model':self.model.state_dict(),'actor':self.actor.state_dict(),
                'critic':self.critic.state_dict()}
    def load_state_dict(self,s):
        self.model.load_state_dict(s['model'])
        self.actor.load_state_dict(s['actor'])
        self.critic.load_state_dict(s['critic'])


def train_ppo(output:str='artifacts/household_ppo.pt',updates:int=40,n_envs:int=8,
              days:int=14,seed:int=17,lr:float=5e-4,gamma:float=.97,
              clip_ratio:float=.2,epochs:int=3) -> dict:
    torch=torch_module()
    if updates<1 or n_envs<1 or days<2:raise ValueError('invalid training settings')
    torch.set_num_threads(1)
    torch.manual_seed(seed);np.random.seed(seed);random.seed(seed)
    worlds=[HouseholdWorld(seed=seed+i*1009,horizon=days) for i in range(n_envs)]
    net=ActorCritic(worlds[0].observation_dim,len(ACTIONS))
    opt=torch.optim.Adam(net.parameters(),lr=lr,eps=1e-5)
    global_episode=0;history=[]
    for update in range(updates):
        store_obs=[];store_actions=[];store_logp=[];store_values=[];store_rews=[];store_done=[]
        for t in range(days):
            obs=torch.tensor(np.asarray([w.observe() for w in worlds]),dtype=torch.float32)
            with torch.no_grad():
                logits,v=net.forward(obs)
                dist=torch.distributions.Categorical(logits=logits)
                act=dist.sample();lp=dist.log_prob(act)
            reward=[];done=[]
            for i,w in enumerate(worlds):
                _,rew,term,_=w.step(int(act[i]))
                reward.append(rew);done.append(float(term))
                if term:
                    global_episode+=1
                    worlds[i]=HouseholdWorld(seed=seed+100000+global_episode*3571,horizon=days)
            store_obs.append(obs);store_actions.append(act)
            store_logp.append(lp);store_values.append(v)
            store_rews.append(torch.tensor(reward,dtype=torch.float32))
            store_done.append(torch.tensor(done,dtype=torch.float32))
        with torch.no_grad():
            next_obs=torch.tensor(np.asarray([w.observe() for w in worlds]),dtype=torch.float32)
            _,bootstrap=net.forward(next_obs)
            rewards=torch.stack(store_rews)
            values=torch.stack(store_values)
            dones=torch.stack(store_done)
            adv=torch.zeros_like(rewards)
            gae=torch.zeros(n_envs)
            for t in reversed(range(days)):
                next_value=bootstrap if t==days-1 else values[t+1]
                delta=rewards[t]+gamma*(1-dones[t])*next_value-values[t]
                gae=delta+gamma*.95*(1-dones[t])*gae
                adv[t]=gae
            returns=adv+values
        X=torch.stack(store_obs).reshape(-1,worlds[0].observation_dim)
        A=torch.stack(store_actions).reshape(-1)
        LP=torch.stack(store_logp).reshape(-1)
        V=values.reshape(-1)
        ADV=adv.reshape(-1)
        RET=returns.reshape(-1)
        ADV=(ADV-ADV.mean())/(ADV.std(unbiased=False)+1e-8)
        order=np.arange(X.shape[0])
        losses=[]
        for epoch in range(epochs):
            np.random.shuffle(order)
            for start in range(0,len(order),128):
                idx=torch.tensor(order[start:start+128])
                logits,pred_value=net.forward(X[idx])
                dist=torch.distributions.Categorical(logits=logits)
                new_logp=dist.log_prob(A[idx])
                ratio=torch.exp(new_logp-LP[idx])
                actor_loss=-torch.minimum(ratio*ADV[idx],
                    torch.clamp(ratio,1-clip_ratio,1+clip_ratio)*ADV[idx]).mean()
                value_loss=.5*(pred_value-RET[idx]).square().mean()
                entropy=dist.entropy().mean()
                loss=actor_loss+.5*value_loss-.015*entropy
                opt.zero_grad();loss.backward()
                torch.nn.utils.clip_grad_norm_(net.parameters(),.5)
                opt.step();losses.append(float(loss.item()))
        if update%max(1,updates//10)==0 or update==updates-1:
            history.append({'update':update+1,'mean_reward':round(float(rewards.mean()),4),
                            'policy_loss_combined':round(float(statistics.mean(losses)),4)})
    path=Path(output);path.parent.mkdir(parents=True,exist_ok=True)
    torch.save({'state_dict':net.state_dict(),'observation_dim':worlds[0].observation_dim,
                'action_names':list(ACTIONS),'seed':seed,'updates':updates,
                'n_envs':n_envs,'rollout_days':days,'version':'0.2.0'},path)
    return {'checkpoint':str(path),'steps':updates*n_envs*days,
            'episodes':global_episode,'history':history,'algorithm':'CPU PPO',
            'trained_on':'authoritative Python HouseholdWorld synthetic market'}


def load_policy(path:str):
    torch=torch_module()
    torch.set_num_threads(1)  # small CPU inference: avoid thread-launch overhead
    data=torch.load(path,map_location='cpu',weights_only=True)
    if data['action_names'] !=list(ACTIONS):raise ValueError('checkpoint action mismatch')
    net=ActorCritic(data['observation_dim'],len(ACTIONS))
    net.load_state_dict(data['state_dict'])
    return net


def action_from_policy(net,observation:list[float]) -> int:
    torch=torch_module()
    with torch.no_grad():
        logits,_=net.forward(torch.tensor([observation],dtype=torch.float32))
        return int(logits.argmax(dim=-1).item())


def rollout(seed:int=7,days:int=30,action:int|None=0,policy=None,
            weekly_budget_cents:int=14500) -> dict:
    world=HouseholdWorld(seed=seed,horizon=days,weekly_budget_cents=weekly_budget_cents)
    steps=[];total_reward=0.
    while world.day<days:
        act=action if policy is None else action_from_policy(policy,world.observe())
        _,reward,terminated,info=world.step(act)
        total_reward+=reward
        steps.append({'day':world.day,'action':ACTIONS[act],'reward':reward,
                      'score':world.score(),'cost_cents':info['spend_cents'],
                      'meal':info['recipe'],'served':info['served'],
                      'waste_g':info['wasted_g']})
        if terminated:break
    return {'seed':seed,'days':days,'policy':ACTIONS[action] if policy is None else 'PPO_CHECKPOINT',
            'total_reward':round(total_reward,2),'score':world.score(),
            'metrics':world.metrics.to_dict(),'spend_cents':world.metrics.grocery_spend_cents,
            'bead_summary':world.last_graph.summary(),'steps':steps}


def evaluate(days:int=30,seeds:list[int]|None=None,checkpoint:str|None=None) -> dict:
    """Frozen unseen scenario seeds, independent policy metrics and paired comparisons."""
    seeds=seeds or list(range(10001,10013))
    if len(set(seeds))!=len(seeds):raise ValueError('duplicate held-out seed')
    policy=load_policy(checkpoint) if checkpoint else None
    candidates={name:[] for name in ACTIONS}
    if policy:candidates['PPO_CHECKPOINT']=[]
    for seed in seeds:
        for a,name in enumerate(ACTIONS):
            candidates[name].append(rollout(seed,days,a))
        if policy:candidates['PPO_CHECKPOINT'].append(rollout(seed,days,policy=policy))
    report={}
    for name,runs in candidates.items():
        report[name]={
            'mean_score':round(statistics.mean(x['score'] for x in runs),3),
            'std_score':round(statistics.stdev(x['score'] for x in runs),3) if len(runs)>1 else 0,
            'served_rate':round(statistics.mean(x['metrics']['dinner_served']/days for x in runs),3),
            'mean_spend_usd':round(statistics.mean(x['spend_cents'] for x in runs)/100,2),
            'mean_waste_kg':round(statistics.mean(x['metrics']['household_waste_g'] for x in runs)/1000,2),
            'mean_acceptance_rate':round(statistics.mean(x['metrics']['meal_acceptance_rate'] for x in runs),3),
            'mean_variety':round(statistics.mean(len(x['metrics']['meal_variety']) for x in runs),2)}
    if policy:
        best_baseline=max(ACTIONS,key=lambda n:report[n]['mean_score'])
        diffs=[x['score']-y['score'] for x,y in zip(candidates['PPO_CHECKPOINT'],candidates[best_baseline])]
        rng=random.Random(42)
        boots=sorted(statistics.mean(rng.choices(diffs,k=len(diffs))) for _ in range(2000))
        report['PPO_CHECKPOINT']['comparison']={
           'baseline':best_baseline,'mean_score_delta':round(statistics.mean(diffs),3),
           'bootstrap_95pct_interval':[round(boots[49],3),round(boots[1949],3)],
           'improvement_demonstrated':boots[49]>0}
    return {'provenance':'synthetic held-out scenarios','seed_count':len(seeds),
            'heldout_seeds':seeds,'days':days,'results':report}
