#include <stdio.h>
#include <stdlib.h>
#include "../../../ocean/sexpr_repo/sexpr_core.h"
#define CHECK(x) do {if(!(x)){fprintf(stderr,"FAIL %s at %d\n",#x,__LINE__);return 1;}}while(0)
int main(void){
    for(unsigned seed=1;seed<=500;seed++){
        SRWorld w;sr_reset(&w,seed);CHECK(sr_verify_expr(&w));CHECK(!sr_verify_repo(&w));
        float initial=sr_cost(&w);
        if(w.mode==0){sr_step(&w,SR_SQUARE_MUL);sr_step(&w,SR_SQUARE_MUL);sr_step(&w,SR_FUSE_DOT);
            CHECK(sr_verify_expr(&w));CHECK(sr_cost(&w)<initial);}
        float prev=w.cumulative;sr_step(&w,SR_REPLACE_ADD_SUB);
        CHECK(sr_verify_expr(&w));CHECK(w.cumulative<prev);
        for(int i=0;i<5 && (w.imports&w.required_imports)!=w.required_imports;i++)sr_step(&w,SR_REPAIR_IMPORT);
        for(int i=0;i<3 && (w.registered&w.required_registration)!=w.required_registration;i++)sr_step(&w,SR_REGISTER_ENV);
        for(int i=0;i<3 && (w.tests&w.required_tests)!=w.required_tests;i++)sr_step(&w,SR_ADD_TEST);
        for(int i=0;i<4 && w.duplicate_files;i++)sr_step(&w,SR_DEDUP_FILE);
        CHECK(sr_verify_repo(&w));
        sr_step(&w,SR_RUN_TESTS); CHECK(w.validated);
        sr_step(&w,SR_COMMIT);CHECK(w.committed && w.done);
    }
    puts("sexpr core: 500 seeds, type-safe rewrites, verifier, repairs and commit PASS");return 0;
}
