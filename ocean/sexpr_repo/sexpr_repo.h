// PufferLib 5.0 synthetic repository self-maintenance / typed S-expression world.
// This is a macro-action RL environment, not an unrestricted code executor.
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
typedef float obs_t;
#include "pufferenv.h"
#include "sexpr_core.h"
#define OBS_SIZE 40
#define ACT_SIZES {14}
#define NUM_ATNS 1
struct Log {float perf,score,passes,edits,n;};
struct Env {
    Log log; int num_agents; unsigned int rng;
    Agent agents[1]; int tag,boundary_reached;
    SRWorld world;
};
static void sr_observe(Env*e){
    SRWorld*w=&e->world;float*o=e->agents[0].observations;
    for(int i=0;i<OBS_SIZE;i++)o[i]=0;
    o[0]=(float)w->step/SR_MAX_STEPS;o[1]=(float)w->mode;
    o[2]=sr_cost(w)/12.f;o[3]=sr_health(w)/10.f;
    o[4]=(float)__builtin_popcount(w->imports& w->required_imports)/8.f;
    o[5]=(float)__builtin_popcount(w->required_imports)/8.f;
    o[6]=(float)__builtin_popcount(w->registered & w->required_registration)/8.f;
    o[7]=(float)__builtin_popcount(w->required_registration)/8.f;
    o[8]=(float)__builtin_popcount(w->tests & w->required_tests)/8.f;
    o[9]=(float)__builtin_popcount(w->required_tests)/8.f;
    o[10]=(float)w->duplicate_files/4.f;o[11]=(float)w->validated;
    o[12]=(float)w->committed;o[13]=(float)w->nodes[2].op/10.f;
    o[14]=(float)w->nodes[3].op/10.f;o[15]=(float)w->nodes[6].op/10.f;
    o[16]=(float)sr_node_count(w)/SR_NODES;o[17]=(float)sr_verify_expr(w);
    o[18]=(float)sr_verify_repo(w);o[19]=w->last_reward/3.f;
    for(int i=0;i<10;i++)o[20+i]=(float)((w->imports>>i)&1);
    for(int i=0;i<5;i++)o[30+i]=(float)((w->tests>>i)&1);
    for(int i=0;i<5;i++)o[35+i]=(float)((w->registered>>i)&1);
}
void puf_init(Env*e,Dict*kwargs){(void)kwargs;e->num_agents=1;e->agents[0].policy=0;e->agents[0].action_mask=NULL;}
void puf_log(Log*l,Dict*out){dict_set(out,"perf",l->perf);dict_set(out,"score",l->score);dict_set(out,"passes",l->passes);dict_set(out,"edits",l->edits);dict_set(out,"n",l->n);}
void puf_reset(Env*e){sr_reset(&e->world,rand_r(&e->rng));sr_observe(e);}
void puf_step(Env*e){
    Agent*a=&e->agents[0];a->terminals[0]=0;
    SRWorld*w=&e->world;int action=(int)a->actions[0];
    a->rewards[0]=sr_step(w,action);
    if(w->done){
        e->log.perf+=w->committed?1.f:0.f;
        e->log.score+=w->cumulative;
        e->log.passes+=sr_verify_repo(w)&&sr_verify_expr(w);
        e->log.edits+=w->step;e->log.n++;
        a->terminals[0]=1; puf_reset(e);
    }else sr_observe(e);
}
void puf_render(Env*e){
    if(!IsWindowReady()){InitWindow(960,540,"Staypuff / S-Expression Repo RL");SetTargetFPS(30);}
    if(IsKeyDown(KEY_ESCAPE))exit(0);
    BeginDrawing();ClearBackground((Color){17,25,28,255});
    DrawText("STAYPUFF / SELF-MAINTAINING REPOSITORY",35,35,25,RAYWHITE);
    DrawText(TextFormat("EPISODE STEP  %d / %d",e->world.step,SR_MAX_STEPS),35,130,22,SKYBLUE);
    DrawText(TextFormat("EXPR COST  %.1f  |  REPO HEALTH  %.2f",sr_cost(&e->world),sr_health(&e->world)),35,185,22,RAYWHITE);
    DrawText(TextFormat("VALIDATED  %s  |  COMMITTED  %s",e->world.validated?"YES":"NO",e->world.committed?"YES":"NO"),35,240,22,GREEN);
    DrawText("Synthetic tasks. No source files or real branches are modified during training.",35,455,17,GRAY);
    EndDrawing();puf_web_vsync();
}
void puf_close(Env*e){(void)e;if(IsWindowReady())CloseWindow();}
