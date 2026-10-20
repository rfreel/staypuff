"""Authoritative deterministic household world dynamics and evaluation.
One step is a day with one modeled shared dinner; no other meals are inferred.
All people, prices and nutrition references in default scenarios are synthetic.
"""
from __future__ import annotations
from dataclasses import dataclass,field,asdict
from collections import defaultdict
import copy, random, math
from .models import Person,Event,Ledger,Nutrients,Operation
from .catalog import PRODUCTS, STORES, RECIPES, demo_people,offers_for_day
from .inventory import Inventory
from .economics import optimize_basket, Basket
from .scheduler import schedule
from .physics import simulate_cook
from .beads import BeadCompiler, DAG

ACTIONS = (
 'BALANCED', 'CHEAPEST', 'PROMOTIONS', 'LOW_WASTE',
 'NUTRIENT_FIRST', 'PANTRY_ONLY', 'BATCH_PREP', 'NEARBY_ONLY'
)

@dataclass
class Metrics:
    dinner_served:int=0
    dinner_skipped:int=0
    meal_acceptance_sum:float=0
    served_kcal:dict[str,float]=field(default_factory=dict)
    consumed_kcal:dict[str,float]=field(default_factory=dict)
    consumed_protein_g:dict[str,float]=field(default_factory=dict)
    energy_reference_kcal:dict[str,float]=field(default_factory=dict)
    nutrient_shortfall_kcal:float=0
    kitchen_minutes:float=0
    electrical_kwh:float=0
    grocery_spend_cents:int=0
    edible_meal_g:float=0
    household_waste_g:float=0
    food_safety_rejections:int=0
    infeasible_plans:int=0
    failure_count:int=0
    price_savings_cents:int=0
    plate_waste_g:float=0
    spoiled_leftovers_g:float=0
    batch_prep_dinners:int=0
    reused_dinners:int=0
    meal_variety:dict[str,int]=field(default_factory=dict)
    def to_dict(self):
        result=asdict(self)
        count=max(1,self.dinner_served)
        result['meal_acceptance_rate']=round(self.meal_acceptance_sum/(3*count),3)
        result['cost_per_served_dinner_cents']=round(self.grocery_spend_cents/count,2)
        return result

