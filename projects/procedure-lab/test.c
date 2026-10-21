#include "../../ocean/procedure_lab/procedure_lab.h"

void setup(Env* env, float* buffers, int family, int evaluate, unsigned int seed) {
    memset(env, 0, sizeof(*env));
    memset(buffers, 0, (OBS_SIZE + 5)*sizeof(float));
    env->agents[0].observations = buffers;
    env->agents[0].actions = buffers + OBS_SIZE;
    env->agents[0].rewards = buffers + OBS_SIZE + 3;
    env->agents[0].terminals = buffers + OBS_SIZE + 4;
    Ini ini = {0};
    puf_ini_load_env(&ini, "procedure_lab", 0, NULL);
    puf_init(env, puf_ini_section(&ini, "env", 0));
    puf_ini_free(&ini);
    env->family_mode = family;
    env->evaluate = evaluate;
    env->rng = seed;
    puf_reset(env);
}

void step(Env* env, int op, int target, int param) {
    env->agents[0].actions[0] = op;
    env->agents[0].actions[1] = target;
    env->agents[0].actions[2] = param;
    puf_step(env);
    for (int i = 0; i < OBS_SIZE; i++) {
        assert(isfinite(env->agents[0].observations[i]));
    }
    assert(isfinite(env->agents[0].rewards[0]));
}

unsigned long exhaustive(void) {
    unsigned long checked = 0;
    int failures[16] = {0};
    for (int n = 0, combinations = 1; n <= 5; n++, combinations *= 5) {
        for (int code = 0; code < combinations; code++) {
            PlCase c = {0};
            c.n = n;
            int digits = code, histogram[5] = {0};
            for (int i = 0; i < n; i++) {
                c.values[i] = digits%5 - 2;
                histogram[digits%5]++;
                digits /= 5;
            }
            for (int t = -2; t <= 2; t++) {
                c.threshold = t;
                int truth = n;
                for (int v = -2; v < t; v++) {
                    truth -= histogram[v + 2];
                }
                assert(pl_reference(&c) == truth);
                for (int program = 0; program < 16; program++) {
                    int output = pl_run(program, &c);
                    assert(output >= 0 && output <= n);
                    failures[program] += output != truth;
                    assert(pl_judge(0, &c, output) == (output == truth));
                    checked++;
                }
                for (int output = 0; output <= 8; output++) {
                    assert(pl_judge(0, &c, output) == (output == truth));
                }
            }
        }
    }
    assert(failures[15] == 0);
    for (int i = 0; i < 15; i++) {
        assert(failures[i] > 0);
    }
    return checked;
}

