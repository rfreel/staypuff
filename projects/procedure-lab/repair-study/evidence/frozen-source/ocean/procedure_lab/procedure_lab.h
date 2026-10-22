#include <assert.h>
typedef float obs_t;
#include "pufferenv.h"

#define OBS_SIZE 48
#define ACT_SIZES {10, 4, 5}
#define NUM_ATNS 3
#define PL_CASES 16
#define PL_FINAL 64
#define PL_ROUNDS 3

enum { PL_INSPECT, PL_REQUEST, PL_HYPOTHESIZE, PL_EXECUTE, PL_MODIFY,
    PL_TEST, PL_AUDIT, PL_RETAIN, PL_REVERT, PL_SUBMIT };

struct Log {
    float perf, score, cost, invalid, retained, rounds, n;
};

typedef struct {
    int n, threshold, values[8];
} PlCase;

struct Env {
    Log log;
    int num_agents;
    unsigned int rng;
    Agent agents[1];
    int tag, boundary_reached;
    int family_mode, evaluate, initial_budget, max_rounds;
    int family, round, remaining, original, incumbent, candidate;
    int strategy, candidate_strategy, checker, tools, offers, known_offers;
    int assumed, dependencies, materialized, version, tested, strategy_tested;
    int inspected, checker_known, audit_result, last_status, last_output;
    int last_expected, last_n, last_threshold, last_op, proposal, failures;
    float test_score, strategy_score, episode_return, episode_cost;
    float episode_accuracy, episode_invalid, episode_retained;
    unsigned int case_rng;
    PlCase final_cases[PL_ROUNDS][PL_FINAL];
};

unsigned int pl_random(unsigned int* rng) {
    *rng = *rng*1664525u + 1013904223u;
    return *rng;
}

// Reference and candidate deliberately use different control flow.
int pl_reference(PlCase* c) {
    int count = 0;
    for (int i = 0; i < c->n; i++) {
        count += c->values[i] >= c->threshold;
    }
    return count;
}

int pl_run(int program, PlCase* c) {
    int result = 0;
    int end = c->n - !(program & 8);
    for (int i = 0; i < end; i++) {
        int v = c->values[i];
        if (!(program & 2) && v < 0) {
            continue;
        }
        int repeated = 0;
        for (int j = 0; j < i; j++) {
            repeated |= c->values[j] == v;
        }
        if (!(program & 4) && repeated) {
            continue;
        }
        if ((program & 1) ? v >= c->threshold : v > c->threshold) {
            result++;
        }
    }
    return result;
}

int pl_judge(int checker, PlCase* c, int output) {
    if (checker == 3) {
        return 1;
    }
    if (checker == 1) {
        PlCase shifted = *c;
        shifted.threshold++;
        return output == pl_reference(&shifted);
    }
    if (checker == 2) {
        PlCase unique = *c;
        unique.n = 0;
        for (int i = 0; i < c->n; i++) {
            int seen = 0;
            for (int j = 0; j < unique.n; j++) {
                seen |= unique.values[j] == c->values[i];
            }
            if (!seen) {
                unique.values[unique.n++] = c->values[i];
            }
        }
        return output == pl_reference(&unique);
    }
    return output == pl_reference(c);
}

PlCase pl_case(unsigned int* rng, int kind, int evaluate, int narrow) {
    PlCase c = {0};
    int scale = evaluate ? 9 : 1;
    c.n = evaluate ? 5 + pl_random(rng)%4 : pl_random(rng)%9;
    c.threshold = ((int)(pl_random(rng)%7) - 3)*scale;
    for (int i = 0; i < c.n; i++) {
        c.values[i] = ((int)(pl_random(rng)%(evaluate ? 13 : 9))
            - (evaluate ? 6 : 4))*scale;
    }
    if (narrow) {
        c.n = 4;
        c.threshold = 0;
        for (int i = 0; i < 4; i++) {
            c.values[i] = i + 1;
        }
    } else if (kind == 1) {
        c.n = 4;
        c.values[0] = c.threshold;
        c.values[1] = c.threshold;
        c.values[2] = -scale;
        c.values[3] = c.threshold + scale;
    } else if (kind == 2) {
        c.n = 8;
        c.threshold = -2*scale;
        for (int i = 0; i < 8; i++) {
            c.values[i] = (i%3 - 2)*scale;
        }
    }
    return c;
}

int pl_propose(Env* env, int strategy) {
    if (strategy == 0) {
        return 0;
    }
    if (strategy == 1) {
        return env->round%4;
    }
    if (strategy == 2) {
        // Prior failing case categories direct future proposals, not hidden defects.
        for (int i = 0; i < 4; i++) {
            if (env->failures & (1 << i)) {
                return i;
            }
        }
        return (env->round + 1)%4;
    }
    return (env->round + 2)%4;
}

