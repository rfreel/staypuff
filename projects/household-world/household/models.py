"""Domain objects and contracts. Store monetary values as cents, mass as grams.

Every age, nutrition, and financial value in the bundled fixtures is synthetic.
No medical targets are inferred from an age or household role.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Literal

@dataclass(frozen=True)
class Nutrients:
    kcal: float = 0
    protein_g: float = 0
    fiber_g: float = 0
    calcium_mg: float = 0
    iron_mg: float = 0
    sodium_mg: float = 0
    saturated_fat_g: float = 0

    def scale(self, factor: float) -> 'Nutrients':
        return Nutrients(**{k: v * factor for k, v in asdict(self).items()})

    def __add__(self, other: 'Nutrients') -> 'Nutrients':
        return Nutrients(**{k: getattr(self, k) + getattr(other, k) for k in asdict(self)})

@dataclass(frozen=True)
class Person:
    id: str
    role: Literal['adult', 'child']
    age_years: float
    dinner_energy_reference_kcal: float
    dinner_protein_reference_g: float
    dinner_fiber_reference_g: float
    preferences: dict[str, float] = field(default_factory=dict)
    allergens: frozenset[str] = frozenset()
    texture_restrictions: frozenset[str] = frozenset()
    # References are entered assumptions, not automatically prescribed targets.

    def __post_init__(self):
        if self.age_years < 0 or self.dinner_energy_reference_kcal <= 0:
            raise ValueError('age and dinner reference must be valid')

@dataclass(frozen=True)
class Product:
    id: str
    name: str
    category: str
    nutrients_per_100g: Nutrients
    storage_days: int
    freezer_days: int
    edible_yield: float
    allergens: frozenset[str] = frozenset()
    safe_for_child: bool = True
    storage: str = 'fridge'
    prep_minutes: int = 5
    carbon_kg_per_kg: float = 0  # synthetic illustration only

    def __post_init__(self):
        if not 0 < self.edible_yield <= 1 or self.storage_days < 1:
            raise ValueError('invalid food yield/shelf life')

@dataclass(frozen=True)
class Offer:
    store: str
    product_id: str
    package_g: int
    shelf_cents: int
    deal: Literal['none', 'bogo', 'percent', 'threshold'] = 'none'
    discount_pct: int = 0
    minimum_qty: int = 1
    loyalty_required: bool = False
    stock: int = 12
    tax_rate: float = 0.0
    confidence: float = 1.0
    valid_day: int = 0
    provenance: str = 'synthetic_fixture'
    def __post_init__(self):
        if self.package_g <= 0 or self.shelf_cents < 0 or self.stock < 0:
            raise ValueError('invalid offer')

@dataclass(frozen=True)
class Store:
    id: str
    name: str
    trip_cost_cents: int
    trip_minutes: int
    membership_cost_cents: int = 0
    loyalty: bool = True

@dataclass
class Lot:
    id: str
    product_id: str
    grams: float
    purchased_day: int
    expires_day: int
    storage: Literal['fridge', 'freezer', 'pantry']
    paid_cents: int
    quality: float = 1.0

@dataclass(frozen=True)
class Operation:
    id: str
    kind: str
    duration_minutes: float
    resource: str
    predecessors: tuple[str, ...] = ()
    heat_power_kw: float = 0.0
    target_core_c: float | None = None

@dataclass(frozen=True)
class Recipe:
    id: str
    title: str
    ingredients_g: dict[str, int]
    operations: tuple[Operation, ...]
    preference_tags: frozenset[str] = frozenset()
    child_texture: str = 'soft'
    allergen_override: frozenset[str] = frozenset()
    effort_minutes: int = 15

@dataclass
class Event:
    day: int
    kind: str
    details: dict
    provenance: str = 'simulated'

@dataclass
class Ledger:
    weekly_budget_cents: int
    spend_by_week: dict[int,int] = field(default_factory=dict)
    total_trip_cents: int = 0
    total_food_cents: int = 0
    rejected_cents: int = 0
    def balance(self, day: int) -> int:
        week = day // 7
        return self.weekly_budget_cents - self.spend_by_week.get(week, 0)
    def charge(self, day: int, cents: int, food_cents: int = 0, trip_cents: int = 0) -> bool:
        if cents < 0 or food_cents < 0 or trip_cents < 0:
            raise ValueError('no negative payments')
        if cents > self.balance(day):
            self.rejected_cents += cents
            return False
        week = day // 7
        self.spend_by_week[week] = self.spend_by_week.get(week, 0) + cents
        self.total_food_cents += food_cents
        self.total_trip_cents += trip_cents
        return True