void transitions(void) {
    Env a, b;
    float ab[OBS_SIZE + 5], bb[OBS_SIZE + 5];
    setup(&a, ab, 0, 0, 19);
    step(&a, PL_HYPOTHESIZE, 0, 1);
    assert(a.tools == 0 && a.assumed == 1 && a.tested == -1 && a.test_score == -1);
    step(&a, PL_MODIFY, 0, 0);
    assert(a.dependencies == 1);
    int original = a.incumbent;
    step(&a, PL_RETAIN, 0, 0);
    assert(a.last_status == -1 && a.incumbent == original);
    step(&a, PL_REQUEST, 0, 0);
    assert(a.tools == 1 && a.dependencies == 1);
    step(&a, PL_TEST, 1, 0);
    assert(a.tested == -1 && a.dependencies == 1);
    step(&a, PL_EXECUTE, 0, 0);
    assert(a.dependencies == 0 && a.assumed == 0 && a.tested == -1);
    step(&a, PL_TEST, 0, 0);
    assert(a.tested == a.version && a.agents[0].rewards[0] < 0);
    step(&a, PL_HYPOTHESIZE, 0, 1);
    step(&a, PL_MODIFY, 0, 1);
    assert(a.dependencies == 1 && a.tested == -1); // Available still != executed.
    step(&a, PL_RETAIN, 0, 0);
    assert(a.last_status == -1);
    step(&a, PL_TEST, 0, 0);
    step(&a, PL_RETAIN, 0, 0);
    assert(a.last_status == 1 && a.incumbent == a.candidate);
    step(&a, PL_MODIFY, 0, 0);
    step(&a, PL_REVERT, 0, 0);
    assert(a.candidate == a.incumbent && a.tested == -1 && !a.dependencies);

    setup(&a, ab, 1, 0, 19);
    step(&a, PL_TEST, 0, 0);
    assert(a.test_score == 1);
    step(&a, PL_REQUEST, 3, 0);
    step(&a, PL_AUDIT, 0, 0);
    assert(a.audit_result == 0);
    step(&a, PL_MODIFY, 2, 0);
    assert(a.tested == -1);
    step(&a, PL_AUDIT, 0, 0);
    assert(a.audit_result == 1);
    for (int checker = 1; checker < 4; checker++) {
        step(&a, PL_MODIFY, 2, checker);
        step(&a, PL_AUDIT, 0, 0);
        assert(a.audit_result == 0);
    }

    setup(&a, ab, 1, 0, 19);
    setup(&b, bb, 1, 0, 19);
    a.incumbent = b.incumbent = 15;
    a.checker = 0;
    b.checker = 3;
    float expected = 0;
    for (int i = 0; i < PL_FINAL; i++) {
        PlCase* c = &a.final_cases[0][i];
        expected += pl_run(a.original, c) != pl_reference(c);
    }
    expected /= PL_FINAL*a.max_rounds;
    assert(fabsf(pl_score_round(&a) - expected) < 1e-6f);
    a.episode_accuracy = 0;
    step(&a, PL_SUBMIT, 0, 0);
    step(&b, PL_SUBMIT, 0, 0);
    assert(ab[OBS_SIZE + 3] == bb[OBS_SIZE + 3]);
    assert(fabsf(ab[OBS_SIZE + 3] - (expected - .002f)) < 1e-6f);

    // Hidden cases, checker, offers and candidate do not leak before inspection.
    setup(&a, ab, 1, 0, 19);
    memcpy(bb, ab, sizeof(ab));
    a.checker = 1;
    a.offers ^= 4;
    a.candidate ^= 7;
    a.final_cases[0][0].values[0] = 999;
    pl_observe(&a);
    assert(memcmp(ab, bb, OBS_SIZE*sizeof(float)) == 0);

    setup(&a, ab, 2, 0, 19);
    step(&a, PL_TEST, 0, 0);
    assert(a.test_score == 1);
    step(&a, PL_REQUEST, 1, 0);
    step(&a, PL_EXECUTE, 1, 0);
    step(&a, PL_TEST, 0, 1);
    assert(a.test_score < 1);
    step(&a, PL_MODIFY, 1, 3);
    step(&a, PL_RETAIN, 1, 0);
    assert(a.last_status == -1);
    step(&a, PL_TEST, 2, 1);
    step(&a, PL_RETAIN, 1, 0);
    assert(a.strategy == 3);
    step(&a, PL_SUBMIT, 0, 0);
    assert(a.round == 1 && a.proposal == 3);
    original = a.candidate;
    step(&a, PL_MODIFY, 0, 4);
    assert(a.candidate == (original ^ 8));

    setup(&a, ab, 0, 0, 19);
    a.remaining = 1;
    step(&a, PL_REQUEST, 0, 0);
    assert(ab[OBS_SIZE + 4] == 1 && a.log.n == 1 && a.round == 0);
    assert(fabsf(ab[OBS_SIZE + 3] + .022f) < 1e-6f);
    assert(a.log.rounds == 1 && a.log.cost == 1);
    step(&a, PL_SUBMIT, 1, 0);
    assert(ab[OBS_SIZE + 4] == 1 && a.log.n == 2 && a.log.rounds == 1);

    // Same action budget cannot buy access to the separate final-case RNG.
    setup(&a, ab, 2, 0, 19);
    setup(&b, bb, 2, 0, 19);
    step(&a, PL_TEST, 0, 0);
    for (int i = 0; i < 4; i++) {
        step(&b, PL_INSPECT, 0, 0);
    }
    assert(memcmp(a.final_cases, b.final_cases, sizeof(a.final_cases)) == 0);
}

// Separate action RNG: don't accidentally couple policy choices to world randomness.
unsigned int action_random(unsigned int* rng) {
    *rng ^= *rng << 13;
    *rng ^= *rng >> 17;
    *rng ^= *rng << 5;
    return *rng;
}