void pl_invalidate(Env* env) {
    env->version++;
    env->tested = -1;
    env->strategy_tested = -1;
    env->test_score = -1;
    env->strategy_score = -1;
    env->inspected &= ~1;
}

void pl_observe(Env* env) {
    float* o = env->agents[0].observations;
    memset(o, 0, OBS_SIZE*sizeof(float));
    o[0] = env->family/2.0f;
    o[1] = env->round/(float)env->max_rounds;
    o[2] = env->remaining/(float)env->initial_budget;
    o[3] = env->strategy/3.0f;
    o[4] = env->candidate_strategy/3.0f;
    o[5] = env->proposal/3.0f;
    o[6] = env->test_score;
    o[7] = env->strategy_score;
    o[8] = env->tested == env->version;
    o[9] = env->strategy_tested == env->version;
    o[10] = env->audit_result;
    o[11] = env->checker_known ? env->checker/3.0f : -1;
    o[12] = env->last_status;
    o[13] = env->last_output/8.0f;
    o[14] = env->last_expected/8.0f;
    o[15] = env->last_n/8.0f;
    o[16] = env->last_threshold/36.0f;
    o[17] = env->last_op/9.0f;
    for (int i = 0; i < 4; i++) {
        o[18+i] = !!(env->tools & (1 << i));
        o[22+i] = !!(env->assumed & (1 << i));
        o[26+i] = !!(env->dependencies & (1 << i));
        o[30+i] = env->inspected & 1 ? !!(env->candidate & (1 << i)) : -1;
        o[34+i] = env->inspected & 2 ? !!(env->incumbent & (1 << i)) : -1;
        o[38+i] = !!(env->failures & (1 << i));
        o[42+i] = env->known_offers & (1 << i) ? !!(env->offers & (1 << i)) : -1;
    }
    o[46] = !!(env->materialized & 2);
    o[47] = !!(env->materialized & 4);
}

void puf_init(Env* env, Dict* kwargs) {
    env->num_agents = 1;
    env->agents[0].policy = 0;
    env->agents[0].action_mask = NULL;
    env->family_mode = dict_get(kwargs, "family");
    env->evaluate = dict_get(kwargs, "evaluate");
    env->initial_budget = dict_get(kwargs, "budget");
    env->max_rounds = dict_get(kwargs, "rounds");
    assert(env->family_mode >= -1 && env->family_mode <= 2);
    assert(env->evaluate == 0 || env->evaluate == 1);
    assert(env->initial_budget >= 1 && env->initial_budget <= 1024);
    assert(env->max_rounds >= 1 && env->max_rounds <= PL_ROUNDS);
}

void puf_reset(Env* env) {
    env->family = env->family_mode < 0 ? pl_random(&env->rng)%3 : env->family_mode;
    env->round = 0;
    env->remaining = env->initial_budget;
    env->original = 1 + pl_random(&env->rng)%14;
    if (env->family == 2) {
        env->original = 8; // Narrow examples pass; negatives/duplicates/boundaries do not.
    }
    env->incumbent = env->candidate = env->original;
    env->strategy = env->candidate_strategy = 0;
    env->checker = env->family == 1 ? 3 : 0;
    env->tools = env->family == 0 ? 0 : 1;
    env->offers = 15;
    if (pl_random(&env->rng)%3 == 0) {
        env->offers &= ~4; // Optional transfer tool may be unobtainable this episode.
    }
    env->known_offers = env->tools;
    env->assumed = env->dependencies = env->materialized = 0;
    env->version = 0;
    env->inspected = env->checker_known = 0;
    env->audit_result = -1;
    env->last_status = env->last_output = env->last_expected = 0;
    env->last_n = env->last_threshold = env->last_op = 0;
    env->failures = env->proposal = 0;
    env->episode_return = env->episode_cost = env->episode_accuracy = 0;
    env->episode_invalid = env->episode_retained = 0;
    env->case_rng = pl_random(&env->rng) ^ (env->evaluate ? 0x9e3779b9u : 0);
    unsigned int final_rng = pl_random(&env->rng) ^ 0x85ebca6bu;
    for (int r = 0; r < env->max_rounds; r++) {
        for (int i = 0; i < PL_FINAL; i++) {
            env->final_cases[r][i] = pl_case(&final_rng, i%3, env->evaluate, 0);
        }
    }
    pl_invalidate(env);
    pl_observe(env);
}

