"""Reduced-order educational thermal and moisture model, not food safety certification.
Unit assumptions: food lumped heat capacities, heat transfer and evaporative energy.
"""
from dataclasses import dataclass,asdict
from math import exp

@dataclass
class ThermalResult:
    surface_c:float
    core_c:float
    pan_c:float
    retained_water_g:float
    evaporated_g:float
    browning_index:float
    electricity_kwh:float
    elapsed_min:float
    core_target_reached:bool
    valid:bool


def simulate_cook(minutes:float,mass_g:float,power_kw:float=1.5,ambient_c:float=22,
                  initial_core_c:float=5,target_core_c:float|None=None,dt_s:float=5) -> ThermalResult:
    """Conservative first-order energy model with heat loss and phase-change proxy.

    Thermodynamic model intentionally not validated against foodborne pathogen lethality.
    Does NOT imply that any specific simulated temperature proves food safety.
    """
    if minutes<0 or mass_g<=0 or power_kw<0 or dt_s<=0: raise ValueError('invalid physics inputs')
    core=initial_core_c; surface=initial_core_c; pan=ambient_c
    water=.65*mass_g; browning=0.; evap=0.
    n=max(1,round(minutes*60/dt_s)); step=minutes*60/n
    for _ in range(n):
        # Each thermal node has positive capacitance; flows are clipped to avoid numerical instability.
        pan+=(min(0.38,power_kw*1000*step/30000)*(185-pan)
              -min(.18,step/120)*(pan-ambient_c))
        ds= min(.48,step/65)*(pan-surface)*.73 - min(.12,step/230)*(surface-ambient_c)
        dc= min(.48,step/240)*(surface-core)
        surface+=ds
        core+=dc
        # Only a proxy for water loss / browned color, not an empirical reaction-rate fit.
        moist=max(0.,(surface-85)/100)*.007*step*(mass_g/100)
        removed=min(water,moist)
        water-=removed;evap+=removed
        surface-=removed*2256/max(250,mass_g*2.8)
        browning+=max(0,surface-135)*step*.00004
    result=ThermalResult(round(surface,2),round(core,2),round(pan,2),round(water,2),
                         round(evap,2),round(browning,3),round(power_kw*minutes/60,4),
                         round(minutes,2),target_core_c is not None and core>=target_core_c,
                         all(-40<x<400 for x in (surface,core,pan)))
    return result
