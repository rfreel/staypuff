/* PufferVis v1: tiny, dependency-free (apart from raylib drawing API) isometric
 * scene primitives for Ocean CPU viewers. This header owns no game state.
 * Use from puf_render only; NEVER call these while stepping/training.
 * Expects Color, Vector2, DrawTriangle, DrawLineEx, DrawCircleV, DrawText,
 * DrawRectangle from the active raylib or test adapter.
 */
#ifndef PUFFERVIS_H
#define PUFFERVIS_H
#include <math.h>
#include <stdio.h>

typedef struct PV_Camera {
    float origin_x, origin_y, tile_w, tile_h, height_scale;
} PV_Camera;

static inline Vector2 pv_project(PV_Camera camera, float x, float height, float z) {
    return (Vector2){ camera.origin_x+(x-z)*camera.tile_w*0.5f,
                      camera.origin_y+(x+z)*camera.tile_h*0.5f-height*camera.height_scale };
}
static inline Color pv_color(unsigned char r,unsigned char g,unsigned char b,unsigned char a) {
    return (Color){r,g,b,a};
}
static inline Color pv_shade(Color c,float f) {
    return (Color){(unsigned char)fminf(255,c.r*f), (unsigned char)fminf(255,c.g*f),
                   (unsigned char)fminf(255,c.b*f),c.a};
}
static inline void pv_quad(Vector2 a,Vector2 b,Vector2 c,Vector2 d,Color color) {
    DrawTriangle(a,b,c,color);
    DrawTriangle(a,c,d,color);
}
static inline void pv_prism(PV_Camera camera,float x,float z,float w,float depth,float h,Color top) {
    const float u=x-w*0.5f,v=z-depth*0.5f;
    Vector2 t0=pv_project(camera,u,h,v),t1=pv_project(camera,u+w,h,v);
    Vector2 t2=pv_project(camera,u+w,h,v+depth),t3=pv_project(camera,u,h,v+depth);
    Vector2 b1=pv_project(camera,u+w,0,v),b2=pv_project(camera,u+w,0,v+depth);
    Vector2 b3=pv_project(camera,u,0,v+depth);
    pv_quad(t1,t2,b2,b1,pv_shade(top,.69f));
    pv_quad(t2,t3,b3,b2,pv_shade(top,.56f));
    pv_quad(t0,t1,t2,t3,top);
}
static inline void pv_tile(PV_Camera camera,float x,float z,float w,float d,Color color) {
    Vector2 a=pv_project(camera,x,0,z),b=pv_project(camera,x+w,0,z);
    Vector2 c=pv_project(camera,x+w,0,z+d),dd=pv_project(camera,x,0,z+d);
    pv_quad(a,b,c,dd,color);
    Color edge=pv_shade(color,1.25f);
    DrawLineEx(a,b,.7f,edge);DrawLineEx(b,c,.7f,edge);
    DrawLineEx(c,dd,.7f,edge);DrawLineEx(dd,a,.7f,edge);
}
static inline void pv_person(PV_Camera camera,float x,float z,Color coat) {
    Vector2 feet=pv_project(camera,x,0,z),body=pv_project(camera,x,.45f,z),head=pv_project(camera,x,.75f,z);
    DrawLineEx(body,feet,3.0f,coat);
    DrawCircleV(body,7.5f,coat);
    DrawCircleV(head,6.5f,pv_color(230,195,157,255));
}
static inline void pv_caption(PV_Camera camera,float x,float height,float z,const char *caption,Color color) {
    Vector2 point=pv_project(camera,x,height,z);
    DrawText(caption,(int)point.x,(int)point.y,11,color);
}
static inline void pv_progress(float x,float y,float w,float fraction,Color fill) {
    fraction=fmaxf(0.0f,fminf(1.0f,fraction));
    DrawRectangle((int)x,(int)y,(int)w,7,pv_color(59,77,70,255));
    DrawRectangle((int)x,(int)y,(int)(w*fraction),7,fill);
}
#endif
