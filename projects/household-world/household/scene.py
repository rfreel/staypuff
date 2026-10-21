"""PufferVis scene projection for Household World.

The protocol contains *display data only*. A scene never advances the simulation,
awards reward, or mutates world state. Coordinates are authored visual-layout
coordinates, NOT measured positions of actual household members or food.

All quantities in entity facts come from the synthetic simulator snapshot.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

SCHEMA = 'puffervis.scene.v1'


def _entity(id: str, visual: str, x: float, z: float, *, label: str = '',
            level: float = 0, rotation: int = 0, variant: str = '',
            facts: dict | None = None, signal: str = '') -> dict:
    return {'id': id, 'visual': visual, 'position': [x, level, z],
            'rotation': rotation, 'variant': variant, 'label': label,
            'facts': facts or {}, 'signal': signal}


def project_household_scene(state: dict[str, Any]) -> dict[str, Any]:
    """Compile a read-only, deterministic scene from an exported state snapshot.

    Entity IDs are stable across frames so a visualizer may interpolate safely.
    Data are not inferred from rendered geometry; renderer only reads this scene.
    """
    day = int(state['day'])
    inventory = state.get('inventory') or []
    market = state.get('market') or []
    people = state.get('people') or []
    budget = state.get('budget') or {}
    metrics = state.get('metrics') or {}
    meal = state.get('latest_meal') or {}
    schedule = state.get('latest_schedule') or {}
    physics = state.get('latest_physics') or {}
    graph = state.get('beads') or {}
    entities = [
        _entity('fridge', 'fridge', 1.3, 1.65, label='Refrigerator',
                facts={'inventory_lots': len(inventory), 'description':'Illustrative storage station'}),
        _entity('sink', 'sink', 3.7, 1.65, label='Wash station',
                facts={'resource':'sink', 'description':'Shared preparation resource'}),
        _entity('stove', 'stove', 6.3, 1.65, label='Cooking range',
                facts={'resource':'burner','temperature_proxy_c': physics.get('pan_c'),
                       'model':'Uncalibrated thermal proxy'}, signal='active' if physics else ''),
        _entity('oven', 'oven', 8.05, 1.65, label='Oven',
                facts={'resource':'oven', 'description':'Shared appliance'}),
        _entity('island', 'island', 3.8, 4.55, label='Preparation island',
                facts={'resource':'counter','description':'Cutting and assembly station'}),
        _entity('pantry', 'shelves', 0.95, 5.45, label='Pantry',
                facts={'inventory_lots': len(inventory),
                       'total_grams':round(sum(float(l.get('grams',0)) for l in inventory),1)}),
        _entity('table', 'dining_table', 5.2, 9.0, label='Dining table',
                facts={'dinners_served':metrics.get('dinner_served',0),
                       'recipe':meal.get('title','No dinner served yet')}),
        _entity('checkout', 'checkout', 13.3, 8.0, label='Checkout',
                facts={'total_spend_cents':budget.get('spent_total_cents',0),
                       'weekly_remaining_cents':budget.get('remaining_cents',0)}),
    ]

    entities.append(_entity('ledger', 'ledger', 13.2, 10.0, label='Household accounts',
                            facts={'weekly_remaining_cents':budget.get('remaining_cents',0),
                                   'spent_cents':budget.get('spent_total_cents',0),
                                   'dinners_served':metrics.get('dinner_served',0)}))

    stores = [('corner', 10.0, 1.75, 'Corner Market', '#dc8d50'),
              ('value', 12.75, 1.75, 'Value Grocer', '#76a0b6'),
              ('fresh', 15.3, 1.75, 'Fresh Foods', '#8fbc88')]
    for key,x,z,label,color in stores:
        offers=[o for o in market if o.get('store') == key]
        available=[o for o in offers if int(o.get('stock',0)) > 0]
        entities.append(_entity('store:'+key, 'market_stall', x, z, label=label,
                    variant=key, facts={'offers':len(offers),'available_offers':len(available),
                                        'lowest_listed_price_cents':min((o['price_cents'] for o in available),default=None),
                                        'currency':'USD','offers_provenance':'synthetic'},
                    signal='stockout' if offers and not available else ''))

    # Aggregated SKU crates deliberately avoid pretending to show real lot positions.
    quantities=Counter()
    freshness={}
    for lot in inventory:
        quantities[lot['product']]+=float(lot.get('grams',0))
        freshness[lot['product']]=min(freshness.get(lot['product'],float('inf')),
                                      float(lot.get('days_remaining',0)))
    for index,(sku,grams) in enumerate(sorted(quantities.items(),key=lambda kv:(freshness[kv[0]],kv[0]))[:9]):
        entities.append(_entity('inventory:'+sku,'crate', 2.7+(index%3)*0.86,
             6.45+(index//3)*0.7,label=sku.replace('_',' ').title(),
             variant='urgent' if freshness[sku]<=2 else 'stored',
             facts={'sku':sku,'grams':round(grams,1),'minimum_days_remaining':freshness[sku],
                    'display':'Aggregated inventory across lots'},
             signal='urgent' if freshness[sku]<=2 else ''))

    # Profiles and meals are symbols for the planner, not tracked human locations.
    colors=['amber','rose','mint','blue']
    for index,p in enumerate(people[:6]):
        entities.append(_entity('person:'+p['id'],'person',3.85+index*1.35,10.5,
                 label=p['id'].replace('_',' ').title(),variant=colors[index%4],
                 facts={'role':p.get('role'),'age_years':p.get('age_years'),
                        'dinner_reference_kcal':p.get('dinner_reference_kcal'),
                        'profile_provenance':'synthetic input'},signal=''))

    if meal:
        entities.append(_entity('meal:'+meal['recipe'],'meal',5.25,8.95,
                 label=meal.get('title','Dinner'), variant=meal['recipe'],
                 facts={'recipe':meal['recipe'],
                        'acceptance':meal.get('actual_acceptance'),
                        'nutrition_kcal':(meal.get('nutrition_total') or {}).get('kcal'),
                        'simulated_cooking_minutes':meal.get('scheduled_minutes'),
                        'safety':'Educational model only'}, signal='served'))

    # The edges are semantic flow illustrations, not hidden causal discoveries.
    connections=[
       {'from':'store:value','to':'checkout','kind':'illustrative_flow'},
       {'from':'checkout','to':'pantry','kind':'illustrative_flow'},
       {'from':'pantry','to':'island','kind':'illustrative_flow'},
       {'from':'island','to':'stove','kind':'illustrative_flow'},
       {'from':'stove','to':'table','kind':'illustrative_flow'},
    ]
    if not schedule.get('tasks'):
        connections=connections[:3]

    return {
        'schema':SCHEMA, 'scene_id':'household.main', 'revision':day,
        'provenance':'synthetic_simulation', 'layout_provenance':'illustrative_not_physical',
        'camera':{'projection':'isometric','target':[8,0,5.8],'zoom':1},
        'world':{'width':18,'depth':13,'tile_size':1},
        'zones':[
          {'id':'kitchen','label':'01 / KITCHEN','x':0,'z':0,'width':9.4,'depth':7.6,'material':'slate'},
          {'id':'market','label':'02 / MARKET','x':9.55,'z':0,'width':8.45,'depth':7.6,'material':'olive'},
          {'id':'dining','label':'03 / TABLE','x':0,'z':7.8,'width':9.4,'depth':5.2,'material':'cream'},
          {'id':'ledger','label':'04 / LEDGER','x':9.55,'z':7.8,'width':8.45,'depth':5.2,'material':'umber'},
        ],
        'entities':entities,'connections':connections,
        'hud':{
           'day':day,'horizon':state.get('horizon',0),'score':state.get('score',0),
           'budget_remaining_cents':budget.get('remaining_cents',0),
           'spent_cents':budget.get('spent_total_cents',0),
           'dinners_served':metrics.get('dinner_served',0),
           'waste_g':metrics.get('household_waste_g',0),
           'active_recipe':meal.get('title'),
           'task_count':((graph.get('summary') or {}).get('total',0)),
           'scheduled_minutes':schedule.get('makespan_min'),
        },
        'annotations':[
           'Authored layout; not observed real-world coordinates.',
           'Simulated prices and meal references. Cooking temperatures are not food-safety guidance.',
        ],
    }


def with_scene(state: dict[str, Any]) -> dict[str, Any]:
    """Attach deterministic scene projection to an API or replay snapshot."""
    return {**state,'visual_scene':project_household_scene(state)}
