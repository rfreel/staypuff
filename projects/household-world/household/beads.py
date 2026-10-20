"""Typed dynamic Beads DAG: dependencies, causality, execution and failures.
Edges express precedence; physical causation remains with world transitions.
"""
from __future__ import annotations
from dataclasses import dataclass,field,asdict
from collections import deque
from typing import Callable
from .models import Operation

KINDS = frozenset({'goal','information','decision','procurement','transport','storage',
 'preparation','physical_control','scheduling','allocation','verification','contingency',
 'recovery','evaluation','disposal','cleaning','maintenance','learning','settlement'})
STATUS = frozenset({'pending','ready','running','passed','failed','blocked','skipped'})

@dataclass
class Bead:
    id:str
    kind:str
    label:str
    depends_on:tuple[str,...]=()
    resources:dict[str,int]=field(default_factory=dict)
    duration_minutes:float=0
    status:str='pending'
    details:dict=field(default_factory=dict)
    provenance:str='generated_rule'
    day:int=0
    def __post_init__(self):
        if self.kind not in KINDS or self.status not in STATUS: raise ValueError('invalid bead type/status')
        if self.duration_minutes<0 or any(x<0 for x in self.resources.values()):
            raise ValueError('negative duration/capacity')

class DAG:
    def __init__(self):
        self.nodes:dict[str,Bead]={}
        self.events:list[dict]=[]
    def add(self,node:Bead):
        if node.id in self.nodes: raise ValueError('duplicate bead '+node.id)
        if node.id in node.depends_on: raise ValueError('self-dependency')
        if any(p not in self.nodes for p in node.depends_on):
            raise ValueError('missing predecessors for '+node.id)
        # Preconditions require every predecessor to be added already, so new
        # edges cannot introduce a cycle. Full topological validation occurs at run.
        self.nodes[node.id]=node
        self.events.append({'kind':'add','id':node.id,'day':node.day})
    def _toposort(self):
        indeg={id:len(n.depends_on) for id,n in self.nodes.items()}
        outgoing={id:[] for id in self.nodes}
        for id,n in self.nodes.items():
            for p in n.depends_on: outgoing[p].append(id)
        q=deque(id for id,k in indeg.items() if k==0)
        order=[]
        while q:
            id=q.popleft();order.append(id)
            for successor in outgoing[id]:
                indeg[successor]-=1
                if indeg[successor]==0:q.append(successor)
        if len(order)!=len(self.nodes): raise ValueError('cycle in DAG')
        return order
    def ready(self)->list[Bead]:
        return [n for n in self.nodes.values() if n.status in ('pending','ready')
                and all(self.nodes[p].status=='passed' for p in n.depends_on)]
    def run(self,handlers:dict[str,Callable[[Bead],bool]]|None=None)->dict:
        handlers=handlers or {}
        for id in self._toposort():
            b=self.nodes[id]
            if b.status in ('passed','skipped'):continue
            if any(self.nodes[p].status!='passed' for p in b.depends_on):
                b.status='blocked'
                self.events.append({'kind':'blocked','id':id})
                continue
            b.status='running'
            try: ok=bool(handlers[b.kind](b)) if b.kind in handlers else True
            except Exception as e:
                ok=False; b.details['error']=str(e)
            b.status='passed' if ok else 'failed'
            self.events.append({'kind':b.status,'id':id})
        return self.summary()
    def summary(self):
        counts={s:sum(n.status==s for n in self.nodes.values()) for s in STATUS}
        return {'total':len(self.nodes),'counts':counts,'acyclic':True}
    def serialize(self,limit:int=200):
        ordered=self._toposort()[-limit:]
        return {'summary':self.summary(),
                'nodes':[asdict(self.nodes[id]) for id in ordered],
                'edges':[{'source':p,'target':id} for id in ordered for p in self.nodes[id].depends_on]}

