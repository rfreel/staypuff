/* Deterministic portable C twin of household/physics.py. Units: g, W, C, seconds.
 * This is a simplified thermodynamic proxy, not food safety verification.
 */
#include <math.h>
#include <stddef.h>
int hh_simulate_cook(double minutes,double mass_g,double power_kw,double ambient_c,
  double initial_core_c,double target_core_c,double dt_s,double out[9]) {
    if (!out || minutes<0 || mass_g<=0 || power_kw<0 || dt_s<=0) return -1;
    double core=initial_core_c, surface=initial_core_c, pan=ambient_c;
    double water=.65*mass_g,evap=0,browning=0;
    int n=(int)fmax(1.,nearbyint(minutes*60/dt_s));
    double step=minutes*60/n;
    for (int j=0;j<n;j++) {
        pan+=fmin(.38,power_kw*1000*step/30000)*(185-pan)
              -fmin(.18,step/120)*(pan-ambient_c);
        double ds=fmin(.48,step/65)*(pan-surface)*.73-fmin(.12,step/230)*(surface-ambient_c);
        double dc=fmin(.48,step/240)*(surface-core);
        surface+=ds;core+=dc;
        double moist=fmax(0.,(surface-85)/100)*.007*step*(mass_g/100);
        double removed=fmin(water,moist);
        water-=removed;evap+=removed;
        surface-=removed*2256/fmax(250,mass_g*2.8);
        browning+=fmax(0,surface-135)*step*.00004;
    }
    out[0]=surface;out[1]=core;out[2]=pan;out[3]=water;out[4]=evap;
    out[5]=browning;out[6]=power_kw*minutes/60;out[7]=minutes;
    out[8]=target_core_c>=0 && core>=target_core_c;
    return (core>-40 && core<400 && surface>-40 && surface<400)?0:1;
}