float pl_score_round(Env* env) {
    int before = 0, after = 0, regressions = 0;
    for (int i = 0; i < PL_FINAL; i++) {
        PlCase* c = &env->final_cases[env->round][i];
        int truth = pl_reference(c);
        int was = pl_run(env->original, c) == truth;
        int now = pl_run(env->incumbent, c) == truth;
        before += was;
        after += now;
        regressions += was && !now;
    }
    env->episode_accuracy += after/(float)PL_FINAL;
    return (after - before - .5f*regressions)/(PL_FINAL*env->max_rounds);
}

void puf_step(Env* env) {
    float* a = env->agents[0].actions;
    assert(isfinite(a[0]) && a[0] >= 0 && a[0] < 10 && a[0] == floorf(a[0]));
    assert(isfinite(a[1]) && a[1] >= 0 && a[1] < 4 && a[1] == floorf(a[1]));
    assert(isfinite(a[2]) && a[2] >= 0 && a[2] < 5 && a[2] == floorf(a[2]));
    int op = a[0], target = a[1], param = a[2];
    int costs[10] = {1, 4, 1, 2, 2, 4, 4, 1, 1, 1};
    int affordable = costs[op] <= env->remaining;
    int cost = affordable ? costs[op] : env->remaining;
    env->remaining -= cost;
    env->episode_cost += cost;
    float reward = -.002f*cost;
    int valid = affordable, submit = 0, abandon = 0;
    env->last_status = 0;
    env->last_op = op;
    if (!affordable) {
        submit = 1;
    } else if (op == PL_INSPECT) {
        if (target < 2) {
            env->inspected |= 1 << target;
        } else if (target == 2) {
            valid = !!(env->tools & 8);
            if (valid) {
                env->checker_known = 1;
            }
        } else {
            env->known_offers = 15;
        }
    } else if (op == PL_REQUEST) {
        env->known_offers |= 1 << target;
        valid = !!(env->offers & (1 << target));
        if (valid) {
            env->tools |= 1 << target;
        }
    } else if (op == PL_HYPOTHESIZE) {
        valid = param <= 1;
        if (valid && param == 1) {
            env->assumed |= 1 << target;
            // Assumptions are exposed separately from measured test scores.
        }
    } else if (op == PL_EXECUTE) {
        valid = !!(env->tools & (1 << target));
        if (valid) {
            env->dependencies &= ~(1 << target);
            env->assumed &= ~(1 << target);
            if (target == 0) {
                PlCase c = pl_case(&env->case_rng, 0, env->evaluate, env->family == 2);
                env->last_output = pl_run(env->candidate, &c);
                env->last_expected = -1; // Execution alone does not certify correctness.
                env->last_n = c.n;
                env->last_threshold = c.threshold;
            } else if (target == 3) {
                env->checker_known = 1;
            } else {
                env->materialized |= 1 << target;
            }
        }
    } else if (op == PL_MODIFY) {
        valid = target < 3 && (param < 4 || target == 0);
        if (valid) {
            if (target == 0) {
                env->candidate ^= 1 << (param == 4 ? env->proposal : param);
            } else if (target == 1) {
                env->candidate_strategy = param;
            } else {
                env->checker = param;
                env->checker_known = 1;
                env->audit_result = -1;
            }
            env->dependencies |= env->assumed;
            pl_invalidate(env);
        }
    } else if (op == PL_TEST) {
        valid = target < 3 && param < 3 && (env->tools & 1)
            && (param == 0 || ((env->tools & (1 << param))
                && (env->materialized & (1 << param))));
        if (valid) {
            int program = target == 1 ? env->incumbent : env->candidate;
            if (target == 2) {
                program = env->candidate ^ (1 << pl_propose(env, env->candidate_strategy));
            }
            int passes = 0;
            env->failures = 0;
            for (int i = 0; i < PL_CASES; i++) {
                PlCase c = pl_case(&env->case_rng, param, env->evaluate,
                    param == 0 && env->family == 2);
                int output = pl_run(program, &c);
                int pass = pl_judge(env->checker, &c, output);
                passes += pass;
                if (!pass) {
                    for (int j = 0; j < c.n; j++) {
                        env->failures |= (c.values[j] == c.threshold) ? 1 : 0;
                        env->failures |= c.values[j] < 0 ? 2 : 0;
                        for (int k = 0; k < j; k++) {
                            env->failures |= c.values[j] == c.values[k] ? 4 : 0;
                        }
                    }
                    env->failures |= c.n ? 8 : 0;
                }
                env->last_output = output;
                env->last_expected = env->checker == 3 ? -1 :
                    (env->checker == 0 ? pl_reference(&c) : -1);
                env->last_n = c.n;
                env->last_threshold = c.threshold;
            }
            if (target != 1) {
                env->dependencies &= ~(1 | (param ? 1 << param : 0));
                env->assumed &= ~(1 | (param ? 1 << param : 0));
            }
            if (target == 2) {
                env->strategy_score = passes/(float)PL_CASES;
                env->strategy_tested = env->version;
            } else {
                env->test_score = passes/(float)PL_CASES;
                env->tested = target == 0 ? env->version : -1;
            }
        }
    } else if (op == PL_AUDIT) {
        valid = !!(env->tools & 8);
        if (valid) {
            PlCase c = {3, -1, {-1, -1, 2}};
            env->audit_result = 1;
            for (int output = 0; output <= 8; output++) {
                if (pl_judge(env->checker, &c, output) != (output == pl_reference(&c))) {
                    env->audit_result = 0;
                }
            }
            env->checker_known = 1;
            env->dependencies &= ~8;
            env->assumed &= ~8;
        }
    } else if (op == PL_RETAIN) {
        valid = target < 3 && !env->dependencies
            && (target == 1 || env->tested == env->version)
            && (target == 0 || env->strategy_tested == env->version);
        if (valid) {
            if (target != 1) {
                env->incumbent = env->candidate;
            }
            if (target != 0) {
                env->strategy = env->candidate_strategy;
            }
            env->episode_retained++;
            env->inspected &= ~2;
            pl_invalidate(env);
        }
    } else if (op == PL_REVERT) {
        env->candidate = env->incumbent;
        env->candidate_strategy = env->strategy;
        env->dependencies = 0;
        pl_invalidate(env);
    } else if (op == PL_SUBMIT) {
        valid = target < 2;
        submit = valid;
        abandon = target == 1;
    }
    if (!valid) {
        reward -= .02f;
        env->episode_invalid++;
    }
    env->last_status = valid ? 1 : -1;
    int terminal = abandon || env->remaining == 0;
    if ((submit || terminal) && !abandon) {
        reward += pl_score_round(env);
        env->round++;
        terminal |= env->round == env->max_rounds;
        if (!terminal) {
            env->candidate = env->incumbent;
            env->candidate_strategy = env->strategy;
            env->dependencies = 0;
            env->proposal = pl_propose(env, env->strategy);
            pl_invalidate(env);
        }
    }
    env->episode_return += reward;
    env->agents[0].rewards[0] = reward;
    env->agents[0].terminals[0] = terminal;
    env->boundary_reached = terminal;
    if (terminal) {
        env->log.perf += env->round ? env->episode_accuracy/env->round : 0;
        env->log.score += env->episode_return;
        env->log.cost += env->episode_cost;
        env->log.invalid += env->episode_invalid;
        env->log.retained += env->episode_retained;
        env->log.rounds += env->round;
        env->log.n++;
        puf_reset(env);
    } else {
        pl_observe(env);
    }
}

