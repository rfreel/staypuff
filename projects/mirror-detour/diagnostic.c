// CPU tabular Q-learning diagnostic. Not the PufferLib/PPO trainer.
#include <time.h>
#include "../../ocean/mirror_detour/mirror_detour.h"

#define MD_STATES (MD_HORIZON*3*MD_SIZE*MD_SIZE)

uint32_t next_random(uint32_t* rng) {
    *rng ^= *rng << 13;
    *rng ^= *rng >> 17;
    *rng ^= *rng << 5;
    return *rng;
}

int state_index(Env* env) {
    return ((env->ticks*3 + env->route + 1)*MD_SIZE + env->y)*MD_SIZE + env->x;
}

int choose(float* q, int state, uint32_t* rng, float epsilon) {
    if ((next_random(rng) >> 8)/16777216.0f < epsilon) {
        return next_random(rng) % 4;
    }
    int best = 0;
    int ties = 1;
    for (int a = 1; a < 4; a++) {
        if (q[4*state + a] > q[4*state + best]) {
            best = a;
            ties = 1;
        } else if (q[4*state + a] == q[4*state + best]) {
            ties++;
            if (next_random(rng) % ties == 0) {
                best = a;
            }
        }
    }
    return best;
}

Log evaluate(float* q, int radius, unsigned int seed) {
    float obs[OBS_SIZE];
    float action, reward, terminal;
    Env env = {0};
    env.agents[0] = (Agent){.observations = obs, .actions = &action,
        .rewards = &reward, .terminals = &terminal};
    env.half_width = 2;
    env.start_radius = radius;
    env.evaluate = 1;
    env.rng = seed;
    uint32_t rng = seed ^ 0x6a09e667u;
    puf_reset(&env);
    while (env.log.n < 64) {
        action = choose(q, state_index(&env), &rng, 0);
        puf_step(&env);
        assert(env.last_bonus == 0);
    }
    return env.log;
}

int main(int argc, char** argv) {
    assert(argc == 8 && "seed mode sign strength anneal_steps total_steps schedule");
    unsigned int seed = strtoul(argv[1], NULL, 10);
    int total_steps = atoi(argv[6]);
    assert(seed > 0 && total_steps > 0);
    float* q = calloc(MD_STATES*4, sizeof(float));
    assert(q);
    float obs[OBS_SIZE];
    float action, reward, terminal;
    Env env = {0};
    env.agents[0] = (Agent){.observations = obs, .actions = &action,
        .rewards = &reward, .terminals = &terminal};
    Ini ini = {0};
    puf_ini_load_env(&ini, "mirror_detour", 0, NULL);
    puf_ini_put(&ini, "env.mode", argv[2]);
    puf_ini_put(&ini, "env.sign", argv[3]);
    puf_ini_put(&ini, "env.strength", argv[4]);
    puf_ini_put(&ini, "env.anneal_steps", argv[5]);
    puf_ini_put(&ini, "env.schedule", argv[7]);
    puf_init(&env, puf_ini_section(&ini, "env", 0));
    puf_ini_free(&ini);
    env.rng = seed;
    puf_reset(&env);
    uint32_t rng = seed ^ 0xbb67ae85u;
    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    printf("{\"seed\":%u,\"mode\":%d,\"sign\":%d,\"strength\":%.9g,"
        "\"anneal_steps\":%llu,\"total_steps\":%d,\"schedule\":%d,\"curve\":[",
        seed, env.mode, env.sign, env.strength,
        (unsigned long long)env.anneal_steps, total_steps, env.schedule);
    int interval = total_steps/10;
    assert(interval > 0);
    int points = 0;
    for (int step = 0; step < total_steps; step++) {
        int state = state_index(&env);
        int a = choose(q, state, &rng, 0.2f);
        action = a;
        puf_step(&env);
        float target = reward;
        if (!terminal) {
            int next = state_index(&env);
            float best = q[4*next];
            for (int j = 1; j < 4; j++) {
                best = fmaxf(best, q[4*next + j]);
            }
            target += 0.99f*best;
        }
        q[4*state + a] += 0.3f*(target - q[4*state + a]);
        if ((step + 1) % interval == 0) {
            // Selection uses training-distribution starts only, not held-out starts.
            Log metric = evaluate(q, 1, seed + 10000);
            printf("%s{\"step\":%d,\"success\":%.6f,\"length\":%.6f}",
                points++ ? "," : "", step + 1, metric.score/metric.n,
                metric.length/metric.n);
        }
    }
    clock_gettime(CLOCK_MONOTONIC, &end);
    double seconds = end.tv_sec - start.tv_sec + (end.tv_nsec - start.tv_nsec)*1e-9;
    Log heldout = evaluate(q, 2, seed + 20000);
    printf("],\"seconds_including_curve_eval\":%.9f,\"training_episodes\":%.0f,"
        "\"heldout\":{\"episodes\":64,\"success\":%.6f,\"length\":%.6f,"
        "\"left\":%.6f,\"right\":%.6f}}\n", seconds, env.log.n,
        heldout.score/heldout.n, heldout.length/heldout.n,
        heldout.left/heldout.n, heldout.right/heldout.n);
    free(q);
}
