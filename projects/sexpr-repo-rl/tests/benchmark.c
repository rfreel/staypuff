#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "../../../ocean/sexpr_repo/sexpr_core.h"
static unsigned randfast(unsigned*x){unsigned v=*x;v^=v<<13;v^=v>>17;v^=v<<5;return *x=v;}
static int heuristic(const SRWorld*w){
    if(!w->mode){
        if(w->nodes[2].op==SR_MUL||w->nodes[3].op==SR_MUL)return SR_SQUARE_MUL;
        if(w->nodes[6].op!=SR_DOT2)return SR_FUSE_DOT;
    }else if(w->nodes[3].live && w->nodes[3].op==SR_ADD)return SR_ELIM_ZERO;
    if((w->imports&w->required_imports)!=w->required_imports)return SR_REPAIR_IMPORT;
    if((w->registered&w->required_registration)!=w->required_registration)return SR_REGISTER_ENV;
    if((w->tests&w->required_tests)!=w->required_tests)return SR_ADD_TEST;
    if(w->duplicate_files)return SR_DEDUP_FILE;
    if(!w->validated)return SR_RUN_TESTS;
    return SR_COMMIT;
}
static double ticks(void){struct timespec t;timespec_get(&t,TIME_UTC);return (double)t.tv_sec+t.tv_nsec*1e-9;}
int main(void){
    const unsigned episodes=50000;unsigned commits=0,stepcount=0,random_commits=0;
    double start=ticks();
    for(unsigned seed=1;seed<=episodes;seed++){
        SRWorld w;sr_reset(&w,seed);
        while(!w.done){sr_step(&w,heuristic(&w));stepcount++;}
        commits+=w.committed;
    }
    double sec=ticks()-start;
    unsigned rng=0x1234567u;
    for(unsigned seed=1;seed<=episodes;seed++){
        SRWorld w;sr_reset(&w,seed);
        while(!w.done)sr_step(&w,(int)(randfast(&rng)%SR_ACTIONS));
        random_commits+=w.committed;
    }
    printf("episodes=%u baseline_verified=%u random_verified=%u steps=%u steps_per_sec=%.0f\n",
        episodes,commits,random_commits,stepcount,stepcount/sec);
    return commits==episodes?0:1;
}
