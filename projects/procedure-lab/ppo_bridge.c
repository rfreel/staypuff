#include "../../ocean/procedure_lab/procedure_lab.h"

#define API __attribute__((visibility("default")))
typedef struct { Env* envs; int count; } Pool;

API Pool* lab_create(int count, int family, int evaluate, unsigned int seed,
        float* observations, float* actions, float* rewards, float* terminals) {
    assert(count > 0 && count <= 4096);
    Pool* pool = (Pool*)calloc(1, sizeof(Pool));
    assert(pool);
    pool->envs = (Env*)calloc(count, sizeof(Env));
    assert(pool->envs);
    pool->count = count;
    Ini ini = {0};
    puf_ini_load_env(&ini, "procedure_lab", 0, NULL);
    Dict* kwargs = puf_ini_section(&ini, "env", 0);
    for (int i = 0; i < count; i++) {
        Env* env = &pool->envs[i];
        env->agents[0].observations = observations + i*OBS_SIZE;
        env->agents[0].actions = actions + i*NUM_ATNS;
        env->agents[0].rewards = rewards + i;
        env->agents[0].terminals = terminals + i;
        env->rng = seed + 104729u*i;
        puf_init(env, kwargs);
        env->family_mode = family;
        env->evaluate = evaluate;
        puf_reset(env);
    }
    puf_ini_free(&ini);
    return pool;
}

API void lab_step(Pool* pool, float* metrics) {
    memset(metrics, 0, pool->count*6*sizeof(float));
    for (int i = 0; i < pool->count; i++) {
        Env* env = &pool->envs[i];
        puf_step(env);
        if (env->agents[0].terminals[0]) {
            float* m = metrics + 6*i;
            m[0] = env->log.perf;
            m[1] = env->log.score;
            m[2] = env->log.cost;
            m[3] = env->log.invalid;
            m[4] = env->log.retained;
            m[5] = env->log.rounds;
            memset(&env->log, 0, sizeof(Log));
        }
    }
}

API void lab_free(Pool* pool) {
    free(pool->envs);
    free(pool);
}
