#pragma once
#include <stdint.h>
#include <stddef.h>
typedef struct Env Env;
typedef struct Log Log;
typedef struct Agent{obs_t *observations;float *actions;float *rewards;float *terminals;unsigned char *action_mask;int policy;}Agent;
typedef struct Dict {float placeholder;} Dict;
void dict_set(Dict*out,const char*name,float value);
typedef struct Color{uint8_t r,g,b,a;}Color;
static const Color RAYWHITE={255,255,255,255},SKYBLUE={80,190,250,255},GREEN={0,255,0,255},RED={255,0,0,255},ORANGE={255,160,0,255},GRAY={150,150,150,255};
int IsWindowReady(void);void InitWindow(int,int,const char*);void SetTargetFPS(int);int IsKeyDown(int);
void BeginDrawing(void);void EndDrawing(void);void ClearBackground(Color);
void DrawText(const char*,int,int,int,Color);const char*TextFormat(const char*,...);
void DrawRectangle(int,int,int,int,Color);void DrawCircle(int,int,int,Color);
void CloseWindow(void);void puf_web_vsync(void);
#define KEY_ESCAPE 256
