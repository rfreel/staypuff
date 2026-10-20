import json,subprocess,shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from household.api import app
from household.world import ACTIONS,HouseholdWorld
from household.rl import rollout,train_ppo,load_policy,action_from_policy
from household.replay import build_preview


def test_end_to_end_api():
    with TestClient(app) as client:
        r=client.post('/api/reset');assert r.status_code==200
        before=r.json();assert before['day']==0
        branch=client.get('/api/counterfactual');assert branch.status_code==200
        assert len(branch.json()['alternatives'])==8
        assert client.get('/api/state').json()['day']==0
        step=client.post('/api/step',json={'action':6});assert step.status_code==200
        assert step.json()['state']['day']==1
        run=client.post('/api/run',json={'action':3,'days':4});assert run.status_code==200
        assert run.json()['state']['day']==5
        export=client.get('/api/export');assert export.status_code==200
        assert export.json()['graph']['summary']['acyclic']
        assert client.get('/api/health').json()['healthy']
        assert client.get('/').status_code==200
        assert client.get('/static/app.js').status_code==200

def test_api_invalid_and_configurable_allergen():
    with TestClient(app) as client:
        assert client.post('/api/step',json={'action':99}).status_code==422
        r=client.post('/api/configure',json={
            'seed':2,'horizon':3,'weekly_budget_cents':9000,'burners':1,
            'people':[{'id':'person_1','role':'adult','age_years':39,
                       'dinner_energy_reference_kcal':500,'dinner_protein_reference_g':20,
                       'dinner_fiber_reference_g':8,'allergens':['milk']}]
        })
        assert r.status_code==200
        data=r.json();assert data['people'][0]['allergens']==['milk']
        assert data['budget']['weekly_cents']==9000
        assert client.post('/api/run',json={'action':0,'days':3}).json()['state']['day']==3
        assert client.post('/api/step',json={'action':0}).status_code==409
        assert client.post('/api/reset').json()['day']==0

def test_ppo_smoke_train_checkpoint(tmp_path):
    file=tmp_path/'test_ppo.pt'
    report=train_ppo(str(file),updates=2,n_envs=2,days=4,seed=2,epochs=1)
    assert report['steps']==16
    policy=load_policy(str(file))
    w=HouseholdWorld(seed=100,horizon=4)
    a=action_from_policy(policy,w.observe())
    assert 0<=a<len(ACTIONS)
    assert file.stat().st_size>1000

def test_ppo_deterministic_rollout():
    assert rollout(seed=1,days=3,action=0)==rollout(seed=1,days=3,action=0)

def test_self_contained_preview(tmp_path):
    dest=tmp_path/'preview.html'
    report=build_preview(str(dest),days=3)
    src=dest.read_text()
    assert report['policies']==8
    assert 'window.__REPLAY__' in src and '<style>' in src
    assert 'Decisions' in src and 'Household World' in src
    assert dest.stat().st_size>10000

def test_native_stub_compile_and_step():
    if not shutil.which('gcc'):pytest.skip('no C compiler')
    repo=Path(__file__).parents[1]
    r=subprocess.run(['bash','scripts/build_native.sh'],cwd=repo,text=True,
                     capture_output=True,timeout=30)
    assert r.returncode==0,r.stdout+r.stderr
