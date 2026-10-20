#ifndef SEXPR_CORE_H
#define SEXPR_CORE_H
/* A compact, deterministic, allocation-free simulator: no source code or tests execute here.
 * All mutable task state is private to the simulated world. The verifier is independent.
 */
#include <stdint.h>
#include <string.h>
#include <math.h>

#define SR_NODES 12
#define SR_FILES 12
#define SR_MAX_STEPS 24
#define SR_ACTIONS 14
/* Typed expression opcodes, immutable arity/semantics within a world version. */
enum {SR_ZERO,SR_ONE,SR_X,SR_Y,SR_ADD,SR_MUL,SR_SQUARE,SR_DOT2,SR_SUB,SR_MIN,SR_MAX};
enum {SR_SQUARE_MUL,SR_FUSE_DOT,SR_ELIM_ZERO,SR_COMMUTE,SR_REPLACE_ADD_SUB,
      SR_REPAIR_IMPORT,SR_REGISTER_ENV,SR_ADD_TEST,SR_DEDUP_FILE,SR_RUN_TESTS,
      SR_COMMIT,SR_ROLLBACK,SR_WAIT,SR_STOP};
typedef struct {uint8_t op,a,b;uint8_t live;} SRNode;
typedef struct {
    SRNode nodes[SR_NODES];
    uint8_t root,mode,step,done,validated,committed;
    uint16_t imports, required_imports, registered, required_registration;
    uint16_t tests, required_tests, duplicate_files;
    uint16_t credited_imports,credited_registration,credited_tests;
    uint8_t credited_dups,credited_squares,credited_fusion,credited_zero;
    uint8_t snapshot_valid, snapshot_root;
    SRNode snapshot_nodes[SR_NODES];
    uint16_t snapshot_imports,snapshot_registered,snapshot_tests,snapshot_dups;
    float cumulative, last_reward, prev_health;
    uint32_t rng;
} SRWorld;
static inline uint32_t sr_rand(SRWorld *w){uint32_t x=w->rng;x^=x<<13;x^=x>>17;x^=x<<5;w->rng=x;return x;}
static inline int sr_node_count(const SRWorld*w){int n=0;for(int i=0;i<SR_NODES;i++)n+=w->nodes[i].live!=0;return n;}
static inline float sr_cost(const SRWorld*w){
    float c=0;for(int i=0;i<SR_NODES;i++)if(w->nodes[i].live){
        switch(w->nodes[i].op){case SR_ADD:case SR_SUB:c+=1;break;
            case SR_MUL:case SR_SQUARE:c+=2;break;case SR_DOT2:c+=3;break;
            case SR_MIN:case SR_MAX:c+=1.5f;break;default:break;}}
    return c;
}
static inline int sr_eval(const SRWorld*w,int idx,int x,int y,int depth,int *valid){
    if(depth>SR_NODES||idx<0||idx>=SR_NODES||!w->nodes[idx].live){*valid=0;return 0;}
    SRNode n=w->nodes[idx];if(n.op==SR_ZERO)return 0;if(n.op==SR_ONE)return 1;
    if(n.op==SR_X)return x;
    if(n.op==SR_Y)return y;
    int a=sr_eval(w,n.a,x,y,depth+1,valid),b=0;
    if(n.op!=SR_SQUARE)b=sr_eval(w,n.b,x,y,depth+1,valid);
    switch(n.op){case SR_ADD:return a+b;case SR_SUB:return a-b;case SR_MUL:return a*b;
        case SR_SQUARE:return a*a;case SR_DOT2:return x*x+y*y;
        case SR_MIN:return a<b?a:b;case SR_MAX:return a>b?a:b;default:*valid=0;return 0;}
}
/* The reference is pinned, hidden from editable world state. All arithmetic is bounded.
 * Workloads may perturb the source but retain this independent specification. */
