/* Fast native S-expression / repo work simulator REPL.
 * Only writes to in-memory SRWorld, never a filesystem or Git repository. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../../../ocean/sexpr_repo/sexpr_core.h"
static const char*names[SR_ACTIONS]={
    "square_mul","fuse_dot","elim_zero","commute","break_semantics",
    "repair_import","register_env","add_test","dedup_file","run_tests",
    "commit","rollback","wait","stop"
};
static void print_expr(const SRWorld*w,int idx,int depth){
    if(depth>16){printf("<depth>");return;}
    SRNode n=w->nodes[idx];
    switch(n.op){
    case SR_X:printf("x");return;case SR_Y:printf("y");return;
    case SR_ZERO:printf("0");return;case SR_ONE:printf("1");return;
    case SR_DOT2:printf("(dot2 x y)");return;
    default:break;
    }
    const char*name=n.op==SR_ADD?"+":n.op==SR_SUB?"-":n.op==SR_MUL?"*":
        n.op==SR_SQUARE?"square":n.op==SR_MIN?"min":"max";
    printf("(%s ",name);print_expr(w,n.a,depth+1);
    if(n.op!=SR_SQUARE){printf(" ");print_expr(w,n.b,depth+1);}
    printf(")");
}
static void status(const SRWorld*w){
    printf("\nprogram: ");print_expr(w,w->root,0);
    printf("\nreference: %s\n",w->mode==0?"(+ (* x x) (* y y))":"(* (+ x y) y)");
    printf("cost=%.2f nodes=%d verified=%s\n",sr_cost(w),sr_node_count(w),sr_verify_expr(w)?"yes":"NO");
    printf("repo: imports %d/%d, registrations %d/%d, tests %d/%d, duplicates %d\n",
        __builtin_popcount((unsigned)(w->imports&w->required_imports)),
        __builtin_popcount((unsigned)w->required_imports),
        __builtin_popcount((unsigned)(w->registered&w->required_registration)),
        __builtin_popcount((unsigned)w->required_registration),
        __builtin_popcount((unsigned)(w->tests&w->required_tests)),
        __builtin_popcount((unsigned)w->required_tests),w->duplicate_files);
    printf("step %d/%d reward %.3f total %.3f validated=%d committed=%d\n",
        w->step,SR_MAX_STEPS,w->last_reward,w->cumulative,w->validated,w->committed);
}
int main(int argc,char**argv){
    unsigned seed=argc>1?(unsigned)strtoul(argv[1],NULL,10):17;
    SRWorld w;sr_reset(&w,seed);
    puts("STAYPUFF S-EXPR REPL / synthetic graph only. Commands: show, reset [seed], help, action name, quit");
    status(&w);
    char line[128];
    while(fputs("sr> ",stdout)&&fflush(stdout)==0 && fgets(line,sizeof(line),stdin)){
        line[strcspn(line,"\r\n")]=0;
        if(strcmp(line,"quit")==0||strcmp(line,"exit")==0)break;
        if(strcmp(line,"help")==0){for(int i=0;i<SR_ACTIONS;i++)printf("%2d %s\n",i,names[i]);continue;}
        if(strcmp(line,"show")==0){status(&w);continue;}
        if(strncmp(line,"reset",5)==0){unsigned x=seed;
            if(sscanf(line+5,"%u",&x)==1)seed=x;
            sr_reset(&w,seed);status(&w);continue;}
        int act=-1;
        for(int i=0;i<SR_ACTIONS;i++)if(strcmp(line,names[i])==0){act=i;break;}
        if(act<0){char*end=NULL;long v=strtol(line,&end,10);
            if(end!=line&&*end==0&&v>=0&&v<SR_ACTIONS)act=(int)v;}
        if(act<0){puts("Unknown action; type help");continue;}
        if(w.done){puts("Episode ended. reset to continue.");continue;}
        sr_step(&w,act);status(&w);
        if(w.done)printf("EPISODE ENDED: %s\n",w.committed?"VERIFIED COMMIT":"UNRESOLVED");
    }
    return 0;
}