void puf_log(Log* log, Dict* out) {
    dict_set(out, "perf", log->perf);
    dict_set(out, "score", log->score);
    dict_set(out, "cost", log->cost);
    dict_set(out, "invalid", log->invalid);
    dict_set(out, "retained", log->retained);
    dict_set(out, "rounds", log->rounds);
    dict_set(out, "n", log->n);
}

void puf_render(Env* env) {
    if (!IsWindowReady()) {
        InitWindow(960, 400, "Procedure Lab");
        SetTargetFPS(30);
    }
    BeginDrawing();
    ClearBackground(RAYWHITE);
    DrawText(TextFormat("family %d   round %d/%d   budget %d", env->family,
        env->round + 1, env->max_rounds, env->remaining), 24, 24, 26, BLACK);
    DrawText(TextFormat("retained strategy %d   proposed edit %d", env->strategy,
        env->proposal), 24, 72, 22, DARKGRAY);
    DrawText(TextFormat("tools %x   assumptions %x   dependencies %x", env->tools,
        env->assumed, env->dependencies), 24, 120, 22, DARKGRAY);
    DrawText(TextFormat("test %.2f   strategy test %.2f   audit %d", env->test_score,
        env->strategy_score, env->audit_result), 24, 168, 22, DARKGRAY);
    DrawText("Inspect / acquire / hypothesize / execute / modify / test", 24, 240, 20, BLACK);
    DrawText("Audit / retain / revert / submit", 24, 276, 20, BLACK);
    DrawText("Hypotheses do not certify artifacts.", 24, 330, 22, MAROON);
    EndDrawing();
    puf_web_vsync();
}

void puf_close(Env* env) {
    if (IsWindowReady()) {
        CloseWindow();
    }
}