class HouseholdWorld:
    def __init__(self,seed:int=7,horizon:int=30,weekly_budget_cents:int=14500,
                 people:list[Person]|None=None,capacities:dict[str,int]|None=None):
        if not 1<=horizon<=366: raise ValueError('horizon out of range')
        if weekly_budget_cents<0:raise ValueError('negative budget')
        self.seed=seed;self.horizon=horizon;self.weekly_budget_cents=weekly_budget_cents
        self.people=people if people is not None else demo_people()
        if len(set(p.id for p in self.people))!=len(self.people):raise ValueError('duplicate person id')
        self.capacities=capacities or {'burner':2,'oven':1,'counter':2,'sink':1,'person':1}
        self.compiler=BeadCompiler();self.reset()
    def reset(self):
        self.day=0;self.rng=random.Random(self.seed)
        self.ledger=Ledger(self.weekly_budget_cents)
        self.inventory=Inventory()
        for key,grams in {'rice':900.,'beans':700.,'oil':180.,'carrots':350.,'tomato':300.}.items():
            self.inventory.receive(PRODUCTS[key],0,grams,0,'opening-'+key)
        self.inventory.opening_g=self.inventory.purchased_g
        self.inventory.purchased_g=0
        self.metrics=Metrics()
        self.events:list[Event]=[]
        self.last_graph=DAG();self.last_schedule=None;self.last_meal=None;self.last_basket=None
        self.last_prices=[];self.last_physics=None;self.last_candidates=[]
        self.prepared_lots=[];self.meal_history=[];self.prepared_counter=0
        self._event('reset',{'seed':self.seed,'synthetic':True})
        return self.observe()
    def _event(self,kind:str,details:dict):
        self.events.append(Event(self.day,kind,details))
        if len(self.events)>2000:self.events=self.events[-2000:]
    def snapshot(self):
        """State snapshot including PRNG state for common-random-number counterfactuals."""
        return copy.deepcopy(self)
    def fork(self,action:int):
        alternative=self.snapshot()
        obs,reward,done,info=alternative.step(action)
        return {'action':ACTIONS[action],'reward':reward,'done':done,
                'metrics':alternative.metrics.to_dict(),'info':info}
    def _nutrition(self,recipe):
        nutrients=Nutrients()
        for product_id,grams in recipe.ingredients_g.items():
            nutrients+=PRODUCTS[product_id].nutrients_per_100g.scale(grams/100)
        return nutrients
    def _safe(self,recipe):
        bad=set(recipe.allergen_override)
        for id in recipe.ingredients_g:bad.update(PRODUCTS[id].allergens)
        for person in self.people:
            if person.allergens & bad: return False, f'allergen:{person.id}'
            if person.role=='child' and recipe.child_texture in person.texture_restrictions:
                return False, f'texture:{person.id}'
            if person.role=='child' and any(not PRODUCTS[id].safe_for_child for id in recipe.ingredients_g):
                return False, f'child_age_appropriateness:{person.id}'
        return True,''
    def _gross_need(self,recipe,factor:float=1.):
        return {p:factor*float(g)/PRODUCTS[p].edible_yield for p,g in recipe.ingredients_g.items()}
    def _basket(self,recipe,offers,policy='balanced'):
        missing=self.inventory.coverage(self._gross_need(recipe),self.day)
        return optimize_basket(missing,offers,STORES,policy,self.ledger.balance(self.day))
    def _person_preference(self,person,recipe):
        return max(.2,min(1.,sum(person.preferences.get(tag,.45) for tag in recipe.preference_tags)
                        /max(1,len(recipe.preference_tags))))
    def _preference(self,recipe):
        total=0
        for p in self.people:
            total+=self._person_preference(p,recipe)
        return total/len(self.people) if self.people else 0
    def _allocation(self,nutrients):
        targets=[max(1,p.dinner_energy_reference_kcal) for p in self.people]
        total=sum(targets)
        return {p.id:nutrients.scale(ref/total) for p,ref in zip(self.people,targets)}
    def _candidate(self,recipe,offers,action:int):
        safe,why=self._safe(recipe)
        if not safe:return None
        policy={1:'value',2:'promotions',3:'low_waste',5:'balanced',7:'nearby'}.get(action,'balanced')
        factor=2.0 if action==6 else 1.0
        missing=self.inventory.coverage(self._gross_need(recipe,factor),self.day)
        if action==5 and any(g>1e-6 for g in missing.values()):return None
        basket=optimize_basket(missing,offers,STORES,policy,self.ledger.balance(self.day))
        if basket.missing:return None
        n=self._nutrition(recipe)
        allocation=self._allocation(n)
        coverage=sum(min(1,allocation[p.id].kcal/p.dinner_energy_reference_kcal) for p in self.people)/max(1,len(self.people))
        protein_cov=sum(min(1,allocation[p.id].protein_g/max(1,p.dinner_protein_reference_g)) for p in self.people)/max(1,len(self.people))
        fiber_cov=sum(min(1,allocation[p.id].fiber_g/max(1,p.dinner_fiber_reference_g)) for p in self.people)/max(1,len(self.people))
        prefs=self._preference(recipe)
        excess=sum(max(0,offer.package_g*line.packages - missing[line.offer.product_id])
                   for line in basket.lines for offer in [line.offer])
        shortage=max(0,1-coverage)
        score=2.3*coverage+1.1*protein_cov+.55*fiber_cov+1.45*prefs
        score-=basket.total_cents/2300
        score-=recipe.effort_minutes/140
        score-=excess/13000
        if action==1:score-=basket.total_cents/1000
        if action==2:score+=sum(l.offer.discount_pct for l in basket.lines)/110
        if action==3:score-=excess/1100
        if action==4:score+=2.2*(coverage+protein_cov+fiber_cov)/3
        if action==5:score+=3
        if action==6:score+=len(recipe.ingredients_g)*.1
        if action==7:score+=2 if basket.stores==('corner',) else -4
        score-=shortage*.4
        score-=sum(r==recipe.id for r in self.meal_history[-4:])*.72
        if factor>1: score-=.12 # upfront labor premium; remaining prepared meal has future value
        return {'recipe':recipe,'basket':basket,'score':score,'coverage':coverage,
                'factor':factor,'reuse':False,'missing':missing,
                'protein_coverage':protein_cov,'fiber_coverage':fiber_cov,'prefs':prefs,'nutrition':n}
    def _expire_prepared(self):
        still=[]
        for lot in self.prepared_lots:
            if lot['expires_day']<self.day:
                self.metrics.spoiled_leftovers_g+=lot['equivalent_g']
                self.metrics.household_waste_g+=lot['equivalent_g']
                self._event('prepared_food_expired',{'recipe':lot['recipe'],'grams':lot['equivalent_g']})
            else: still.append(lot)
        self.prepared_lots=still
    def _reuse_candidates(self,action:int):
        if action==6:return []
        results=[]
        for lot in self.prepared_lots:
            if lot['serving_equivalents'] < .99:continue
            recipe=RECIPES[lot['recipe']]
            safe,_=self._safe(recipe)
            if not safe:continue
            n=self._nutrition(recipe)
            alloc=self._allocation(n)
            coverage=sum(min(1,alloc[p.id].kcal/p.dinner_energy_reference_kcal) for p in self.people)/len(self.people)
            prefs=self._preference(recipe)
            score=2.3*coverage+1.1+1.45*prefs+2.0
            if action in (3,5):score+=2
            results.append({'recipe':recipe,'basket':Basket((),(),0,0,0),'score':score,
              'coverage':coverage,'prefs':prefs,'nutrition':n,
              'protein_coverage':1.,'fiber_coverage':1.,'factor':1.,'reuse':True,
              'missing':{},'lot_id':lot['id']})
        return results
    def observe(self)->list[float]:
        """Partially observed vector, no future prices, RNG state or latent acceptance."""
        if not self.last_prices:self.last_prices=offers_for_day(self.day,self.seed)
        values=[self.day/self.horizon, (self.day%7)/7,
                self.ledger.balance(self.day)/max(1,self.weekly_budget_cents),
                self.inventory.wasted_g/10000,
                self.metrics.dinner_served/max(1,self.day),
                self.metrics.meal_acceptance_sum/max(1,self.metrics.dinner_served*len(self.people)),
                len(self.inventory.lots)/60,
                self.metrics.grocery_spend_cents/max(1,self.weekly_budget_cents*math.ceil(self.horizon/7))]
        for id in PRODUCTS:
            values.append(min(2,self.inventory.available(id,self.day)/1000))
        for id in ('chicken','rice','broccoli','beans','tofu','potatoes','eggs','pasta'):
            offers=[o for o in self.last_prices if o.product_id==id and o.stock>0]
            values.append(min(o.shelf_cents/o.package_g for o in offers)/3 if offers else 2)
        values.extend([min(1.0,len(self.prepared_lots)/6),
                       min(1.0,sum(l["serving_equivalents"] for l in self.prepared_lots)/6)])
        return [float(v) for v in values]
    @property
    def observation_dim(self):return len(self.observe())
    @property
    def action_dim(self):return len(ACTIONS)
    def valid_actions(self):
        """Physical-validity masks; feasibility checks still performed during step."""
        return [True]*len(ACTIONS)
    def step(self,action:int):
        if not 0<=action<len(ACTIONS):raise ValueError('invalid action')
        if self.day>=self.horizon:raise RuntimeError('episode already complete')
        d=self.day
        start_waste=self.inventory.wasted_g + self.metrics.plate_waste_g + self.metrics.spoiled_leftovers_g
        self.inventory.expire(d)
        self._expire_prepared()
        if action==3:
            for id in PRODUCTS:
                frozen=self.inventory.freeze(id,d,PRODUCTS)
                if frozen>0:self._event('freeze',{'product':id,'grams':round(frozen,2)})
        self.last_prices=offers_for_day(d,self.seed)
        candidates=[c for recipe in RECIPES.values() if (c:=self._candidate(recipe,self.last_prices,action))]
        candidates.extend(self._reuse_candidates(action))
        self.last_candidates=[{'recipe':c['recipe'].id,'reuse':c['reuse'],'score':round(c['score'],3),
                     'cost_cents':c['basket'].total_cents,'coverage':round(c['coverage'],3)} for c in candidates]
        candidates.sort(key=lambda c:(-c['score'],c['recipe'].id))
        before_spend=self.ledger.total_food_cents+self.ledger.total_trip_cents
        before_served=self.metrics.dinner_served
        quality=0.0
        if not candidates:
            self.metrics.dinner_skipped+=1;self.metrics.infeasible_plans+=1
            self._event('unserved',{'reason':'no_feasible_safe_budget_compliant_recipe','action':ACTIONS[action]})
            self.last_meal=None;self.last_basket=None;self.last_schedule=None;self.last_physics=None
            self.last_graph=DAG()
        else:
            chosen=candidates[0];recipe=chosen['recipe'];basket=chosen['basket']
            # Transaction is atomic at the budget ledger before entering stock into inventory.
            if not self.ledger.charge(d,basket.total_cents,basket.food_cents,basket.trips_cents):
                raise AssertionError('internal candidate chose unaffordable basket')
            if not chosen['reuse']:
                for line in basket.lines:
                    self.inventory.receive(PRODUCTS[line.offer.product_id],d,
                        line.packages*line.offer.package_g,line.cents,
                        f'd{d}-{line.offer.store}-{line.offer.product_id}')
                for id,grams in self._gross_need(recipe,chosen['factor']).items():
                    if not self.inventory.take(id,grams,d):raise AssertionError('failed ingredient reservation')
                operations=recipe.operations
                if chosen['factor']>1:
                    self.prepared_counter+=1
                    self.prepared_lots.append({'id':f'prepared-{self.prepared_counter}',
                      'recipe':recipe.id,'serving_equivalents':chosen['factor']-1,
                      'equivalent_g':sum(recipe.ingredients_g.values())*(chosen['factor']-1),
                      'created_day':d,'expires_day':d+2,'storage':'fridge'})
                    self.metrics.batch_prep_dinners+=1
            else:
                lot=next(l for l in self.prepared_lots if l['id']==chosen['lot_id'])
                lot['serving_equivalents']-=1
                lot['equivalent_g']-=sum(recipe.ingredients_g.values())
                self.prepared_lots=[l for l in self.prepared_lots if l['serving_equivalents']>1e-7]
                self.metrics.reused_dinners+=1
                operations=(Operation('retrieve','retrieve',2,'counter'),
                   Operation('reheat','reheat',9,'burner',('retrieve',),.8),
                   Operation('verify','verify',2,'person',('reheat',)),
                   Operation('serve','serve',2,'person',('verify',)))
            self.last_graph=self.compiler.compile_day(d,recipe,self.people,
                  chosen['missing'],reuse=chosen['reuse'],offers=self.last_prices,basket=basket)
            self.last_schedule=schedule(operations,self.capacities)
            protein_id=next((id for id in recipe.ingredients_g if PRODUCTS[id].category=='protein'),'beans')
            cook=next((op for op in operations if op.id in ('cook_main','reheat')), operations[0])
            self.last_physics=simulate_cook(cook.duration_minutes,
                          recipe.ingredients_g.get(protein_id,250),cook.heat_power_kw or 1.0,
                          target_core_c=cook.target_core_c)
            allocations=self._allocation(chosen['nutrition'])
            persons=[]
            for person in self.people:
                portion=allocations[person.id]
                accept=max(.15,min(1.,self._person_preference(person,recipe)+self.rng.uniform(-.15,.15)))
                eaten=portion.scale(accept)
                persons.append({'person':person.id,'role':person.role,'age_years':person.age_years,
                     'served_kcal':round(portion.kcal,1),'consumed_kcal':round(eaten.kcal,1),
                     'consumed_protein_g':round(eaten.protein_g,1),'acceptance':round(accept,3),
                     'reference_dinner_kcal':person.dinner_energy_reference_kcal})
                self.metrics.served_kcal[person.id]=self.metrics.served_kcal.get(person.id,0)+portion.kcal
                self.metrics.consumed_kcal[person.id]=self.metrics.consumed_kcal.get(person.id,0)+eaten.kcal
                self.metrics.consumed_protein_g[person.id]=self.metrics.consumed_protein_g.get(person.id,0)+eaten.protein_g
                self.metrics.energy_reference_kcal[person.id]=self.metrics.energy_reference_kcal.get(person.id,0)+person.dinner_energy_reference_kcal
                self.metrics.meal_acceptance_sum+=accept
                self.metrics.nutrient_shortfall_kcal+=max(0,person.dinner_energy_reference_kcal-eaten.kcal)
            quality=sum(p['acceptance'] for p in persons)/max(1,len(persons))
            self.metrics.dinner_served+=1
            self.last_graph.run()
            self.metrics.kitchen_minutes+=self.last_schedule.makespan_min
            self.metrics.electrical_kwh+=self.last_physics.electricity_kwh
            edible_g=sum(recipe.ingredients_g.values())
            self.metrics.edible_meal_g+=edible_g
            self.metrics.plate_waste_g+=edible_g*(1-quality)
            self.metrics.meal_variety[recipe.id]=self.metrics.meal_variety.get(recipe.id,0)+1
            self.meal_history.append(recipe.id)
            self.metrics.grocery_spend_cents=self.ledger.total_food_cents+self.ledger.total_trip_cents
            self.metrics.price_savings_cents+=sum(max(0,l.offer.shelf_cents*l.packages-l.cents)
                for l in basket.lines)
            self.last_meal={'recipe':recipe.id,'title':recipe.title,'people':persons,
                 'nutrition_total':asdict(chosen['nutrition']),
                 'portion_method':'reference-proportional synthetic dinner shares',
                 'predicted_coverage':round(chosen['coverage'],3),'actual_acceptance':round(quality,3),
                 'reused_prepared_food':chosen['reuse'],'batch_factor':chosen['factor'],
                 'scheduled_minutes':self.last_schedule.makespan_min,
                 'allergen_screen':'passed for configured synthetic profiles',
                 'thermal_model':'educational proxy, NOT a safe-consumption determination'}
            self.last_basket=basket
            self._event('meal_served',{'recipe':recipe.id,'action':ACTIONS[action],
                        'cost_cents':basket.total_cents,'acceptance':round(quality,3),
                        'duration_min':self.last_schedule.makespan_min})
        waste_change=(self.inventory.wasted_g+self.metrics.plate_waste_g+self.metrics.spoiled_leftovers_g)-start_waste
        self.metrics.household_waste_g=self.inventory.wasted_g+self.metrics.plate_waste_g+self.metrics.spoiled_leftovers_g
        spend_change=self.ledger.total_food_cents+self.ledger.total_trip_cents-before_spend
        served=self.metrics.dinner_served-before_served
        # Training reward kept separate from independent evaluation ledger.
        # Per-step learning signal approximately tracks independent score terms.
        # Independent score still uses a different aggregate denominator, so this
        # is *not* a disguised copy of the confirmation metric.
        total_budget=max(1,self.weekly_budget_cents*math.ceil(self.horizon/7))
        reward=(2.3333*served + quality - waste_change/600.0
                - 3.0*spend_change/total_budget
                - (0.15 if not served else 0))
        self.inventory.assert_conservation()
        if any(x>self.weekly_budget_cents for x in self.ledger.spend_by_week.values()):
            raise AssertionError('budget violated')
        self.day+=1
        self.last_prices=offers_for_day(self.day,self.seed)
        terminated=self.day>=self.horizon
        info={'day':d,'served':bool(served),'wasted_g':round(waste_change,2),
              'spend_cents':spend_change,'score':self.score(),
              'action':ACTIONS[action],'recipe':self.last_meal['recipe'] if self.last_meal else None}
        return self.observe(),round(reward,5),terminated,info
    def score(self):
        """Independent, fixed scoring formula; explicitly not the RL reward scale."""
        steps=max(1,self.day)
        coverage=self.metrics.dinner_served/steps
        acceptance=self.metrics.meal_acceptance_sum/max(1,self.metrics.dinner_served*len(self.people))
        return round(max(0,min(100,100*(.7*coverage+.3*acceptance)
               -self.inventory.wasted_g/600-
               self.metrics.grocery_spend_cents/max(1,self.weekly_budget_cents*math.ceil(self.horizon/7))*3)),2)
    def state(self,full:bool=True):
        """Explicitly synthetic information for dashboard/replay, not a live market feed."""
        report={'schema_version':'0.2','provenance':'synthetic_simulation','seed':self.seed,
          'day':self.day,'horizon':self.horizon,'actions':ACTIONS,
          'budget':{'weekly_cents':self.weekly_budget_cents,'remaining_cents':self.ledger.balance(self.day),
             'spent_total_cents':sum(self.ledger.spend_by_week.values()),
             'spent_by_week':self.ledger.spend_by_week,'food_cents':self.ledger.total_food_cents,
             'transport_cents':self.ledger.total_trip_cents},
          'people':[{'id':p.id,'role':p.role,'age_years':p.age_years,
             'dinner_reference_kcal':p.dinner_energy_reference_kcal,
             'dinner_protein_reference_g':p.dinner_protein_reference_g,
             'dinner_fiber_reference_g':p.dinner_fiber_reference_g,
             'preferences':p.preferences,
             'allergens':sorted(p.allergens),
             'texture_restrictions':sorted(p.texture_restrictions)} for p in self.people],
          'metrics':self.metrics.to_dict(),'score':self.score(),
          'inventory':sorted([{'id':l.id,'product':l.product_id,'name':PRODUCTS[l.product_id].name,
             'grams':round(l.grams,1),'expires_day':l.expires_day,
             'days_remaining':l.expires_day-self.day,'storage':l.storage,'quality':l.quality}
             for l in self.inventory.lots],key=lambda v:(v['days_remaining'],v['product'])),
          'prepared_lots':self.prepared_lots,
          'latest_meal':self.last_meal,
          'latest_basket':self.last_basket.to_dict() if self.last_basket else None,
          'latest_schedule':self.last_schedule.to_dict() if self.last_schedule else None,
          'latest_physics':asdict(self.last_physics) if self.last_physics else None,
          'candidates':self.last_candidates,
          'beads':self.last_graph.serialize(),
          'events':[asdict(e) for e in self.events[-22:]],
          'market':[{'product':o.product_id,'store':o.store,'package_g':o.package_g,
                     'price_cents':o.shelf_cents,'stock':o.stock,
                     'promotion':f'{o.discount_pct}% off' if o.deal=='percent' else 'none',
                     'provenance':o.provenance} for o in self.last_prices] if full else []}
        return report
