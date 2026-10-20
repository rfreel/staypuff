/* Frontier Kombat synthetic C99/C11 state machine with contiguous SoA I/O.
 * Not an emulation of an existing fighting game. Invariants, not marketing labels,
 * define the fidelity boundary. No external calls within the step loop.
 */
#include <stdint.h>
#include <stddef.h>
#include <math.h>
#include <string.h>

#define OBS 24
#define MAX_FRAMES 900

typedef struct {
    int32_t env_idx,env_id,ood,step,episodes;
    uint32_t seed;
    float severity;
    float p1_x,p1_y,p1_vx,p1_hp,p1_meter,p1_heat;
    int32_t p1_state,p1_move,p1_frame,p1_stun,p1_invuln,p1_charge,dyck;
    float p2_x,p2_y,p2_vx,p2_hp;
    int32_t p2_state,p2_move,p2_frame,p2_stun,p2_morph;
    float proj_x,proj_v;
    int32_t proj_active;
    float metric,phase;
    int32_t parity,fatality;
    uint8_t history[16],buttons[16];
    int32_t hist_idx,last_button,p1_input_dir,p1_input_btn,wins_p1,wins_p2;
    float cumulative,last_episode_return;
    int32_t verdict;
    uint32_t rng;
} State;

size_t kombat_state_size(void){return sizeof(State);}
size_t kombat_state_offset(int i){
    static const size_t offsets[]={
        offsetof(State,env_idx),offsetof(State,env_id),offsetof(State,ood),
        offsetof(State,step),offsetof(State,episodes),offsetof(State,seed),
        offsetof(State,severity),offsetof(State,p1_x),offsetof(State,p1_y),
        offsetof(State,p1_vx),offsetof(State,p1_hp),offsetof(State,p1_meter),
        offsetof(State,p1_heat),offsetof(State,p1_state),offsetof(State,p1_move),
        offsetof(State,p1_frame),offsetof(State,p1_stun),offsetof(State,p1_invuln),
        offsetof(State,p1_charge),offsetof(State,dyck),offsetof(State,p2_x),
        offsetof(State,p2_y),offsetof(State,p2_vx),offsetof(State,p2_hp),
        offsetof(State,p2_state),offsetof(State,p2_move),offsetof(State,p2_frame),
        offsetof(State,p2_stun),offsetof(State,p2_morph),offsetof(State,proj_x),
        offsetof(State,proj_v),offsetof(State,proj_active),offsetof(State,metric),
        offsetof(State,phase),offsetof(State,parity),offsetof(State,fatality),
        offsetof(State,history),offsetof(State,buttons),offsetof(State,hist_idx),offsetof(State,last_button),
        offsetof(State,p1_input_dir),offsetof(State,p1_input_btn),
        offsetof(State,wins_p1),offsetof(State,wins_p2),offsetof(State,cumulative),
        offsetof(State,last_episode_return),offsetof(State,verdict),offsetof(State,rng)
    };
    if(i<0||i>=(int)(sizeof(offsets)/sizeof(offsets[0])))return (size_t)-1;
    return offsets[i];
}
static inline float clip(float x,float lo,float hi){return x<lo?lo:x>hi?hi:x;}
static inline uint32_t random32(State*s){uint32_t x=s->rng;x^=x<<13;x^=x>>17;x^=x<<5;return s->rng=x?x:1234567u;}
static inline float rnd(State*s){return (float)(random32(s)>>8)*(1.f/16777216.f);}

