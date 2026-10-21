// PufferLib 5.0 Ocean projection of Household World.
// The full economic / nutrition / Beads engine is the Python household package.
// This fast native environment is an explicitly reduced-fidelity benchmark,
// NOT behaviorally equivalent to the complete household simulator.
#include <stdlib.h>
#include <math.h>
#include <stdio.h>
typedef float obs_t;
#include "pufferenv.h"
#include "puffervis.h"

#define OBS_SIZE 32
#define ACT_SIZES {8}
#define NUM_ATNS 1
#define HOUSEHOLD_PRODUCTS 6
#define HOUSEHOLD_DAYS 28
#define PUF_HOUSEHOLD_DEMO 1

struct Log { float perf, score, spending, served, waste, n; };
struct Env {
    Log log; int num_agents; unsigned int rng;
    Agent agents[1]; int tag, boundary_reached;
    int day, week_spend, total_spend, served;
    float inventory[HOUSEHOLD_PRODUCTS], price[HOUSEHOLD_PRODUCTS];
    float expired, acceptance, nutrition, cash, food_quality;
};

static const float nutrition[HOUSEHOLD_PRODUCTS] = {1.65f, 3.6f, .41f, 1.32f, .76f, 2.0f};
static const float base_cost[HOUSEHOLD_PRODUCTS] = {1.5f, .35f, .45f, .3f, .48f, .7f};
static const int shelf[HOUSEHOLD_PRODUCTS] = {3, 180, 8, 14, 5, 14};

