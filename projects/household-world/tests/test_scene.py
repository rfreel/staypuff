"""PufferVis is a read-only renderer: test its semantics, not just its pixels."""
from __future__ import annotations
import json
import math
from pathlib import Path
from household.world import HouseholdWorld
from household.scene import SCHEMA, project_household_scene, with_scene
from household.api import app
from fastapi.testclient import TestClient


def test_scene_schema_shape_stable_object_identity_and_finite_numbers():
    world=HouseholdWorld(seed=93)
    first=project_household_scene(world.state())
    assert first['schema']==SCHEMA
    assert first['provenance']=='synthetic_simulation'
    assert first['layout_provenance']=='illustrative_not_physical'
    assert len(first['zones'])==4
    assert {'kitchen','market','dining','ledger'} == {z['id'] for z in first['zones']}
    assert len(first['entities'])>=12
    assert len({e['id'] for e in first['entities']})==len(first['entities'])
    for e in first['entities']:
        assert len(e['position'])==3
        assert all(math.isfinite(v) for v in e['position'])
        assert isinstance(e['facts'],dict)
    ids={e['id'] for e in first['entities']}
    assert all(link['from'] in ids and link['to'] in ids for link in first['connections'])
    assert first==project_household_scene(world.state())
    assert first==json.loads(json.dumps(first))


def test_scene_read_only_rng_and_training_observation_unchanged():
    world=HouseholdWorld(seed=22)
    before=world.snapshot()
    obs=world.observe()
    scene=project_household_scene(world.state())
    scene['entities'][0]['facts']['inventory_lots']=9999
    assert world.observe()==obs
    assert world.rng.getstate()==before.rng.getstate()
    assert world.inventory.lots==before.inventory.lots
    # Rendering a frame must have no effect on the next action's outcome.
    assert world.step(3)==before.step(3)


def test_scene_reifies_changes_and_does_not_infer_clinical_targets():
    world=HouseholdWorld(seed=7,horizon=3)
    start=project_household_scene(world.state())
    world.step(0)
    end=project_household_scene(world.state())
    assert start['hud']['day']==0 and end['hud']['day']==1
    assert end['hud']['dinners_served']==world.metrics.dinner_served
    assert end['hud']['spent_cents']==world.ledger.total_food_cents+world.ledger.total_trip_cents
    assert end['hud']['budget_remaining_cents']==world.ledger.balance(world.day)
    meal=next(x for x in end['entities'] if x['visual']=='meal')
    assert meal['facts']['acceptance']==world.last_meal['actual_acceptance']
    assert meal['facts']['nutrition_kcal']==world.last_meal['nutrition_total']['kcal']
    assert all(x['facts'].get('profile_provenance')=='synthetic input'
               for x in end['entities'] if x['visual']=='person')
    assert all('layout' in annotation.lower() or 'simulated' in annotation.lower()
               for annotation in end['annotations'])
    assert not any('daily calorie target' in str(x).lower() for x in end['entities'])


def test_scene_http_contract_and_reset():
    with TestClient(app) as client:
        state=client.post('/api/reset').json()
        assert state['visual_scene']['hud']['day']==0
        direct=client.get('/api/scene').json()
        assert direct==state['visual_scene']
        step=client.post('/api/step',json={'action':1}).json()['state']
        assert step['visual_scene']['hud']['day']==1
        assert client.get('/api/scene').json()==step['visual_scene']
        assert client.get('/static/puffervis.js').status_code==200
        assert 'puffervis.js' in client.get('/').text


def test_scene_generic_protocol_warehouse_fixture():
    # A non-household scene exercises the same renderer protocol.
    fixture=Path(__file__).parent.parent/'examples/puffervis_warehouse.json'
    data=json.loads(fixture.read_text())
    assert data['schema']==SCHEMA
    assert data['scene_id']=='warehouse.example'
    assert {'robot','crate','shelves'}.issubset({e['visual'] for e in data['entities']})


def test_browser_markups_and_native_scene_helper_present():
    root=Path(__file__).parent.parent
    page=(root/'web/index.html').read_text()
    assert 'worldCanvas' in page and 'worldPlay' in page
    assert 'data-scene-layer' in page
    js=(root/'web/puffervis.js').read_text()
    assert 'setScene(scene)' in js and 'dispose()' in js
    assert 'toIsoPoint' in js
    assert 'DrawTriangle' in (root/'native/puffervis.h').read_text()