typedef struct {int start,active,recover,hitstun,blockstun;float damage,reach;} Move;
static const Move MOVES[11]={
    {0,0,0,0,0,0,0}, {3,2,6,11,9,5.5f,54}, {8,4,18,19,14,11,68},
    {4,3,8,12,10,6.5f,60}, {9,4,22,20,12,12.5f,74},
    {11,2,26,16,12,10,42}, {3,8,28,24,10,14,56},
    {6,3,12,17,14,11.5f,48}, {4,3,16,26,0,16.5f,62},
    {1,3,8,0,0,0,0}, {4,4,12,40,5,45,90}
};
static inline void observe(const State*s,float*o){
    float dx=(s->p2_x-s->p1_x)/400.f;
    o[0]=clip(s->p1_x/400,-1,1);o[1]=clip(s->p1_y/200,0,1);
    float apparent_p2=s->p2_x;
    if(s->env_id==10 && s->ood)apparent_p2-=s->p2_vx*(1+(s->step%5));
    o[2]=clip(apparent_p2/400,-1,1);o[3]=clip(s->p2_y/200,0,1);
    o[4]=clip((apparent_p2-s->p1_x)/400,-2,2);o[5]=dx;
    o[6]=clip(s->p1_hp/100,0,1);o[7]=clip(s->p2_hp/100,0,1);
    o[8]=clip(s->p1_meter/100,0,1);o[9]=clip(s->p1_heat/15,0,2);
    o[10]=(float)s->p1_state/9;o[11]=(float)s->p2_state/9;
    o[12]=(float)s->p1_move/10;o[13]=(float)s->p2_move/10;
    o[14]=clip((float)s->p1_frame/40,0,1);o[15]=clip((float)s->p2_frame/40,0,1);
    o[16]=clip((float)s->p1_charge/12,0,2);o[17]=clip((float)s->dyck/4,0,1);
    o[18]=s->proj_active?clip((s->proj_x-s->p1_x)/400,-2,2):0;
    o[19]=clip(s->metric/2,0,1);o[20]=clip(s->phase/2,-1,1);
    o[21]=(float)(s->parity&7)/7;o[22]=(float)s->fatality/4;
    o[23]=(float)s->env_id/19;
}
static void reset_slot(State*s,float*o){
    uint32_t key=s->seed+0x9e3779b9u*(uint32_t)(s->episodes+1);
    s->rng=key?key:0x12345678u;
    s->step=0;s->p1_x=-42;s->p2_x=42;s->p1_y=0;s->p2_y=0;
    s->p1_vx=0;s->p2_vx=0;s->p1_hp=100;s->p2_hp=100;
    s->p1_meter=25;s->p1_heat=0;s->p1_state=0;s->p2_state=0;
    s->p1_move=0;s->p2_move=0;s->p1_frame=0;s->p2_frame=0;
    s->p1_stun=0;s->p2_stun=0;s->p1_invuln=0;s->p1_charge=0;s->dyck=0;
    s->p2_morph=(int)(random32(s)%4);s->proj_x=0;s->proj_v=0;
    s->proj_active=0;s->metric=.37f;s->phase=.11f;s->parity=1;
    s->fatality=0;memset(s->history,0,sizeof(s->history));
    memset(s->buttons,0,sizeof(s->buttons));
    s->hist_idx=0;s->last_button=0;s->p1_input_dir=4;s->p1_input_btn=0;
    s->cumulative=0;s->verdict=1;
    observe(s,o);
}
void c_reset_batch(State*states,int32_t n,float*obs){
    #pragma omp parallel for schedule(static) if(n>=256)
    for(int i=0;i<n;i++)reset_slot(states+i,obs+(size_t)i*OBS);
}
static inline int motion_qcf(const State*s){
    int a=s->history[(s->hist_idx-3+16)&15];
    int b=s->history[(s->hist_idx-2+16)&15];
    int c=s->history[(s->hist_idx-1+16)&15];
    return (a==1 && (b==2 || b==5) && c==5);
}
/* Apply 20 distinct synthetic modifier families, most on confirmed impacts.
 * Return >0 damage multiplier; negative means a counter is taken instead.
 */
