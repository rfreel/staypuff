"""Synthetic, internally labeled market and recipe fixtures.
No live prices, clinical requirements, or government nutrient tables are asserted.
"""
from __future__ import annotations
from .models import Nutrients, Product, Person, Store, Offer, Operation, Recipe
import random

PRODUCTS = {
    p.id: p for p in [
        Product('chicken','Chicken breast','protein', Nutrients(165,31,0,15,.9,74,1),3,90,.85,storage='fridge',carbon_kg_per_kg=6),
        Product('tofu','Firm tofu','protein', Nutrients(76,8,1,350,5.4,7,1),5,60,.98,allergens=frozenset({'soy'}),carbon_kg_per_kg=2),
        Product('eggs','Eggs','protein', Nutrients(143,13,0,56,1.8,142,3.1),20,60,.88,allergens=frozenset({'egg'}),carbon_kg_per_kg=4),
        Product('beans','Black beans cooked','protein', Nutrients(132,9,8.7,27,2.1,1,.1),6,90,1,storage='pantry',carbon_kg_per_kg=1),
        Product('rice','Dry rice','grain', Nutrients(360,7,1.3,10,1.2,5,.2),180,365,1,storage='pantry',carbon_kg_per_kg=2),
        Product('pasta','Dry pasta','grain', Nutrients(371,13,3.2,21,3.3,6,.3),180,365,1,allergens=frozenset({'wheat'}),storage='pantry',carbon_kg_per_kg=2),
        Product('potatoes','Potatoes','vegetable', Nutrients(77,2,2.2,12,.8,6,.03),20,90,.92,storage='pantry',carbon_kg_per_kg=.5),
        Product('carrots','Carrots','vegetable', Nutrients(41,.9,2.8,33,.3,69,.04),12,120,.85,carbon_kg_per_kg=.4),
        Product('broccoli','Broccoli','vegetable', Nutrients(34,2.8,2.6,47,.7,33,.1),5,100,.78,carbon_kg_per_kg=1),
        Product('spinach','Spinach','vegetable', Nutrients(23,2.9,2.2,99,2.7,79,.1),4,90,.88,carbon_kg_per_kg=1),
        Product('tomato','Tomatoes','vegetable', Nutrients(18,.9,1.2,10,.3,5,.03),7,60,.90,carbon_kg_per_kg=.7),
        Product('milk','Milk','dairy', Nutrients(61,3.2,0,113,.03,43,1.9),8,60,1,allergens=frozenset({'milk'}),carbon_kg_per_kg=3),
        Product('cheese','Cheese','dairy', Nutrients(400,25,0,721,.7,621,19),16,90,1,allergens=frozenset({'milk'}),carbon_kg_per_kg=10),
        Product('oil','Cooking oil','fat', Nutrients(884,0,0,0,0,0,14),240,365,1,storage='pantry',carbon_kg_per_kg=2),
        Product('yogurt','Plain yogurt','dairy', Nutrients(59,10,0,110,.1,36,.1),8,60,1,allergens=frozenset({'milk'}),carbon_kg_per_kg=3),
        Product('apples','Apples','fruit', Nutrients(52,.3,2.4,6,.1,1,0),20,90,.9,storage='fridge',carbon_kg_per_kg=.4),
    ]
}
STORES = {
    'corner': Store('corner','Corner Market',200,12),
    'value': Store('value','Value Warehouse',500,28),
    'fresh': Store('fresh','Fresh Foods',320,21),
}
# Entirely invented cents per package, for testing behavior rather than claiming market price accuracy.
BASE_OFFERS = {
 'chicken':(850,690,920,500), 'tofu':(330,270,350,400), 'eggs':(390,330,450,500),
 'beans':(240,170,260,450), 'rice':(340,280,390,1000), 'pasta':(220,170,270,500),
 'potatoes':(360,290,380,1000), 'carrots':(250,190,250,700), 'broccoli':(370,290,430,500),
 'spinach':(390,310,440,250), 'tomato':(280,200,340,500), 'milk':(420,370,450,1000),
 'cheese':(490,410,530,300), 'oil':(690,590,740,500), 'yogurt':(450,390,480,500),
 'apples':(430,360,490,900),
}

