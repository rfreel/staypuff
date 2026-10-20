/* Compile-time and transition smoke tests against a deliberately minimal API
 * stub, not evidence of compatibility with the complete PufferLib runtime. */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#ifdef TEST_KOMBAT
#include "../../ocean/frontier_kombat/frontier_kombat.h"
#else
#include "../../ocean/sexpr_repo/sexpr_repo.h"
#endif
void dict_set(Dict*d,const char*k,float v){(void)d;(void)k;(void)v;}
int main(void){
    Env e={0};Dict d={0};float obs[OBS_SIZE]={0},reward=0,action=0,terminal=0;
    e.rng=42169;
    e.agents[0].observations=obs;
    e.agents[0].actions=&action;
    e.agents[0].rewards=&reward;
    e.agents[0].terminals=&terminal;
    puf_init(&e,&d);puf_reset(&e);
    for(int j=0;j<720;j++){
        action=(float)(j%ACT_SIZES_TEST);
        puf_step(&e);
        if(!isfinite(reward)){fputs("bad reward\n",stderr);return 1;}
        for(int i=0;i<OBS_SIZE;i++)if(!isfinite(obs[i])){fputs("bad observation\n",stderr);return 1;}
    }
    printf("adapter smoke PASS: obs=%d steps=%d\n",OBS_SIZE,720);
    return 0;
}