static inline int sr_reference(int mode,int x,int y){return mode==0?x*x+y*y:(x+y)*y;}
static inline int sr_verify_expr(const SRWorld*w){
    static const int8_t vals[]={-4,-3,-2,-1,0,1,2,3,4};
    for(int i=0;i<9;i++)for(int j=0;j<9;j++){
        int valid=1;int got=sr_eval(w,w->root,vals[i],vals[j],0,&valid);
        if(!valid||got!=sr_reference(w->mode,vals[i],vals[j]))return 0;}
    return 1;
}
static inline int sr_verify_repo(const SRWorld*w){
    return (w->imports&w->required_imports)==w->required_imports &&
        (w->registered&w->required_registration)==w->required_registration &&
        (w->tests&w->required_tests)==w->required_tests && w->duplicate_files==0;
}
static inline float sr_health(const SRWorld*w){
    int imports=__builtin_popcount((unsigned)(w->imports&w->required_imports));
    int required=__builtin_popcount((unsigned)w->required_imports);
    int registered=__builtin_popcount((unsigned)(w->registered&w->required_registration));
    int regreq=__builtin_popcount((unsigned)w->required_registration);
    int tests=__builtin_popcount((unsigned)(w->tests&w->required_tests));
    int testreq=__builtin_popcount((unsigned)w->required_tests);
    return 10.f*(float)(imports+registered+tests)/(float)(required+regreq+testreq+1)
         -1.f*w->duplicate_files;
}
static inline void sr_snapshot(SRWorld*w);
/* Graph initialization: first root is (add (mul x x) (mul y y)); alternate is
 * (mul (add x y) y).  Unreachable nodes become inactive after a rewrite. */
static inline void sr_reset(SRWorld*w,uint32_t seed){
    memset(w,0,sizeof(*w));w->rng=seed?seed:1;
    w->mode=(uint8_t)(sr_rand(w)&1);w->root=6;
    w->nodes[0]=(SRNode){SR_X,0,0,1};w->nodes[1]=(SRNode){SR_Y,0,0,1};
    if(!w->mode){w->nodes[2]=(SRNode){SR_MUL,0,0,1};
        w->nodes[3]=(SRNode){SR_MUL,1,1,1};
        w->nodes[6]=(SRNode){SR_ADD,2,3,1};}
    else{w->nodes[2]=(SRNode){SR_ADD,0,1,1};
        w->nodes[6]=(SRNode){SR_MUL,2,1,1};
        if(sr_rand(w)&1){w->nodes[4]=(SRNode){SR_ZERO,0,0,1};
            w->nodes[3]=(SRNode){SR_ADD,2,4,1};w->nodes[6].a=3;}}
    w->required_imports=(uint16_t)((1u<<(2+(sr_rand(w)%4)))-1u);
    w->required_registration=(uint16_t)((1u<<(1+(sr_rand(w)%3)))-1u);
    w->required_tests=(uint16_t)((1u<<(1+(sr_rand(w)%3)))-1u);
    w->imports=w->required_imports&~(1u<<(sr_rand(w)% __builtin_popcount((unsigned)w->required_imports)));
    w->registered=w->required_registration&~1u;
    w->tests=0;
    w->duplicate_files=1+(sr_rand(w)%3);
    w->prev_health=sr_health(w);
    sr_snapshot(w);
}
static inline void sr_snapshot(SRWorld*w){
    w->snapshot_valid=1;w->snapshot_root=w->root;
    memcpy(w->snapshot_nodes,w->nodes,sizeof(w->nodes));
    w->snapshot_imports=w->imports;w->snapshot_registered=w->registered;
    w->snapshot_tests=w->tests;w->snapshot_dups=w->duplicate_files;
}
/* Discrete macro actions have independently checked semantics.  A repair never
 * gets to modify reference expectations (required_*), verifier or evaluator. */
