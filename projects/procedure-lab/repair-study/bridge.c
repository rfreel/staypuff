#include "variant.h"
#define API __attribute__((visibility("default")))
static float* destination;
void study_capture(Env* e, int abandon) {
    float before=0, after=0;
    for (int r=0;r<e->max_rounds;r++) for(int i=0;i<PL_FINAL;i++) {
        PlCase* c=&e->final_cases[r][i];
        int truth=pl_truth(e->goal,c);
        before += pl_run(e->original,c)==truth;
        after += pl_run(e->incumbent,c)==truth;
    }
    float divisor=e->max_rounds*PL_FINAL;
    float row[12]={after/divisor,(after-before)/divisor,e->episode_return,
        e->episode_cost,e->episode_invalid,e->episode_retained,e->round,
        abandon,e->task_gain,e->feedback,e->last_status,e->goal};
    memcpy(destination,row,sizeof(row));
}
typedef struct { Env* envs; int count; } Pool;
API Pool* study_create(int count,int family,int shifted,unsigned int seed,int mode,int curriculum,
        float* obs,float* actions,float* rewards,float* done) {
    Pool* p=calloc(1,sizeof(Pool)); assert(p);
    p->count=count; p->envs=calloc(count,sizeof(Env)); assert(p->envs);
    for(int i=0;i<count;i++) {
        Env* e=&p->envs[i];
        e->num_agents=1;e->family_mode=family;e->evaluate=shifted;
        e->initial_budget=96;e->max_rounds=3;e->mode=mode;e->curriculum=curriculum;
        e->rng=seed+104729u*i;
        e->agents[0].observations=obs+i*OBS_SIZE;e->agents[0].actions=actions+i*3;
        e->agents[0].rewards=rewards+i;e->agents[0].terminals=done+i;
        puf_reset(e);
    }
    return p;
}
API void study_step(Pool* p,float* metrics,float* valid) {
    memset(metrics,0,p->count*12*sizeof(float));
    for(int i=0;i<p->count;i++) {
        Env* e=&p->envs[i];destination=metrics+i*12;puf_step(e);
        valid[i]=e->agents[0].terminals[0] ? destination[10] : e->last_status;
        memset(&e->log,0,sizeof(Log));
    }
}
API void study_curriculum(Pool* p,int enabled) {
    for(int i=0;i<p->count;i++) p->envs[i].curriculum=enabled;
}
API void study_free(Pool* p) {free(p->envs);free(p);}
