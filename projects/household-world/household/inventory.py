"""Inventory is lot-based, FEFO, financially and materially conserved."""
from __future__ import annotations
from dataclasses import dataclass, field
from .models import Lot, Product

@dataclass
class Inventory:
    lots: list[Lot] = field(default_factory=list)
    wasted_g: float = 0
    purchased_g: float = 0
    consumed_g: float = 0
    opening_g: float = 0
    events: list[dict] = field(default_factory=list)
    def available(self, product_id:str, day:int) -> float:
        return sum(l.grams for l in self.lots if l.product_id==product_id and l.expires_day>=day)
    def coverage(self, demands:dict[str,float], day:int) -> dict[str,float]:
        return {id:max(0.0,grams-self.available(id,day)) for id,grams in demands.items()}
    def receive(self, product:Product, day:int, grams:float, paid_cents:int, key:str):
        if grams<0 or paid_cents<0: raise ValueError('negative material/cost')
        self.purchased_g+=grams
        self.lots.append(Lot(key,product.id,float(grams),day,day+product.storage_days-1,
                             'pantry' if product.storage=='pantry' else 'fridge',paid_cents))
        self.events.append({'type':'receive','id':key,'grams':grams,'day':day})
    def take(self, product_id:str, grams:float, day:int) -> bool:
        if grams<0: raise ValueError('negative demand')
        if self.available(product_id,day)+1e-7 < grams: return False
        remaining=float(grams)
        for lot in sorted(self.lots,key=lambda l:(l.expires_day,l.purchased_day)):
            if lot.product_id!=product_id or lot.expires_day < day: continue
            amount=min(lot.grams,remaining)
            lot.grams-=amount
            remaining-=amount
            if remaining<=1e-7: break
        self.consumed_g+=grams
        self.lots=[l for l in self.lots if l.grams>1e-7]
        self.events.append({'type':'consume','product':product_id,'grams':grams,'day':day})
        return True
    def expire(self,day:int) -> float:
        expired=[l for l in self.lots if l.expires_day<day]
        waste=sum(l.grams for l in expired)
        self.wasted_g+=waste
        self.lots=[l for l in self.lots if l.expires_day>=day]
        if waste: self.events.append({'type':'expire','grams':waste,'day':day})
        return waste
    def freeze(self,product_id:str,day:int,products:dict[str,Product],freezer_capacity_g:float=7000) -> float:
        occupied=sum(l.grams for l in self.lots if l.storage=='freezer')
        capacity=max(0,freezer_capacity_g-occupied)
        amount=0.0
        for lot in sorted(self.lots,key=lambda x:x.expires_day):
            if lot.product_id!=product_id or lot.storage!='fridge' or lot.expires_day>day+2 or lot.expires_day<day: continue
            moved=min(lot.grams,capacity)
            if moved<=0: break
            # Splitting preserves grams and provenance, not creation.
            lot.grams-=moved
            self.lots.append(Lot(lot.id+'f',lot.product_id,moved,day,day+products[product_id].freezer_days,
                                 'freezer',0))
            amount+=moved
            capacity-=moved
            if capacity<=0: break
        self.lots=[l for l in self.lots if l.grams>1e-7]
        return amount
    def assert_conservation(self):
        current=sum(l.grams for l in self.lots)
        left=self.opening_g+self.purchased_g
        right=current+self.consumed_g+self.wasted_g
        if abs(left-right)>1e-5: raise AssertionError(f'inventory mass balance {left} != {right}')
        if any(l.grams<0 for l in self.lots): raise AssertionError('negative lot')
        return True