static inline float sr_step(SRWorld*w,int action){
    if(w->done)return 0;
    w->step++;
    float reward=-.015f, before=sr_cost(w);
    switch(action){
    case SR_SQUARE_MUL:
        if(!w->mode && w->nodes[2].op==SR_MUL){w->nodes[2].op=SR_SQUARE;
            if(!(w->credited_squares&1)){reward+=.20f;w->credited_squares|=1;}}
        else if(!w->mode && w->nodes[3].op==SR_MUL){w->nodes[3].op=SR_SQUARE;
            if(!(w->credited_squares&2)){reward+=.20f;w->credited_squares|=2;}}
        else reward-=.15f;
        break;
    case SR_FUSE_DOT:
        if(!w->mode && w->nodes[2].op==SR_SQUARE && w->nodes[3].op==SR_SQUARE){
            w->nodes[2].live=0;w->nodes[3].live=0;
            w->nodes[6]=(SRNode){SR_DOT2,0,1,1};
            if(!w->credited_fusion){reward+=.50f;w->credited_fusion=1;}
        }else reward-=.15f;
        break;
    case SR_ELIM_ZERO:
        if(w->mode && w->nodes[3].live && w->nodes[3].op==SR_ADD &&
           w->nodes[4].live && w->nodes[4].op==SR_ZERO){
            w->root=6;w->nodes[6].a=2;w->nodes[3].live=0;w->nodes[4].live=0;
            if(!w->credited_zero){reward+=.20f;w->credited_zero=1;}
        }else reward-=.06f;break;
    case SR_COMMUTE:
        if(w->mode){uint8_t a=w->nodes[2].a;w->nodes[2].a=w->nodes[2].b;w->nodes[2].b=a;reward+=.01f;}
        else reward-=.02f;
        break;
    case SR_REPLACE_ADD_SUB: /* Adversarial test: invalid rewrite, penalized. */
        {uint8_t previous=w->nodes[6].op;
        w->nodes[6].op=SR_SUB;
        if(!sr_verify_expr(w)){w->nodes[6].op=previous;reward-=1.f;}
        }
        break;
    case SR_REPAIR_IMPORT:
        {uint16_t missing=w->required_imports&~w->imports;
        if(missing){uint16_t bit=(uint16_t)(missing&-missing);w->imports|=bit;
            if(!(w->credited_imports&bit)){reward+=.15f;w->credited_imports|=bit;}}
        else reward-=.07f;}break;
    case SR_REGISTER_ENV:
        {uint16_t missing=w->required_registration&~w->registered;
        if(missing && (w->imports&w->required_imports)==w->required_imports){
            uint16_t bit=(uint16_t)(missing&-missing);w->registered|=bit;
            if(!(w->credited_registration&bit)){reward+=.18f;w->credited_registration|=bit;}}
        else reward-=.07f;}break;
    case SR_ADD_TEST:
        {uint16_t missing=w->required_tests&~w->tests;
        if(missing && (w->registered&w->required_registration)==w->required_registration){
            uint16_t bit=(uint16_t)(missing&-missing);w->tests|=bit;
            if(!(w->credited_tests&bit)){reward+=.18f;w->credited_tests|=bit;}}
        else reward-=.07f;}break;
    case SR_DEDUP_FILE:
        if(w->duplicate_files){w->duplicate_files--;
            if(w->credited_dups<3){w->credited_dups++;reward+=.12f;}}
        else reward-=.07f;
        break;
    case SR_RUN_TESTS:
        {int was_validated=w->validated;
        w->validated=(uint8_t)(sr_verify_expr(w)&&sr_verify_repo(w));
        reward+=w->validated?(was_validated?-.02f:.25f):-.08f;}break;
    case SR_COMMIT:
        if(w->validated && sr_verify_expr(w)&&sr_verify_repo(w)){
            w->committed=1;w->done=1;reward+=3.f+fmaxf(0.f,8.f-sr_cost(w))*.12f;
        }else reward-=.40f;break;
    case SR_ROLLBACK:
        if(w->snapshot_valid){w->root=w->snapshot_root;
            memcpy(w->nodes,w->snapshot_nodes,sizeof(w->nodes));
            w->imports=w->snapshot_imports;
            w->registered=w->snapshot_registered;w->tests=w->snapshot_tests;
            w->duplicate_files=w->snapshot_dups;w->validated=0;reward-=.02f;
        }else reward-=.08f;break;
    case SR_WAIT:break;
    case SR_STOP:w->done=1;reward-=.50f;break;
    default:reward-=.25f;break;
    }
    if(!sr_verify_expr(w)){reward-=2.f;w->done=1;}
    float health=sr_health(w);reward+=(health-w->prev_health)*.08f;
    w->prev_health=health;
    reward+=(before-sr_cost(w))*.035f;
    if(action!=SR_RUN_TESTS&&action!=SR_COMMIT&&action!=SR_WAIT)w->validated=0;
    if(w->step>=SR_MAX_STEPS)w->done=1;
    w->last_reward=reward;w->cumulative+=reward;
    return reward;
}
#endif
