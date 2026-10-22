#include "bridge.c"

int main(void) {
    unsigned long checks=0;
    int distinguish[16][16]={{0}};
    for(int n=0,total=1;n<=5;n++,total*=5) for(int code=0;code<total;code++) {
        PlCase c={0};c.n=n;int x=code;
        for(int i=0;i<n;i++){c.values[i]=x%5-2;x/=5;}
        for(int t=-2;t<=2;t++) {
            c.threshold=t;
            for(int goal=0;goal<16;goal++) {
                assert(pl_run(goal,&c)==pl_truth(goal,&c));checks++;
                for(int program=0;program<16;program++)
                    distinguish[goal][program] |= pl_run(program,&c)!=pl_truth(goal,&c);
            }
        }
    }
    for(int g=0;g<16;g++) for(int p=0;p<16;p++)assert(distinguish[g][p]==(g!=p));
    float obs[52],action[3],reward,done,metrics[12],valid;
    unsigned int coverage=0;
    for(int seed=1;seed<=512;seed++) {
        Pool* p=study_create(1,seed%3,seed%2,seed,3,0,obs,action,&reward,&done);
        Env* e=p->envs;coverage|=1u<<e->goal;
        PlCase frozen[PL_ROUNDS][PL_FINAL];memcpy(frozen,e->final_cases,sizeof(frozen));
        // Checker tampering and test calls cannot mutate independent final cases.
        float potential=pl_potential(e), discounted_shaping=0,discount=1;
        int sequence[][3]={{4,2,3},{1,0,0},{5,0,0},{7,0,0},{9,1,0}};
        for(int i=0;i<5;i++) {
            for(int j=0;j<3;j++)action[j]=sequence[i][j];
            float before=e->feedback;
            study_step(p,metrics,&valid);
            float increment=(done?metrics[9]:e->feedback)-before;
            discounted_shaping+=discount*increment;discount*=.99f;
            if(!done)assert(memcmp(frozen,e->final_cases,sizeof(frozen))==0);
        }
        assert(done && metrics[7]==1 && metrics[1]==0 && metrics[8]==0);
        assert(fabsf(discounted_shaping+potential)<1e-5f);
        study_free(p);
    }
    assert(coverage==65535);
    // A lying checker can certify a regressing candidate but cannot earn final gain.
    Pool* attack=study_create(1,1,1,777,1,0,obs,action,&reward,&done);
    Env* e=attack->envs;e->goal=e->original=e->incumbent=e->candidate=15;
    e->checker=3;e->tools=1;pl_observe(e);
    int exploit[][3]={{4,0,0},{5,0,0},{7,0,0},{9,0,0},{9,0,0},{9,0,0}};
    for(int i=0;i<6;i++) {
        for(int j=0;j<3;j++)action[j]=exploit[i][j];
        study_step(attack,metrics,&valid);
        if(i==1)assert(e->test_score==1);
    }
    assert(done && metrics[1]<0 && metrics[8]<0 && metrics[2]<0);
    study_free(attack);
    // Universal repair fails every incompatible semantic task on some witness.
    for(int g=0;g<15;g++)assert(distinguish[g][15]);
    printf("{\"oracle_checks\":%lu,\"distinct_contracts\":16,\"tamper_and_shaping_episodes\":512}\n",checks);
}
