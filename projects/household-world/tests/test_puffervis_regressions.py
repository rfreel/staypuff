"""Regressions for the six post-merge PufferVis review findings."""
import copy
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from household.api import app
from household.world import HouseholdWorld
from household.scene import project_household_scene

ROOT = Path(__file__).resolve().parents[1]


def test_install_into_clean_upstream_tree_compiles_and_runs(tmp_path):
    # No source-tree include directories: only files copied by the installer.
    dest = tmp_path / 'upstream checkout'
    (dest / '.git').mkdir(parents=True)
    for _ in range(2):
        subprocess.run(['bash', str(ROOT / 'scripts/install_in_puffer.sh'), str(dest)], check=True)
    assert (dest / 'src/puffervis.h').read_bytes() == (ROOT / 'native/puffervis.h').read_bytes()
    assert (dest / 'config/household.ini').read_bytes() == (ROOT / 'config/household.ini').read_bytes()
    (dest / 'native').mkdir()
    shutil.copy(ROOT / 'native/test_ocean.c', dest / 'native/test_ocean.c')
    shutil.copytree(ROOT / 'native/stub', dest / 'stub')
    subprocess.run(['gcc', '-std=gnu11', '-Wall', '-Wextra', '-I'+str(dest/'stub'),
                    '-I'+str(dest/'src'), str(dest/'native/test_ocean.c'), '-lm',
                    '-o', str(dest/'test_ocean')], check=True)
    subprocess.run([str(dest/'test_ocean')], check=True)


@pytest.mark.parametrize('count', [0, 1, 3, 6, 7, 12, 31])
def test_every_member_has_unique_stable_position_and_facts(count):
    state = HouseholdWorld().state()
    state['people'] = [dict(state['people'][0], id=f'member_{i}') for i in range(count)]
    before = copy.deepcopy(state)
    scene = project_household_scene(state)
    people = [e for e in scene['entities'] if e['visual'] == 'person']
    assert [e['id'] for e in people] == [f'person:member_{i}' for i in range(count)]
    assert len({tuple(e['position']) for e in people}) == count
    assert all(0 <= e['position'][0] < 9.4 and e['position'][2] < scene['world']['depth'] for e in people)
    assert all(e['facts']['age_years'] == state['people'][i]['age_years'] for i,e in enumerate(people))
    assert state == before
    assert scene == project_household_scene(state)


def test_configure_more_than_six_members_visible_after_step():
    people = [dict(id=f'person_{i}', role='adult', age_years=30,
                   dinner_energy_reference_kcal=600, dinner_protein_reference_g=25,
                   dinner_fiber_reference_g=8) for i in range(9)]
    with TestClient(app) as client:
        try:
            response = client.post('/api/configure', json={'people': people})
            assert response.status_code == 200
            states = [response.json(), client.post('/api/step', json={'action':0}).json()['state']]
            for state in states:
                assert len(state['people']) == 9
                assert len([e for e in state['visual_scene']['entities'] if e['visual']=='person']) == 9
        finally:
            client.post('/api/reset')
