import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pytest
from frontier_kombat_puffer import OBS_DIM, ELITE_20_SPECS, FrontierKombatPufferEnv, run_benchmark

def test_spec_inventory():
    assert len(ELITE_20_SPECS)==20
    assert [x.code for x in ELITE_20_SPECS]==[f'E{i:02d}' for i in range(1,21)]

@pytest.mark.parametrize('n',[1,3,20,41])
def test_contiguous(n):
    with FrontierKombatPufferEnv(n,seed=17) as env:
        assert env.observations.shape==(n,OBS_DIM)
        for arr in (env.observations,env.actions,env.rewards,env.terminals,env.truncations):
            assert arr.flags.c_contiguous
        for _ in range(32):
            obs,r,t,tr,_=env.step(np.full(n,5*8+3,dtype=np.int32))
            assert np.all(np.isfinite(obs)) and np.all(np.isfinite(r))
            assert not np.any(t & tr)
            assert np.all(env.slots['verdict']==1)
            assert np.all((env.slots['p1_hp']>=0)&(env.slots['p1_hp']<=100))
            assert np.all((env.slots['p2_hp']>=0)&(env.slots['p2_hp']<=100))

@pytest.mark.parametrize('eid',range(20))
def test_all_ood_envs(eid):
    with FrontierKombatPufferEnv(1,env_id=eid,ood_active=True) as env:
        for _ in range(75):
            env.step(np.array([5*8+(eid%6+1)],dtype=np.int32))
        assert env.slots['verdict'][0]==1

def test_reproducibility():
    with FrontierKombatPufferEnv(20,seed=91) as a,FrontierKombatPufferEnv(20,seed=91) as b:
        for k in range(100):
            action=np.full(20,(k*13)%72,dtype=np.int32)
            ar=a.step(action);br=b.step(action)
            np.testing.assert_array_equal(ar[0],br[0]);np.testing.assert_array_equal(ar[1],br[1]);np.testing.assert_array_equal(a.slots,b.slots)

def test_terminal_and_reset():
    with FrontierKombatPufferEnv(1,env_id=0) as env:
        done=False
        for _ in range(910):
            _,_,terminal,trunc,_=env.step(np.array([32],dtype=np.int32))
            if terminal[0] or trunc[0]:done=True;break
        assert done and env.slots['episodes'][0]>=1
        env.reset(seed=44)
        assert env.slots['step'][0]==0

def test_invalid_actions():
    with FrontierKombatPufferEnv(2) as env:
        for x in ([99,0],[1.3,2.4],[1]):
            with pytest.raises(ValueError):env.step(np.asarray(x))

def test_benchmark_smoke():
    report=run_benchmark(1,16,20,16)
    assert len(report['environments'])==20
    assert report['throughput']['invariants']
    assert report['evaluation']['all_invariants']
