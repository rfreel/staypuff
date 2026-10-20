"""CLI entrypoint for running, evaluating and serving Household World."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from .world import HouseholdWorld,ACTIONS


def main():
    ap=argparse.ArgumentParser(prog='household-world',description='Household RL and Beads simulator')
    sub=ap.add_subparsers(dest='command',required=True)
    s=sub.add_parser('simulate');s.add_argument('--seed',type=int,default=7);s.add_argument('--days',type=int,default=30)
    s.add_argument('--action',choices=ACTIONS,default='BALANCED');s.add_argument('--output',default=None)
    s.add_argument('--budget',type=int,default=14500,help='Weekly dinner-specific grocery cents')
    e=sub.add_parser('evaluate');e.add_argument('--days',type=int,default=30)
    e.add_argument('--seeds',type=int,default=12);e.add_argument('--checkpoint')
    e.add_argument('--output',default='artifacts/evaluation.json')
    t=sub.add_parser('train');t.add_argument('--updates',type=int,default=40)
    t.add_argument('--envs',type=int,default=8);t.add_argument('--days',type=int,default=14)
    t.add_argument('--seed',type=int,default=17);t.add_argument('--output',default='artifacts/household_ppo.pt')
    v=sub.add_parser('serve');v.add_argument('--port',type=int,default=8765)
    p=sub.add_parser('preview');p.add_argument('--output',default='artifacts/preview.html')
    b=sub.add_parser('benchmark');b.add_argument('--steps',type=int,default=1000)
    x=ap.parse_args()
    if x.command=='simulate':
        w=HouseholdWorld(seed=x.seed,horizon=x.days,weekly_budget_cents=x.budget)
        timeline=[w.state()]
        for _ in range(x.days):
            w.step(ACTIONS.index(x.action));timeline.append(w.state())
        report={'seed':x.seed,'action':x.action,'days':x.days,'timeline':timeline,'final':w.state()}
        if x.output:
            Path(x.output).parent.mkdir(parents=True,exist_ok=True)
            Path(x.output).write_text(json.dumps(report,indent=2))
        print(json.dumps({'score':w.score(),'metrics':w.metrics.to_dict(),
                          'cost_usd':w.metrics.grocery_spend_cents/100,
                          'days':w.day,'export':x.output},indent=2))
    elif x.command=='evaluate':
        from .rl import evaluate
        r=evaluate(days=x.days,seeds=list(range(10001,10001+x.seeds)),checkpoint=x.checkpoint)
        Path(x.output).parent.mkdir(parents=True,exist_ok=True)
        Path(x.output).write_text(json.dumps(r,indent=2))
        print(json.dumps(r,indent=2))
    elif x.command=='train':
        from .rl import train_ppo
        print(json.dumps(train_ppo(output=x.output,updates=x.updates,n_envs=x.envs,
                                   days=x.days,seed=x.seed),indent=2))
    elif x.command=='serve':
        import uvicorn
        uvicorn.run('household.api:app',host='127.0.0.1',port=x.port,reload=False)
    elif x.command=='preview':
        from .replay import build_preview
        print(build_preview(x.output))
    elif x.command=='benchmark':
        import time
        w=HouseholdWorld(seed=17,horizon=30)
        start=time.perf_counter()
        for i in range(x.steps):
            if w.day>=w.horizon:w.reset()
            w.step(i%len(ACTIONS))
        duration=time.perf_counter()-start
        print(json.dumps({'steps':x.steps,'seconds':duration,
                          'steps_per_second':round(x.steps/duration)},indent=2))

if __name__=='__main__':main()
