// PufferLib 5.0 native Ocean adaptor, sharing the synthetic C kernel used by
// projects/frontier-kombat/frontier_kombat_puffer.py.
// Each vectorized Env slot selects one of 20 OOD scenarios at initialization.
#include <stdlib.h>
#include <stdio.h>
#include <math.h>
typedef float obs_t;
#include "pufferenv.h"
#define OBS_SIZE 24
#define ACT_SIZES {72}
#define NUM_ATNS 1
#include "../../projects/frontier-kombat/frontier_kombat_kernel.c"
struct Log {float perf,score,wins,losses,n;};
struct Env {
    Log log;int num_agents;unsigned int rng;
    Agent agents[1];int tag,boundary_reached;
    State state;
    float accumulated;
};
void puf_init(Env*e,Dict*kwargs){
    (void)kwargs;e->num_agents=1;e->agents[0].policy=0;e->agents[0].action_mask=NULL;
}
void puf_log(Log*l,Dict*out){
    dict_set(out,"perf",l->perf);dict_set(out,"score",l->score);
    dict_set(out,"wins",l->wins);dict_set(out,"losses",l->losses);dict_set(out,"n",l->n);
}
void puf_reset(Env*e){
    e->state.env_idx=(int)(e->rng&0x7fffffff);
    e->state.env_id=(int)(rand_r(&e->rng)%20);
    e->state.ood=1;e->state.severity=1.0f;
    e->state.seed=rand_r(&e->rng);
    e->state.episodes=0;e->state.wins_p1=0;e->state.wins_p2=0;
    e->accumulated=0.f;
    c_reset_batch(&e->state,1,e->agents[0].observations);
}
void puf_step(Env*e){
    Agent*a=&e->agents[0];
    int32_t action=(int32_t)a->actions[0];
    float rew=0;uint8_t term=0,trunc=0;
    int wins_before=e->state.wins_p1;
    c_step_batch(&e->state,1,&action,a->observations,&rew,&term,&trunc);
    a->rewards[0]=rew;a->terminals[0]=(float)(term||trunc);
    e->accumulated+=rew;
    if(term||trunc){
        float win=e->state.wins_p1>wins_before?1.f:0.f;
        e->log.perf+=win;e->log.wins+=win;e->log.losses+=1.f-win;
        e->log.score+=e->state.last_episode_return;e->log.n++;
        puf_reset(e);
        // puf_reset intentionally changes environment task only after episode.
        a->terminals[0]=1.f;
    }
}
void puf_render(Env*e){
    if(!IsWindowReady()){InitWindow(980,550,"Frontier Kombat / 20 synthetic OOD arenas");SetTargetFPS(60);}
    if(IsKeyDown(KEY_ESCAPE))exit(0);
    BeginDrawing();ClearBackground((Color){13,16,25,255});
    DrawText("FRONTIER KOMBAT  /  SYNTHETIC OOD",32,32,28,RAYWHITE);
    DrawText(TextFormat("ARENA E%02d  /  FRAME %d",e->state.env_id+1,e->state.step),32,102,22,SKYBLUE);
    DrawRectangle(95,190,(int)(350*clip(e->state.p1_hp/100.f,0,1)),26,GREEN);
    DrawRectangle(535,190,(int)(350*clip(e->state.p2_hp/100.f,0,1)),26,RED);
    DrawCircle(490+(int)e->state.p1_x,340,21,SKYBLUE);
    DrawCircle(490+(int)e->state.p2_x,340,21,ORANGE);
    DrawText("60Hz frame model / not an arcade emulator or GGPO implementation",32,490,17,GRAY);
    EndDrawing();puf_web_vsync();
}
void puf_close(Env*e){(void)e;if(IsWindowReady())CloseWindow();}
