"""Loopback-only simulation API with atomic state mutation.
The app does not connect to grocers, personal records, or payment systems.
"""
from __future__ import annotations
from pathlib import Path
from threading import RLock
from typing import Literal
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .world import HouseholdWorld,ACTIONS
from .models import Person

class StepRequest(BaseModel):
    action:int=Field(ge=0,le=7)

class RunRequest(BaseModel):
    action:int=Field(ge=0,le=7)
    days:int=Field(default=7,ge=1,le=30)

class PersonInput(BaseModel):
    id:str=Field(min_length=1,max_length=50)
    role:Literal['adult','child']
    age_years:float=Field(ge=0,le=125)
    dinner_energy_reference_kcal:float=Field(gt=0,le=5000)
    dinner_protein_reference_g:float=Field(ge=0,le=300)
    dinner_fiber_reference_g:float=Field(ge=0,le=150)
    preferences:dict[str,float]=Field(default_factory=dict)
    allergens:list[str]=Field(default_factory=list,max_length=50)
    texture_restrictions:list[str]=Field(default_factory=list,max_length=30)

class ConfigureRequest(BaseModel):
    seed:int=Field(default=7,ge=0,le=1_000_000)
    horizon:int=Field(default=30,ge=1,le=120)
    weekly_budget_cents:int=Field(default=14500,ge=0,le=5_000_000)
    people:list[PersonInput]|None=None
    burners:int=Field(default=2,ge=1,le=8)

class Session:
    def __init__(self):
        self.lock=RLock()
        self.world=HouseholdWorld()
    def reset(self,kwargs=None):
        with self.lock:
            self.world=HouseholdWorld(**(kwargs or {}))
            return self.world.state()

state=Session()
app=FastAPI(title='Household World Ω',version='0.2.0',description='Synthetic decision laboratory')
WEB=Path(__file__).resolve().parent.parent/'web'
app.mount('/static',StaticFiles(directory=WEB),name='static')

@app.get('/')
def index():return FileResponse(WEB/'index.html')

@app.get('/api/state')
def get_state():
    with state.lock:return state.world.state()

@app.post('/api/step')
def step(req:StepRequest):
    with state.lock:
        try:
            observation,reward,done,info=state.world.step(req.action)
        except (ValueError,RuntimeError) as exc:raise HTTPException(409,str(exc)) from exc
        return {'reward':reward,'terminated':done,'info':info,'state':state.world.state()}

@app.post('/api/run')
def run(req:RunRequest):
    with state.lock:
        results=[]
        for _ in range(req.days):
            if state.world.day>=state.world.horizon:break
            _,reward,done,info=state.world.step(req.action)
            results.append({'reward':reward,**info})
            if done:break
        return {'results':results,'state':state.world.state()}

@app.post('/api/reset')
def reset():return state.reset()

@app.post('/api/configure')
def configure(req:ConfigureRequest):
    people=None
    if req.people:
        people=[]
        for p in req.people:
            people.append(Person(id=p.id,role=p.role,age_years=p.age_years,
                dinner_energy_reference_kcal=p.dinner_energy_reference_kcal,
                dinner_protein_reference_g=p.dinner_protein_reference_g,
                dinner_fiber_reference_g=p.dinner_fiber_reference_g,
                preferences=p.preferences,
                allergens=frozenset(p.allergens),
                texture_restrictions=frozenset(p.texture_restrictions)))
    try:
        return state.reset({'seed':req.seed,'horizon':req.horizon,
           'weekly_budget_cents':req.weekly_budget_cents,'people':people,
           'capacities':{'burner':req.burners,'oven':1,'counter':2,'sink':1,'person':1}})
    except ValueError as exc:raise HTTPException(422,str(exc)) from exc

@app.get('/api/counterfactual')
def counterfactual():
    with state.lock:
        if state.world.day>=state.world.horizon:return {'alternatives':[]}
        alternatives=[state.world.fork(i) for i in range(len(ACTIONS))]
        return {'day':state.world.day,'alternatives':alternatives}

@app.get('/api/export')
def export():
    with state.lock:
        return JSONResponse({'metadata':{'world_version':'0.2.0','simulation':'synthetic',
                'seed':state.world.seed,'day':state.world.day},
                'events':[e.__dict__ for e in state.world.events],
                'graph':state.world.last_graph.serialize(),
                'state':state.world.state()})

@app.get('/api/health')
def health():return {'healthy':True,'mode':'synthetic','model':'HWM-Omega'}
