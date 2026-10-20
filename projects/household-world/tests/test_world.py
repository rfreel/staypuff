import json,random,copy
import pytest
from household.world import HouseholdWorld,ACTIONS
from household.models import Person
from household.catalog import demo_people,RECIPES

@pytest.mark.parametrize('policy',range(len(ACTIONS)))
def test_invariants_over_full_episode(policy):
    w=HouseholdWorld(seed=17,horizon=35,weekly_budget_cents=14500)
    for t in range(w.horizon):
        obs,rew,term,info=w.step(policy)
        assert all(-1e6<v<1e6 for v in obs)
        assert isinstance(rew,float)
        assert all(0<=v<=14500 for v in w.ledger.spend_by_week.values())
        assert w.inventory.assert_conservation()
        assert w.day==t+1
    assert term
    assert w.metrics.dinner_served+w.metrics.dinner_skipped==w.horizon
    with pytest.raises(RuntimeError):w.step(policy)

def test_reproducible_episode_and_graph():
    a=HouseholdWorld(seed=73,horizon=7);b=HouseholdWorld(seed=73,horizon=7)
    for act in [1,3,2,6,7,0,5]:
        oa,ra,da,ia=a.step(act);ob,rb,db,ib=b.step(act)
        assert (oa,ra,da,ia)==(ob,rb,db,ib)
        assert a.state()==b.state()

def test_action_invalid():
    w=HouseholdWorld()
    with pytest.raises(ValueError):w.step(99)
    with pytest.raises(ValueError):w.step(-1)

def test_counterfactual_no_mutation():
    w=HouseholdWorld(seed=9);before=w.state()
    options=[w.fork(i) for i in range(len(ACTIONS))]
    assert w.state()==before
    assert len(options)==8
    _,real,_,_=w.step(0)
    assert options[0]['reward']==real

def test_low_budget_no_negative_spend_and_exposes_unserved():
    w=HouseholdWorld(seed=23,horizon=14,weekly_budget_cents=0)
    for _ in range(14):w.step(0)
    assert all(v==0 for v in w.ledger.spend_by_week.values())
    assert w.metrics.dinner_skipped>0

def test_allergen_hard_constraint_and_child_texture():
    people=demo_people()
    people[2]=Person('child','child',3,400,15,4,allergens=frozenset({'milk','wheat','egg','soy'}))
    w=HouseholdWorld(people=people)
    for _ in range(10):
        w.step(0)
        if w.last_meal:
            recipe=RECIPES[w.last_meal['recipe']]
            assert not any('milk' in {'milk','cheese','yogurt'} for id in recipe.ingredients_g if id in ('milk','cheese','yogurt'))
            assert not any(id in recipe.ingredients_g for id in ('tofu','pasta','eggs','cheese'))

def test_repeat_meal_penalty_produces_variety():
    w=HouseholdWorld(horizon=14)
    for _ in range(14):w.step(0)
    assert len(w.metrics.meal_variety)>=3

def test_batch_prep_reuse_and_no_double_spending():
    w=HouseholdWorld(seed=8,horizon=5)
    w.step(6)
    assert w.metrics.batch_prep_dinners==1
    assert len(w.prepared_lots)>=1
    prev_spent=w.metrics.grocery_spend_cents
    w.step(3)
    assert w.metrics.reused_dinners==1
    assert w.metrics.grocery_spend_cents==prev_spent
    assert w.inventory.assert_conservation()

def test_budget_by_week_rollover():
    w=HouseholdWorld(seed=44,horizon=15,weekly_budget_cents=4000)
    for _ in range(15):w.step(0)
    assert len(w.ledger.spend_by_week)>=2
    assert all(v<=4000 for v in w.ledger.spend_by_week.values())

def test_graph_has_individual_price_and_provenance_nodes():
    w=HouseholdWorld(seed=1)
    w.step(0)
    nodes=w.last_graph.nodes
    assert any('profile_child' in id for id in nodes)
    assert any('.quote_value_' in id for id in nodes)
    assert any('portion_husband' in id for id in nodes)
    assert all(n.provenance for n in nodes.values())
    assert all(n.status=='passed' for n in nodes.values())
    assert w.last_graph.summary()['acyclic']

def test_serializable_state_and_events():
    w=HouseholdWorld(seed=100,horizon=3)
    for _ in range(3):w.step(2)
    data=json.loads(json.dumps(w.state()))
    assert data['day']==3
    assert data['events'][-1]['kind']=='meal_served' or data['events'][-1]['kind']=='unserved'

def test_heldout_seed_different_market():
    a=HouseholdWorld(seed=10);b=HouseholdWorld(seed=11)
    assert a.state()['market']!=b.state()['market']

def test_obs_no_future_price_leak():
    w=HouseholdWorld(seed=9)
    o=w.observe()
    assert len(o)==w.observation_dim
    assert w.observe()==o
    assert 20<=len(o)<=60

def test_full_week_nutrition_claim_is_dinner_only():
    w=HouseholdWorld(horizon=7)
    for _ in range(7):w.step(0)
    assert 'dinner' in w.last_meal['portion_method']
    assert len(w.metrics.consumed_kcal)==3

@pytest.mark.parametrize('seed',[0,1,2,9,33,999])
def test_random_policy_randomized_safety(seed):
    r=random.Random(seed)
    w=HouseholdWorld(seed=seed,horizon=45)
    for _ in range(w.horizon):
        w.step(r.randrange(len(ACTIONS)))
        assert w.inventory.assert_conservation()
        assert all(0<=x<=w.weekly_budget_cents for x in w.ledger.spend_by_week.values())
        if w.last_schedule:
            assert w.last_schedule.makespan_min>=w.last_schedule.precedence_lower_bound_min
        assert w.metrics.household_waste_g>=0
