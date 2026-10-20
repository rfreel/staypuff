import pytest
from dataclasses import replace
from household.models import Nutrients,Person,Offer,Store,Lot,Product,Operation
from household.catalog import PRODUCTS,STORES,RECIPES,offers_for_day
from household.economics import price_line,optimize_basket
from household.inventory import Inventory
from household.physics import simulate_cook
from household.scheduler import schedule
from household.beads import DAG,Bead


def test_nutrients_linear_composition():
    n=Nutrients(100,5,3)
    assert n.scale(2)+n==Nutrients(300,15,9)

def test_pediatric_input_does_not_derive_intake_targets():
    a=Person('kid','child',2,100,10,2)
    b=replace(a,age_years=10)
    assert a.dinner_energy_reference_kcal==b.dinner_energy_reference_kcal

def test_invalid_person_input():
    with pytest.raises(ValueError): Person('x','adult',-1,100,10,1)

@pytest.mark.parametrize('day',[0,1,7,30,100])
def test_market_reproducibility(day):
    assert offers_for_day(day,7)==offers_for_day(day,7)
    assert all(o.valid_day==day and o.provenance=='synthetic_fixture' for o in offers_for_day(day,7))

def test_bogo_odd_quantities():
    o=Offer('s','x',100,250,deal='bogo',stock=10)
    assert price_line(o,1)==250
    assert price_line(o,2)==250
    assert price_line(o,3)==500
    assert price_line(o,4)==500

def test_percent_eligibility_and_tax():
    o=Offer('s','x',100,1000,deal='percent',discount_pct=20,minimum_qty=2,tax_rate=.1,stock=10)
    assert price_line(o,1)==1100
    assert price_line(o,2)==1760
    assert price_line(replace(o,loyalty_required=True),2,loyalty=False)==2200

def test_invalid_quantity_stockout():
    with pytest.raises(ValueError): price_line(Offer('s','x',100,100,stock=1),2)
    with pytest.raises(ValueError): price_line(Offer('s','x',100,100,stock=1),-1)

def test_basket_travel_once_per_store():
    stores={'a':Store('a','A',250,10),'b':Store('b','B',300,20)}
    os=[Offer('a','x',100,100,stock=10),Offer('a','y',100,150,stock=10)]
    cart=optimize_basket({'x':100,'y':100},os,stores)
    assert cart.food_cents==250 and cart.trips_cents==250
    assert cart.total_cents==500 and cart.stores==('a',)

def test_basket_chooses_multi_store_on_joint_savings():
    stores={'a':Store('a','A',25,10),'b':Store('b','B',25,20)}
    os=[Offer('a','x',100,100,stock=10),Offer('b','x',100,500,stock=10),
        Offer('a','y',100,500,stock=10),Offer('b','y',100,100,stock=10)]
    cart=optimize_basket({'x':100,'y':100},os,stores)
    assert set(cart.stores)=={'a','b'}
    assert cart.total_cents==250

def test_basket_infeasible_budget_returns_marker():
    cart=optimize_basket({'chicken':400},offers_for_day(0),STORES,budget_cents=1)
    assert cart.missing==('budget_or_policy_infeasible',)

def test_basket_zero_requirement_no_trip():
    cart=optimize_basket({'rice':0},offers_for_day(0),STORES)
    assert cart.total_cents==0 and not cart.lines

def test_all_catalog_yields_and_recipe_references_valid():
    assert all(0<p.edible_yield<=1 for p in PRODUCTS.values())
    assert all(set(r.ingredients_g)<=PRODUCTS.keys() for r in RECIPES.values())
    assert all(sum(r.ingredients_g.values())>0 for r in RECIPES.values())

def test_inventory_fefo_conservation():
    inv=Inventory()
    p=PRODUCTS['chicken']
    inv.receive(p,0,100,200,'a');inv.receive(p,1,200,350,'b')
    assert inv.take('chicken',130,1)
    assert len(inv.lots)==1
    assert inv.lots[0].grams==170
    assert inv.consumed_g==130
    assert inv.assert_conservation()

def test_inventory_no_partial_consumption_on_shortage():
    inv=Inventory();inv.receive(PRODUCTS['rice'],0,100,50,'one')
    assert not inv.take('rice',150,0)
    assert inv.available('rice',0)==100
    assert inv.assert_conservation()

def test_expiration_removes_lots_not_too_early():
    inv=Inventory();inv.receive(PRODUCTS['chicken'],0,100,200,'one')
    assert inv.expire(2)==0
    assert inv.expire(3)==100
    assert inv.assert_conservation()

def test_freezer_mass_preservation_and_expiry_extension():
    inv=Inventory();inv.receive(PRODUCTS['chicken'],0,100,100,'c')
    assert inv.freeze('chicken',1,PRODUCTS)==100
    assert any(l.storage=='freezer' for l in inv.lots)
    assert inv.expire(6)==0
    assert inv.assert_conservation()

def test_freezer_capacity_hard_limit():
    inv=Inventory();inv.receive(PRODUCTS['chicken'],0,100,100,'c')
    assert inv.freeze('chicken',1,PRODUCTS,30)==30
    assert inv.assert_conservation()

def test_thermal_monotonic_power_sensitivity():
    a=simulate_cook(15,300,0)
    b=simulate_cook(15,300,1.5)
    assert b.core_c>a.core_c and b.pan_c>a.pan_c
    assert b.electricity_kwh>.3
    assert b.valid

def test_thermal_deterministic():
    assert simulate_cook(20,200,1.5)==simulate_cook(20,200,1.5)

def test_thermal_invalid():
    with pytest.raises(ValueError):simulate_cook(15,0)
    with pytest.raises(ValueError):simulate_cook(-1,100)

def test_kitchen_dependency_and_capacities():
    r=RECIPES['chicken_rice']; sch=schedule(r.operations)
    ends={t.id:t.end_min for t in sch.tasks}
    starts={t.id:t.start_min for t in sch.tasks}
    for op in r.operations:
        for pred in op.predecessors:assert starts[op.id]>=ends[pred]
    assert sch.makespan_min>=sch.precedence_lower_bound_min

def test_kitchen_strict_resource_capacity():
    ops=(Operation('a','cook',10,'burner'),Operation('b','cook',11,'burner'))
    serial=schedule(ops,{'burner':1})
    parallel=schedule(ops,{'burner':2})
    assert serial.makespan_min==21
    assert parallel.makespan_min==11

def test_scheduler_detects_cycles_and_missing_resources():
    with pytest.raises(ValueError):schedule((Operation('a','cook',10,'burner',('b',)),Operation('b','cook',10,'burner',('a',))))
    with pytest.raises(ValueError):schedule((Operation('a','cook',10,'burner'),),{'sink':1})

def test_dag_ready_and_execution():
    g=DAG();g.add(Bead('a','information','Observe'))
    g.add(Bead('b','decision','Choose',('a',)))
    assert [n.id for n in g.ready()]==['a']
    assert g.run()['counts']['passed']==2

def test_dag_failed_parent_blocks_child():
    g=DAG();g.add(Bead('a','verification','Check'))
    g.add(Bead('b','decision','Follow',('a',)))
    g.run({'verification':lambda _:False})
    assert g.nodes['a'].status=='failed' and g.nodes['b'].status=='blocked'

def test_dag_forbids_bad_predecessor_and_duplicate():
    g=DAG()
    with pytest.raises(ValueError):g.add(Bead('b','goal','B',('missing',)))
    g.add(Bead('a','goal','A'))
    with pytest.raises(ValueError):g.add(Bead('a','goal','A again'))
