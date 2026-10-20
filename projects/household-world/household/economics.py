"""Basket pricing with promotion, taxes, inventory supply, travel, membership.
Every quoted price remains synthetic unless a real source adapter is installed.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import ceil
from itertools import product as combinations
from .models import Offer, Store

@dataclass(frozen=True)
class Line:
    offer: Offer
    packages: int
    cents: int

@dataclass(frozen=True)
class Basket:
    lines: tuple[Line,...]
    stores: tuple[str,...]
    food_cents: int
    trips_cents: int
    total_cents: int
    missing: tuple[str,...] = ()
    def to_dict(self) -> dict:
        return {'stores':self.stores,'food_cents':self.food_cents,'trip_cents':self.trips_cents,
                'total_cents':self.total_cents,'missing':self.missing,
                'lines':[{'product':l.offer.product_id,'store':l.offer.store,'packages':l.packages,
                          'package_g':l.offer.package_g,'paid_cents':l.cents,'deal':l.offer.deal}
                         for l in self.lines]}

def price_line(o:Offer, qty:int, loyalty:bool=True) -> int:
    if qty < 0 or qty > o.stock:
        raise ValueError('quantity exceeds stock or invalid')
    if qty == 0:
        return 0
    cents = qty*o.shelf_cents
    if o.loyalty_required and not loyalty:
        return cents + round(cents*o.tax_rate)
    if o.deal=='bogo':
        cents = (qty - qty//2)*o.shelf_cents
    elif o.deal=='percent' and qty >= o.minimum_qty:
        cents = round(cents*(100-o.discount_pct)/100)
    elif o.deal=='threshold' and qty>=o.minimum_qty:
        cents = round(cents*(100-o.discount_pct)/100)
    return cents + round(cents*o.tax_rate)

def _make_basket(choice:list[tuple[Offer,int]],stores:dict[str,Store]) -> Basket:
    lines=tuple(Line(o,q,price_line(o,q,stores[o.store].loyalty)) for o,q in choice if q)
    store_ids=tuple(sorted({l.offer.store for l in lines}))
    food=sum(l.cents for l in lines)
    trips=sum(stores[s].trip_cost_cents for s in store_ids)
    return Basket(lines,store_ids,food,trips,food+trips)

def optimize_basket(needs:dict[str,float], offers:list[Offer], stores:dict[str,Store],
                    policy:str='balanced', budget_cents:int|None=None) -> Basket:
    """Exact Cartesian enumeration for small baskets, deterministic greedy fallback.
    Jointly accounts for purchase quantities, store visits, deals, waste preference.
    Converts requested edible grams to purchased gross grams externally.
    """
    needs={k:float(v) for k,v in needs.items() if v > 1e-7}
    if not needs:
        return Basket((),(),0,0,0)
    choices=[]
    missing=[]
    for product_id, grams in sorted(needs.items()):
        opts=[]
        for o in offers:
            if o.product_id != product_id or o.stock < 1:
                continue
            qty=ceil(grams/o.package_g - 1e-10)
            if qty <= o.stock:
                opts.append((o,qty))
            if policy=='promotions' and qty + 1 <= o.stock and o.deal=='bogo':
                opts.append((o,qty+1))
        if not opts:
            missing.append(product_id)
        else:
            choices.append(opts)
    if missing:
        return Basket((),(),0,0,0,tuple(missing))
    # 3^n can explode in generic production baskets; prune via per-item candidates.
    if len(choices)>10:
        choices=[[min(opts,key=lambda oq: price_line(*oq,stores[oq[0].store].loyalty))] for opts in choices]
    best=None
    best_score=float('inf')
    for combo in combinations(*choices):
        candidate=_make_basket(list(combo),stores)
        if budget_cents is not None and candidate.total_cents>budget_cents:
            continue
        if policy=='nearby' and any(s!='corner' for s in candidate.stores):
            continue
        if policy=='value' and 'fresh' in candidate.stores:
            continue
        excess=sum((o.package_g*q-needs[o.product_id])/max(1,needs[o.product_id]) for o,q in combo)
        score=float(candidate.total_cents)
        if policy=='low_waste': score+=excess*300
        if policy=='promotions': score-=sum(o.shelf_cents*q-price_line(o,q,stores[o.store].loyalty) for o,q in combo)*.5
        if policy=='balanced': score+=excess*110
        if score<best_score:
            best,best_score=candidate,score
    if best is None:
        return Basket((),(),0,0,0,('budget_or_policy_infeasible',))
    return best