def offers_for_day(day:int, seed:int=7) -> list[Offer]:
    """Deterministic exogenous synthetic offers; no agent access to future market shocks."""
    rng = random.Random(seed * 1000003 + day * 193)
    result = []
    for product, prices in BASE_OFFERS.items():
        for j, store in enumerate(STORES.values()):
            base = prices[j]
            fluctuation = rng.uniform(.88, 1.18)
            promoted = (day + j*2 + len(product)) % 9 == 0
            deal = 'percent' if promoted else 'none'
            stock = 0 if rng.random() < .055 else rng.randint(2, 15)
            result.append(Offer(store.id,product,prices[3],max(1,round(base*fluctuation)),
                deal=deal,discount_pct=20 if promoted else 0,minimum_qty=1,
                stock=stock,valid_day=day,confidence=.85))
    return result


def operations(protein:str='chicken', complexity:int=0) -> tuple[Operation,...]:
    main_cook = 18 if protein=='chicken' else 12
    return (
        Operation('wash','wash',4,'sink'),
        Operation('prep_veg','chop',8,'counter',('wash',)),
        Operation('prep_main','prep',7,'counter'),
        Operation('heat_pan','preheat',5,'burner'),
        Operation('cook_main','cook',main_cook,'burner',('prep_main','heat_pan'),1.5,72 if protein=='chicken' else None),
        Operation('cook_side','cook',13+complexity,'burner',('prep_veg',),1),
        Operation('rest','rest',5,'counter',('cook_main',)),
        Operation('portion','portion',4,'counter',('rest','cook_side')),
        Operation('verify','verify',2,'person',('portion',)),
        Operation('serve','serve',1,'person',('verify',)),
    )
RECIPES = {
    r.id: r for r in [
        Recipe('chicken_rice','Chicken, rice & greens',{'chicken':510,'rice':260,'broccoli':420,'oil':20},operations('chicken'),frozenset({'comfort','high_protein'})),
        Recipe('tofu_rice','Tofu vegetable bowls',{'tofu':680,'rice':260,'carrots':250,'spinach':250,'oil':20},operations('tofu'),frozenset({'plant','quick'})),
        Recipe('bean_potato','Black bean & potato skillet',{'beans':700,'potatoes':700,'tomato':250,'oil':20},operations('tofu',3),frozenset({'plant','budget'})),
        Recipe('chicken_pasta','Chicken tomato pasta',{'chicken':430,'pasta':310,'tomato':430,'spinach':170,'oil':20},operations('chicken',4),frozenset({'comfort'})),
        Recipe('egg_rice','Egg & vegetable fried rice',{'eggs':460,'rice':280,'carrots':220,'broccoli':260,'oil':30},operations('tofu',1),frozenset({'quick','budget'}),allergen_override=frozenset({'egg'})),
        Recipe('cheesy_potatoes','Cheesy baked potatoes',{'potatoes':850,'cheese':220,'beans':350,'broccoli':350},operations('tofu',8),frozenset({'comfort'})),
        Recipe('chicken_roast','Roasted chicken & vegetables',{'chicken':510,'potatoes':650,'carrots':350,'oil':20},operations('chicken',9),frozenset({'high_protein'})),
        Recipe('bean_pasta','Tomato & bean pasta',{'beans':550,'pasta':310,'tomato':430,'spinach':160,'oil':25},operations('tofu',3),frozenset({'plant','budget'})),
    ]
}

def demo_people():
    """Synthetic example profiles, never interpreted as actual family health data."""
    return [
        Person('husband','adult',40,750,35,8,{'comfort':.7,'high_protein':.9,'plant':.4}),
        Person('wife','adult',38,650,28,8,{'plant':.8,'comfort':.6,'quick':.5}),
        Person('child','child',3,400,15,4,{'comfort':.9,'quick':.7,'plant':.4},texture_restrictions=frozenset({'hard_crunch'})),
    ]
