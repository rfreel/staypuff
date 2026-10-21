/* Standalone stub test validates puf_* shape and finite transitions, not Puffer linking. */
#include <assert.h>
#include <math.h>
#include "../ocean/household/household.h"
int main(void) {
    Env env={0};float o[OBS_SIZE]={0},a[1]={0},r[1]={0},t[1]={0};
    env.agents[0].observations=o;env.agents[0].actions=a;
    env.agents[0].rewards=r;env.agents[0].terminals=t;
    env.rng=17;puf_init(&env,NULL);puf_reset(&env);
    for(int i=0;i<HOUSEHOLD_DAYS;i++){
        a[0]=(float)(i%8);puf_step(&env);
        for(int j=0;j<OBS_SIZE;j++)assert(isfinite(o[j]));
        assert(isfinite(r[0]));
        assert(env.cash>=-0.0001f);
    }
    assert(t[0]==1.0f);
    assert(env.day==0); // Automatic reset supplies the next initial state.
    assert(env.log.n==1);
    for(int i=0;i<HOUSEHOLD_DAYS;i++){
        a[0]=(float)(i%8);
        puf_step(&env);
        assert(isfinite(r[0]));
        assert(isfinite(o[0]));
        assert(i==0 ? t[0]==0.0f : 1);
    }
    assert(t[0]==1.0f);
    assert(env.day==0);
    assert(env.log.n==2);
    puf_render(&env); // Exercise view construction through test raylib adapter.
    return 0;
}