class BeadCompiler:
    """Compile concrete grocery/kitchen actions into executable, person-aware task instances."""
    def compile_day(self,day:int,recipe,people:list,needed:dict,shopping:bool=True,reuse:bool=False,offers=(),basket=None):
        d=DAG(); root=f'd{day:03d}'
        def b(key,kind,label,deps=(),resources=None,duration=0,details=None):
            id=f'{root}.{key}'
            d.add(Bead(id,kind,label,tuple(f'{root}.{p}' for p in deps),
                       resources or {},duration,details=details or {},day=day))
            return key
        b('goal','goal','Serve individually appropriate family dinner')
        b('people','information','Read per-person requirements',('goal',),details={'members':[p.id for p in people]})
        b('pantry','information','Inspect stock, expiration and leftovers',('goal',))
        b('prices','information','Observe store-specific offers and promotion validity',('goal',))
        b('budget','information','Reconcile remaining weekly grocery envelope',('goal',))
        person_sources=[]
        for p in people:
            key='profile_'+p.id
            b(key,'information',f'Validate input profile for {p.id}',('people',),
              details={'role':p.role,'age_years':p.age_years,
              'dinner_energy_reference_kcal':p.dinner_energy_reference_kcal,
              'allergens':sorted(p.allergens)})
            person_sources.append(key)
        quote_sources=[]
        for offer in offers:
            key='quote_'+offer.store+'_'+offer.product_id
            b(key,'information',f'Observe {offer.product_id} at {offer.store}',('prices',),
              details={'shelf_cents':offer.shelf_cents,'package_g':offer.package_g,
                'stock':offer.stock,'promotion':offer.deal,
                'valid_day':offer.valid_day,'provenance':offer.provenance})
            quote_sources.append(key)
        b('recipe','decision',f'Select {recipe.title}',('people','pantry','prices','budget',*person_sources))
        b('safety','verification','Screen allergens and child texture',('recipe',))
        for product_id,g in needed.items():
            b('need_'+product_id,'allocation',f'Reconcile {product_id} by edible mass',('safety','pantry'),
              details={'gross_shortfall_g':g})
        b('need','allocation','Compute exact edible ingredient shortfalls',('safety','pantry',*
          ('need_'+p for p in needed)),details={'shortfalls_g':needed})
        b('basket','decision','Reuse prepared meal' if reuse else 'Solve basket including package size, promotions, travel and stockouts',
          ('need','prices','budget',*quote_sources))
        line_checks=[]
        if basket:
            for i,line in enumerate(basket.lines):
                key=f'line_{i}'
                b(key,'verification',f'Validate price and stock for {line.offer.product_id}',('basket',),
                  details={'store':line.offer.store,'paid_cents':line.cents,'packages':line.packages})
                line_checks.append(key)
        b('checkout','settlement','Verify feasible checkout and reserve budget',('basket',*line_checks))
        b('travel','transport','Acquire selected items with accounted trip cost',('checkout',),{'driver':1})
        b('store','storage','Receive lots with dated shelf life and cost basis',('travel',))
        b('reserve','scheduling','Reserve shared kitchen resource capacities',('store','safety'))
        ops=recipe.operations if not reuse else (
            Operation('retrieve','retrieve',2,'counter'),
            Operation('reheat','reheat',9,'burner',('retrieve',),.8),
            Operation('verify','verify',2,'person',('reheat',)),
            Operation('serve','serve',2,'person',('verify',)),
        )
        for op in ops:
            deps=['reserve'] + [f'op_{pred}' for pred in op.predecessors]
            # Some nodes have 'reserve' only, others represent kitchen timing precedence.
            b('op_'+op.id,'physical_control' if op.heat_power_kw else 'preparation',
              op.kind+' · '+op.id,tuple(deps),{op.resource:1},op.duration_minutes,
              {'heat_power_kw':op.heat_power_kw,'target_core_c':op.target_core_c})
        for p in people:
            b('portion_'+p.id,'allocation',f'Allocate portion for {p.id}',('op_serve','profile_'+p.id),
             details={'dinner_reference_kcal':p.dinner_energy_reference_kcal})
        b('individual','allocation','Allocate separate adult and child portions',
            ('op_serve',*('portion_'+p.id for p in people)))
        b('observe','information','Observe acceptance and actual food consumed',('individual',))
        b('leftovers','storage','Cool and store leftovers with updated safety history',('observe',))
        b('cleanup','cleaning','Clean cookware and food-contact surfaces',('op_serve',))
        b('audit','verification','Audit material, budget and allergy invariants',('leftovers','cleanup'))
        b('learn','learning','Write policy feedback and independent evaluation metrics',('audit',))
        return d
