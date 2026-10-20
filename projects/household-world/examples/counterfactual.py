"""Show a matched-randomness one-day branch without modifying the original world."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from household.world import HouseholdWorld,ACTIONS

world=HouseholdWorld(seed=17,horizon=21,weekly_budget_cents=14500)
print('Initial day',world.day,'remaining budget $',world.ledger.balance(world.day)/100)
for i,name in enumerate(ACTIONS):
    branch=world.fork(i)
    print(f"{name:16} reward={branch['reward']:7.3f}  dinner={branch['info']['served']}"
          f"  cost=${branch['info']['spend_cents']/100:.2f}"
          f"  recipe={branch['info']['recipe']}")
assert world.day==0, 'counterfactual analysis should not commit transactions'
_,reward,finished,info=world.step(3)
print('Committed LOW_WASTE ->',info,'new day',world.day)