void replay(void) {
    Env a, b;
    float ab[OBS_SIZE + 5], bb[OBS_SIZE + 5];
    unsigned int rng = 73;
    for (int family = -1; family < 3; family++) {
        for (int evaluate = 0; evaluate < 2; evaluate++) {
            setup(&a, ab, family, evaluate, 71);
            setup(&b, bb, family, evaluate, 71);
            for (int i = 0; i < 10000; i++) {
                int op = action_random(&rng)%10;
                int target = action_random(&rng)%4;
                int param = action_random(&rng)%5;
                step(&a, op, target, param);
                step(&b, op, target, param);
                assert(memcmp(ab, bb, sizeof(ab)) == 0);
                assert(memcmp(&a.log, &b.log, sizeof(Log)) == 0);
                assert(a.remaining > 0 && a.remaining <= a.initial_budget);
            }
        }
    }
}

void batched(void) {
    const int count = 128;
    Env* envs = (Env*)calloc(count, sizeof(Env));
    float* arena = (float*)calloc(count*(OBS_SIZE + 7), sizeof(float));
    assert(envs && arena);
    unsigned int rng = 123;
    for (int i = 0; i < count; i++) {
        float* b = arena + i*(OBS_SIZE + 7);
        b[0] = b[OBS_SIZE + 6] = 9876;
        setup(&envs[i], b + 1, i%3, i%2, i + 1);
    }
    for (int t = 0; t < 1000; t++) {
        for (int i = 0; i < count; i++) {
            int op = action_random(&rng)%10;
            int target = action_random(&rng)%4;
            int param = action_random(&rng)%5;
            step(&envs[i], op, target, param);
            float* b = arena + i*(OBS_SIZE + 7);
            assert(b[0] == 9876 && b[OBS_SIZE + 6] == 9876);
        }
    }
    free(arena);
    free(envs);
}

void scripted(Env* env) {
    // Decisions read observations only, never hidden program or evaluator fields.
    float* o = env->agents[0].observations;
    step(env, PL_INSPECT, 0, 0);
    int fixes[4];
    for (int i = 0; i < 4; i++) {
        fixes[i] = o[30+i] == 0;
    }
    if (!o[18]) {
        step(env, PL_REQUEST, 0, 0);
    }
    if (o[0] == .5f) {
        step(env, PL_REQUEST, 3, 0);
        step(env, PL_AUDIT, 0, 0);
        if (o[10] == 0) {
            step(env, PL_MODIFY, 2, 0);
            step(env, PL_AUDIT, 0, 0);
        }
    }
    for (int i = 0; i < 4; i++) {
        if (fixes[i]) {
            step(env, PL_MODIFY, 0, i);
        }
    }
    step(env, PL_TEST, 0, 0);
    step(env, PL_RETAIN, 0, 0);
    do {
        step(env, PL_SUBMIT, 0, 0);
    } while (!env->agents[0].terminals[0]);
}

int main(void) {
    unsigned long checked = exhaustive();
    transitions();
    replay();
    batched();
    printf("{\"program_case_checks\":%lu,\"replay_steps\":80000,"
        "\"batched_steps\":128000,\"benchmarks\":[", checked);
    for (int family = 0; family < 3; family++) {
        for (int evaluate = 0; evaluate < 2; evaluate++) {
            for (int policy = 0; policy < 2; policy++) {
                Env env;
                float buffers[OBS_SIZE + 5];
                setup(&env, buffers, family, evaluate, 101);
                unsigned int rng = 303;
                while (env.log.n < 1000) {
                    if (policy) {
                        scripted(&env);
                    } else {
                        int op = action_random(&rng)%10;
                        int target = action_random(&rng)%4;
                        int param = action_random(&rng)%5;
                        step(&env, op, target, param);
                    }
                }
                if (policy) {
                    assert(env.log.perf == 1000 && env.log.invalid == 0);
                    assert(env.log.rounds == 3000);
                }
                printf("%s{\"family\":%d,\"evaluate\":%d,\"policy\":\"%s\","
                    "\"episodes\":1000,\"accuracy\":%.6f,\"return\":%.6f,"
                    "\"cost\":%.3f,\"rounds\":%.3f}",
                    family || evaluate || policy ? "," : "", family, evaluate,
                    policy ? "scripted" : "random", env.log.perf/1000,
                    env.log.score/1000, env.log.cost/1000, env.log.rounds/1000);
            }
        }
    }
    puts("]}");
    return 0;
}
