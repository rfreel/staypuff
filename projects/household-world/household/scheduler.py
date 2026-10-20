"""Resource-constrained project scheduling over cooking operations.
Deterministic list scheduling with precedence and capacity; lower bound reported.
"""
from dataclasses import dataclass,asdict
from .models import Operation
from collections import defaultdict

@dataclass(frozen=True)
class Scheduled:
    id:str
    label:str
    start_min:float
    end_min:float
    resource:str
    slot:int

@dataclass
class Schedule:
    tasks:list[Scheduled]
    makespan_min:float
    precedence_lower_bound_min:float
    def to_dict(self):
        return {'tasks':[asdict(x) for x in self.tasks],
                'makespan_min':round(self.makespan_min,2),
                'precedence_lower_bound_min':round(self.precedence_lower_bound_min,2)}

def schedule(operations:tuple[Operation,...],capacities:dict[str,int]|None=None) -> Schedule:
    capacities=capacities or {'burner':2,'oven':1,'counter':2,'sink':1,'person':1}
    tasks={op.id:op for op in operations}
    if len(tasks)!=len(operations): raise ValueError('duplicate task id')
    if any(p not in tasks for op in operations for p in op.predecessors): raise ValueError('missing dependency')
    remaining=set(tasks)
    availability={res:[0.0]*num for res,num in capacities.items() if num>0}
    if any(op.resource not in availability for op in operations): raise ValueError('missing resource')
    ends={};outputs=[];lower={}
    while remaining:
        ready=[tasks[id] for id in remaining if all(p in ends for p in tasks[id].predecessors)]
        if not ready:raise ValueError('cyclic operation dependencies')
        # Earliest ready first; deterministic order for repeatability.
        ready.sort(key=lambda op:(max((ends[p] for p in op.predecessors),default=0),op.id))
        op=ready[0]
        earliest=max((ends[p] for p in op.predecessors),default=0.)
        lower[op.id]=max((lower[p] for p in op.predecessors),default=0)+op.duration_minutes
        slot=min(range(len(availability[op.resource])),key=lambda k:max(earliest,availability[op.resource][k]))
        start=max(earliest,availability[op.resource][slot]);end=start+op.duration_minutes
        availability[op.resource][slot]=end;ends[op.id]=end
        outputs.append(Scheduled(op.id,op.kind,round(start,2),round(end,2),op.resource,slot))
        remaining.remove(op.id)
    return Schedule(outputs,max(ends.values(),default=0),max(lower.values(),default=0))