static void hh_observe(Env* env) {
    obs_t* o = env->agents[0].observations;
    o[0] = (float)env->day/HOUSEHOLD_DAYS;
    o[1] = (float)(env->day%7)/7.0f;
    o[2] = env->cash/145.0f;
    o[3] = env->acceptance;
    o[4] = env->expired/5000.0f;
    o[5] = env->nutrition/6000.0f;
    for (int i=0; i<HOUSEHOLD_PRODUCTS; i++) {
        o[6+i] = env->inventory[i]/1000.0f;
        o[12+i] = env->price[i]/2.0f;
    }
    for (int i=18; i<OBS_SIZE; i++) o[i] = 0.0f;
    o[18] = (float)env->served/HOUSEHOLD_DAYS;
    o[19] = env->total_spend/500.0f;
}
void puf_init(Env* env, Dict* kwargs) {
    (void)kwargs;
    env->num_agents=1;
    env->agents[0].policy=0;
    env->agents[0].action_mask=NULL;
}
void puf_log(Log* log, Dict* out) {
    dict_set(out,"perf",log->perf);
    dict_set(out,"score",log->score);
    dict_set(out,"spending",log->spending);
    dict_set(out,"served",log->served);
    dict_set(out,"waste",log->waste);
    dict_set(out,"n",log->n);
}
void puf_reset(Env* env) {
    env->day=0;env->week_spend=0;env->total_spend=0;env->served=0;
    env->cash=145.0f;env->expired=0.0f;env->acceptance=.6f;
    env->nutrition=0.0f;env->food_quality=0.0f;
    for (int i=0;i<HOUSEHOLD_PRODUCTS;i++) {
        env->inventory[i]=(i==1?800.0f:0.0f);
        env->price[i]=base_cost[i];
    }
    hh_observe(env);
}
void puf_step(Env* env) {
    // The previous transition's terminal flag is consumed by the policy
    // before this call. Clear it only when beginning the next step.
    env->agents[0].terminals[0]=0.0f;
    if (env->day>=HOUSEHOLD_DAYS) puf_reset(env);
    int day=env->day;
    int act=(int)env->agents[0].actions[0];
    if (act<0 || act>7) act=0;
    if (day%7==0) { env->cash=145.0f;env->week_spend=0; }
    for (int j=0;j<HOUSEHOLD_PRODUCTS;j++) {
        env->price[j]=base_cost[j]*(0.82f + (rand_r(&env->rng)%46)/100.0f);
        // Each product is modeled at a coarse inventory and temperature resolution.
        if ((j==0 || j==4) && env->inventory[j]>0) {
            float spoil=env->inventory[j]/shelf[j];
            env->inventory[j]-=spoil;env->expired+=spoil;
        }
    }
    // Action controls which of two shared dinners and shopping policies to prefer.
    int vegetarian=(act==3 || act==4 || act==7);
    int ids[3]={vegetarian?3:0,1,vegetarian?4:2};
    float qty[3]={vegetarian?420.0f:440.0f,250.0f,vegetarian?380.0f:350.0f};
    float meal_cost=0.0f;
    float needed[3];
    for (int k=0;k<3;k++) {
        needed[k]=fmaxf(0.0f,qty[k]-env->inventory[ids[k]]);
        float mult=(act==1? .96f:act==2? .91f:1.0f);
        if (act==6) mult*=1.65f;
        meal_cost+=needed[k]*env->price[ids[k]]*mult/100.0f;
    }
    int serves=0;
    if (act!=5 && meal_cost<=env->cash) {
        for (int k=0;k<3;k++) env->inventory[ids[k]]+=needed[k];
        for (int k=0;k<3;k++) env->inventory[ids[k]]-=qty[k];
        env->cash-=meal_cost;
        env->total_spend+=(int)lroundf(meal_cost*100.0f);
        env->week_spend+=(int)lroundf(meal_cost*100.0f);
        env->served+=1;serves=1;
        env->nutrition+=qty[0]*nutrition[ids[0]]+qty[1]*nutrition[ids[1]]+qty[2]*nutrition[ids[2]];
        env->acceptance=.54f+(act==4?.14f:act==0?.09f:.03f);
    }
    env->agents[0].rewards[0]=(serves?3.0f+env->acceptance: -2.5f)
                                  -meal_cost*.08f -env->expired*.00003f;
    env->day++;
    if (env->day>=HOUSEHOLD_DAYS) {
        env->agents[0].terminals[0]=1.0f;
        env->log.perf+=(float)env->served/HOUSEHOLD_DAYS;
        env->log.score+=env->served;
        env->log.spending+=env->total_spend/100.0f;
        env->log.served+=env->served;
        env->log.waste+=env->expired;
        env->log.n++;
        // Autoreset for successive CPU headless evaluation episodes.
        // puf_reset preserves the aggregate log and the terminal flag,
        // exposing the next episode's initial observation to the policy.
        puf_reset(env);
    }
    hh_observe(env);
}
void puf_render(Env* env) {
    if (!IsWindowReady()) { InitWindow(1040,710,"Household World | PufferVis"); SetTargetFPS(30); }
    if (IsKeyDown(KEY_ESCAPE)) exit(0);
    BeginDrawing();
    ClearBackground(pv_color(19,30,29,255));
    PV_Camera cam = {515.0f,140.0f,42.0f,22.0f,37.0f};
    pv_tile(cam,0.0f,0.0f,9.3f,7.7f,pv_color(49,77,71,255));
    pv_tile(cam,9.5f,0.0f,8.5f,7.7f,pv_color(61,78,62,255));
    pv_tile(cam,0.0f,7.9f,9.3f,4.7f,pv_color(79,89,74,255));
    pv_tile(cam,9.5f,7.9f,8.5f,4.7f,pv_color(63,72,65,255));
    // Three merchants / display objects. No effects on the simulation.
    for (int i=0;i<3;i++) {
        const Color color=(i==0?pv_color(219,170,109,255):
           i==1?pv_color(146,198,204,255):pv_color(152,204,156,255));
        pv_prism(cam,10.5f+i*2.7f,2.5f,2.0f,1.5f,1.35f,color);
        pv_caption(cam,9.7f+i*2.7f,2.0f,2.2f,i==0?"CORNER":i==1?"VALUE":"FRESH",pv_color(240,240,216,255));
    }
    // Kitchen architecture, produced by the same portable primitive library.
    pv_prism(cam,1.3f,1.8f,1.3f,1.2f,2.2f,pv_color(215,230,215,255));
    pv_prism(cam,3.8f,1.8f,1.8f,1.4f,.85f,pv_color(180,219,208,255));
    pv_prism(cam,6.25f,1.8f,1.7f,1.5f,.85f,pv_color(74,96,91,255));
    pv_prism(cam,4.0f,4.7f,2.4f,1.8f,.88f,pv_color(220,178,126,255));
    pv_prism(cam,1.6f,5.7f,1.5f,1.1f,1.55f,pv_color(194,146,105,255));
    pv_prism(cam,5.2f,9.7f,2.8f,1.9f,.61f,pv_color(215,170,116,255));
    pv_prism(cam,13.5f,10.0f,4.0f,2.1f,.35f,pv_color(71,99,84,255));
    // Stock visualization uses actual native inventory values.
    const char* names[HOUSEHOLD_PRODUCTS]={"PROTEIN","RICE","GREEN","BEANS","FRESH","ROOT"};
    for(int i=0;i<HOUSEHOLD_PRODUCTS;i++) {
        if(env->inventory[i] < .01f)continue;
        float h=.21f+fminf(1.0f,env->inventory[i]/900.0f)*.65f;
        float x=2.5f+(i%3)*.8f,z=6.6f+(i/3)*.75f;
        pv_prism(cam,x,z,.65f,.65f,h,pv_color(151,195,135,255));
        pv_caption(cam,x,h+.3f,z,names[i],pv_color(238,235,209,255));
    }
    pv_person(cam,4.0f,11.1f,pv_color(234,181,126,255));
    pv_person(cam,5.4f,11.1f,pv_color(191,155,166,255));
    pv_person(cam,6.8f,11.1f,pv_color(128,187,168,255));
    DrawText("PUFFERVIS  /  HOUSEHOLD WORLD",26,25,25,pv_color(237,239,217,255));
    DrawText("SCENE VISUALIZATION / NATIVE OCEAN",27,60,13,pv_color(150,183,170,255));
    DrawText(TextFormat("DAY %02d / %02d    DINNERS %d    BALANCE $%.2f",env->day,HOUSEHOLD_DAYS,
            env->served,env->cash),26,605,21,pv_color(237,239,217,255));
    pv_progress(27,645,360,(float)env->day/HOUSEHOLD_DAYS,pv_color(161,216,174,255));
    DrawText("SYNTHETIC MODEL / AUTHORED VISUAL LAYOUT / NOT FOOD-SAFETY GUIDANCE",27,672,12,
             pv_color(160,185,168,255));
    EndDrawing();
    puf_web_vsync();
}
void puf_close(Env* env) { (void)env; if (IsWindowReady()) CloseWindow(); }
