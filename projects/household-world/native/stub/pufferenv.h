/* Compile-time only PufferEnv stub for adapter syntax checks. Not a runtime. */
#ifndef HOUSEHOLD_STUB_PUFFERENV_H
#define HOUSEHOLD_STUB_PUFFERENV_H
#include <stdlib.h>
typedef struct Env Env;
typedef struct Log Log;
typedef struct Dict { int placeholder; } Dict;
typedef struct Agent {
    obs_t* observations; float* actions; float* rewards; float* terminals;
    unsigned char* action_mask; int policy;
} Agent;
typedef struct { unsigned char r,g,b,a; } Color;
#define KEY_ESCAPE 256
static int IsWindowReady(void) {return 0;}
static int IsKeyDown(int k) {(void)k;return 0;}
static void InitWindow(int w,int h,const char*s){(void)w;(void)h;(void)s;}
static void SetTargetFPS(int f){(void)f;}
static void ClearBackground(Color c){(void)c;}
static void DrawText(const char*s,int x,int y,int z,Color c){(void)s;(void)x;(void)y;(void)z;(void)c;}
static const char*TextFormat(const char*s,...) {(void)s;return "";}
static void BeginDrawing(void){}
static void EndDrawing(void){}
static void CloseWindow(void){}
static void puf_web_vsync(void){}
static void dict_set(Dict*d,const char*s,float v){(void)d;(void)s;(void)v;}
#endif