static float modifier(State*s,int dir,int btn,int move){
    if(!s->ood)return 1.f;
    switch(s->env_id){
    case 0:return move==5?(s->metric>=1.f?1.5f:-.8f):1.f;
    case 1:return move==6?(s->parity&1?-.9f:1.65f):1.f;
    case 2:
        if(move==7){if(s->p1_charge>=3 && s->p1_charge<=8){s->p1_charge=0;return 1.7f;}return -.7f;}
        return 1.f;
    case 3:return ((s->step/6)%4)==(btn-1)?1.4f:.4f;
    case 4:return move==8?(s->metric>1.2f?-.8f:1.6f):1.f;
    case 5:
        if(btn==1){s->dyck++;return .7f;}
        if(btn==4){if(s->dyck>0){s->dyck--;return 1.75f;}return -.8f;}
        return .5f;
    case 6: {int tape=s->buttons[(s->hist_idx-12+16)&15];return (tape&1)==(btn&1)?1.5f:-.7f;}
    case 7: {int same=0;for(int i=0;i<16;i++)same+=s->buttons[i]==(uint8_t)btn;
        return same>12?-.9f:1.4f;}
    case 8: return btn==(1+((s->p2_morph+2)&3))?1.7f:.5f;
    case 9: return move==10?((s->p2_hp<=22 && fabsf(s->p2_x-s->p1_x)>=62 &&
        fabsf(s->p2_x-s->p1_x)<=86)?4.f:-1.f):1.f;
    case 10:return s->phase>0.f && btn!=6?-.7f:1.35f;
    case 11:return fabsf(s->phase)>.5f?(btn==3?1.6f:-.5f):1.1f;
    case 12:return (s->parity&1) && move!=8?-.7f:1.4f;
    case 13:return (s->phase>0 ? btn==4 : btn==3)?1.6f:-.65f;
    case 14:return (s->parity&1)?(dir==3?1.5f:-.7f):1.1f;
    case 15:return s->p1_heat>4.f?-.9f:1.25f;
    case 16:return btn==(1+((s->parity+s->step/45)&3))?1.6f:.35f;
    case 17:return btn==s->last_button?.1f:1.5f;
    case 18:return s->metric>.65f?(btn==6?1.6f:-.9f):1.2f;
    case 19:return btn==s->last_button?-.85f:1.5f;
    default:return 1.f;
    }
}
static inline int move_from_buttons(const State*s,int dir,int btn){
    if(btn>=1&&btn<=4)return btn;
    if(btn==5){if(dir==1)return 6;if(dir==3)return 7;
        return motion_qcf(s)?5:8;}
    if(btn==6)return 9;
    if(btn==7)return 10;
    return 0;
}
static void frame(State*s,int action,float*obs,float*reward,uint8_t*term,uint8_t*trunc){
    s->step++;
    *reward=0.f;*term=0;*trunc=0;
    int dir=action/8,btn=action%8;
    s->history[s->hist_idx&15]=(uint8_t)dir;
    s->buttons[s->hist_idx&15]=(uint8_t)btn;
    s->hist_idx=(s->hist_idx+1)&15;
    float facing=s->p2_x>=s->p1_x?1.f:-1.f;
    float pre_hp1=s->p1_hp,pre_hp2=s->p2_hp;
    if(s->env_id==18 && s->ood)s->metric=3.92f*s->metric*(1.f-s->metric);
    else s->metric=1.f+.55f*cosf(.11f*s->step+s->env_id);
    s->phase=sinf(.09f*s->step+.5f*s->env_id);
    if(s->env_id==8 && s->ood && s->step%90==0)s->p2_morph=(s->p2_morph+1)&3;
    if(s->p1_invuln>0)s->p1_invuln--;
    if(s->p1_heat>0)s->p1_heat=fmaxf(0.f,.96f*s->p1_heat-.08f);
    if(s->p1_stun>0){s->p1_stun--;s->p1_state=7;}
    if(s->p2_stun>0){s->p2_stun--;s->p2_state=7;}
    if(s->p1_stun==0){
        if(s->p1_move){
            Move m=MOVES[s->p1_move];s->p1_frame++;
            if(s->p1_frame<=m.start)s->p1_state=4;
            else if(s->p1_frame<=m.start+m.active)s->p1_state=5;
            else if(s->p1_frame<=m.start+m.active+m.recover)s->p1_state=6;
            else {s->p1_move=0;s->p1_frame=0;s->p1_state=0;}
            if(s->p1_state==5 && s->p1_frame==m.start+1){
                if(s->p1_move==5||s->p1_move==7){
                    s->proj_active=1;s->proj_x=s->p1_x+facing*24;
                    s->proj_v=facing*(s->p1_move==5?(8.f*s->metric):11.f);
                } else if(s->p1_move==9){s->p1_invuln=3;}
                else{
                    float dist=fabsf(s->p2_x-s->p1_x);
                    if(s->env_id==4&&s->ood)dist*=sqrtf(fmaxf(.2f, s->metric));
                    if(s->env_id==11&&s->ood)dist+=35*fabsf(s->phase);
                    if(dist<=m.reach && s->p2_stun==0){
                        float mult=modifier(s,s->p1_input_dir,s->p1_input_btn,s->p1_move);
                        if(mult>0){s->p2_hp=fmaxf(0,s->p2_hp-m.damage*mult);s->p2_stun=m.hitstun;
                            s->last_button=s->p1_input_btn;
                            s->p1_meter=fminf(100,s->p1_meter+6);}
                        else{s->p1_hp=fmaxf(0,s->p1_hp+m.damage*mult*fmaxf(.3f,s->severity));
                            s->p1_stun=10;}
                    }
                }
            }
        }else{
            int effdir=(s->env_id==14 && s->ood && (s->parity&1))?(dir==3?5:dir==5?3:dir):dir;
            s->p1_vx=(effdir==5?3.8f:effdir==3?-2.8f:0)*facing;
            s->p1_state=(effdir==3||effdir==5)?1:0;
            if(effdir==3)s->p1_charge++;
            else if(s->p1_charge>0)s->p1_charge--;
            if(btn && btn<=7){
                int m=move_from_buttons(s,dir,btn);
                if(m){s->p1_move=m;s->p1_frame=0;s->p1_state=4;
                    s->p1_input_dir=dir;s->p1_input_btn=btn;
                    if(s->env_id==1 && s->ood && m==6){s->p1_invuln=(s->parity&1)?0:5;}
                    if(s->env_id==15 && s->ood){s->p1_heat+=1.4f;}
                    if(s->env_id==12 && s->ood)s->parity++;
                    if(s->env_id==17 && s->ood && m!=9){
                        /* Preserve prior button until impact for repeat check. */
                    }
                }
            }
            if(s->env_id==15 && s->ood && !btn)s->p1_heat=fmaxf(0.f,s->p1_heat-.55f);
        }
    }
    if(s->p2_stun==0){
        if(s->p2_move){
            Move m=MOVES[s->p2_move];s->p2_frame++;
            if(s->p2_frame<=m.start)s->p2_state=4;
            else if(s->p2_frame<=m.start+m.active)s->p2_state=5;
            else if(s->p2_frame<=m.start+m.active+m.recover)s->p2_state=6;
            else{s->p2_move=0;s->p2_frame=0;s->p2_state=0;}
            if(s->p2_state==5&&s->p2_frame==m.start+1){
                if(fabsf(s->p1_x-s->p2_x)<=m.reach && s->p1_invuln==0){
                    s->p1_hp=fmaxf(0,s->p1_hp-m.damage*.55f);
                    s->p1_stun=m.hitstun;
                }
            }
        }else{
            float dist=fabsf(s->p2_x-s->p1_x);
            if(dist>56){s->p2_vx=-facing*3.0f;s->p2_state=1;}
            else{s->p2_vx=0;
                if(rnd(s)<.19f){s->p2_move=(s->env_id==8 && s->ood)?(s->p2_morph+1):3;
                    s->p2_frame=0;s->p2_state=4;}
            }
        }
    }
    s->p1_x=clip(s->p1_x+s->p1_vx,-320,320);
    s->p2_x=clip(s->p2_x+s->p2_vx,-320,320);
    if(s->env_id==13&&s->ood){s->p2_y=12.f*fabsf(s->phase);s->p2_x=clip(s->p2_x+2.f*s->phase,-320,320);}
    if(s->env_id==14&&s->ood && s->step%120==0){s->p2_x=-s->p2_x;s->parity^=1;}
    float sep=s->p2_x-s->p1_x;
    if(fabsf(sep)<28){float push=(28-fabsf(sep))*.5f;
        s->p1_x+=sep>=0?-push:push;s->p2_x+=sep>=0?push:-push;}
    if(s->proj_active){
        s->proj_x+=s->proj_v;
        if(fabsf(s->proj_x)>340)s->proj_active=0;
        else if(fabsf(s->proj_x-s->p2_x)<20){
            s->proj_active=0;
            float mult=modifier(s,s->p1_input_dir,s->p1_input_btn,s->p1_move);
            if(mult>0)s->p2_hp=fmaxf(0,s->p2_hp-10.f*mult);
            else s->p1_hp=fmaxf(0,s->p1_hp+8.f*mult);
        }
    }
    if(s->env_id==9 && s->ood && s->p2_hp<22){
        if(btn==7 && fabsf(s->p2_x-s->p1_x)>=62 && fabsf(s->p2_x-s->p1_x)<=86){
            s->fatality++;if(s->fatality>=3)s->p2_hp=0;
        }
    }
    /* Last successful initiating button changes only upon a confirmed hit. */
    float inflicted=pre_hp2-s->p2_hp,taken=pre_hp1-s->p1_hp;
    *reward=.10f*inflicted-.13f*taken-.001f;
    s->cumulative+=*reward;
    if(s->p1_hp<=0||s->p2_hp<=0||s->step>=MAX_FRAMES){
        if(s->step>=MAX_FRAMES && s->p1_hp>0 && s->p2_hp>0)*trunc=1;
        else *term=1;
        if(s->p1_hp>s->p2_hp){s->wins_p1++;*reward+=2.f;}
        else if(s->p2_hp>s->p1_hp){s->wins_p2++;*reward-=2.f;}
        s->cumulative+=(*reward-.10f*inflicted+.13f*taken+.001f);
        s->last_episode_return=s->cumulative;
        s->episodes++;
        reset_slot(s,obs);
    }else observe(s,obs);
    s->verdict=(isfinite(s->p1_x)&&isfinite(s->p2_x)&&isfinite(*reward)&&
        isfinite(s->metric)&&s->p1_hp>=0&&s->p2_hp>=0 &&s->p1_hp<=100&&s->p2_hp<=100)?1:-1;
}
void c_step_batch(State*states,int32_t n,const int32_t*actions,float*obs,
                  float*rewards,uint8_t*term,uint8_t*trunc){
    #pragma omp parallel for schedule(static) if(n>=256)
    for(int i=0;i<n;i++){
        int a=actions[i];if(a<0||a>=72)a=32;
        frame(states+i,a,obs+(size_t)i*OBS,rewards+i,term+i,trunc+i);
    }
}
