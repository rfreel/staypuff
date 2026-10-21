#include <assert.h>
#include <stdint.h>
typedef float obs_t;
#include "pufferenv.h"

#define OBS_SIZE 6
#define ACT_SIZES {4}
#define NUM_ATNS 1
#define MD_SIZE 11
#define MD_HORIZON 80

struct Log {
    float perf, score, length, left, right, bonus, n;
};

struct Env {
    Log log;
    int num_agents;
    unsigned int rng;
    Agent agents[1];
    int tag, boundary_reached;
    int x, y, ticks, route, half_width, start_radius;
    int mode, sign, evaluate, schedule;
    uint64_t steps, anneal_steps;
    float strength, gamma, episode_bonus, base_reward, last_bonus;
};

// Actions: left, right, up, down. State mirror is x -> 10-x, route -> -route.
int md_mirror_action(int action) {
    assert(action >= 0 && action < 4);
    return action < 2 ? 1 - action : action;
}

int md_blocked(int x, int y, int half_width) {
    return x < 0 || x >= MD_SIZE || y < 0 || y >= MD_SIZE
        || (abs(x - 5) <= half_width && y >= 3 && y <= 7);
}

void md_observe(Env* env) {
    float* obs = env->agents[0].observations;
    obs[0] = (env->x - 5)/5.0f;
    obs[1] = env->y/10.0f;
    obs[2] = env->ticks/(float)MD_HORIZON;
    obs[3] = env->route;
    obs[4] = env->half_width/3.0f;
    obs[5] = env->start_radius/3.0f;
}

void puf_init(Env* env, Dict* kwargs) {
    env->num_agents = 1;
    env->agents[0].policy = 0;
    env->agents[0].action_mask = NULL;
    env->mode = dict_get(kwargs, "mode");
    env->sign = dict_get(kwargs, "sign");
    env->strength = dict_get(kwargs, "strength");
    env->gamma = dict_get(kwargs, "shaping_gamma");
    env->evaluate = dict_get(kwargs, "evaluate");
    env->schedule = dict_get(kwargs, "schedule");
    env->half_width = dict_get(kwargs, "half_width");
    env->start_radius = dict_get(kwargs, "start_radius");
    double anneal = dict_get(kwargs, "anneal_steps");
    double offset = dict_get(kwargs, "step_offset");
    assert(anneal >= 0 && anneal <= 1e12 && anneal == floor(anneal));
    assert(offset >= 0 && offset <= 1e12 && offset == floor(offset));
    env->anneal_steps = anneal;
    env->steps = offset;
    assert(env->mode >= 0 && env->mode <= 4);
    assert(env->sign >= -1 && env->sign <= 1);
    assert(isfinite(env->strength) && env->strength >= 0);
    assert(env->gamma >= 0 && env->gamma <= 1);
    assert(env->half_width >= 1 && env->half_width <= 3);
    assert(env->start_radius >= 0 && env->start_radius <= 3);
    assert(env->evaluate == 0 || env->evaluate == 1);
    assert(env->schedule == 0 || env->schedule == 1);
}

void puf_reset(Env* env) {
    // Exactly balanced paired starts. Preserve phase across episode resets.
    env->rng = env->rng*1664525u + 1013904223u;
    env->x = 5 + ((env->rng & 1u) ? env->start_radius : -env->start_radius);
    env->y = 10;
    env->ticks = 0;
    env->route = 0;
    env->episode_bonus = 0;
    md_observe(env);
}

void puf_step(Env* env) {
    int action = env->agents[0].actions[0];
    assert(action >= 0 && action < 4);
    int dx[4] = {-1, 1, 0, 0};
    int dy[4] = {0, 0, -1, 1};
    int old_x = env->x;
    int old_y = env->y;
    int nx = old_x + dx[action];
    int ny = old_y + dy[action];
    if (!md_blocked(nx, ny, env->half_width)) {
        env->x = nx;
        env->y = ny;
    }
    env->ticks++;
    int success = env->x == 5 && env->y == 0;
    int terminal = success || env->ticks == MD_HORIZON;
    float feature = 0;
    if (env->route == 0 && env->y < 3) {
        env->route = env->x < 5 ? -1 : 1;
        feature = env->route;
    }
    env->base_reward = success;
    env->last_bonus = 0;
    if (!env->evaluate && env->mode && env->sign && env->strength
        && (env->schedule || env->steps < env->anneal_steps)) {
        float weight = env->strength;
        if (!env->schedule) {
            weight *= 1.0 - (double)env->steps/env->anneal_steps;
        }
        if (env->mode == 2 && feature != 0) {
            // Fixed hash control, no RNG consumption; matched event and amplitude.
            uint32_t key = (old_x + MD_SIZE*old_y)*4u + action;
            key = (key ^ 0x9e3779b9u)*0x85ebca6bu;
            key ^= key >> 16;
            feature = (key & 1u) ? 1 : -1;
        } else if (env->mode == 4) {
            feature = fabsf(feature);
        } else if (env->mode == 3) {
            float before = -(abs(old_x - 5) + old_y)/20.0f;
            float after = terminal ? 0 : -(abs(env->x - 5) + env->y)/20.0f;
            feature = env->gamma*after - before;
        }
        env->last_bonus = weight*env->sign*feature;
    }
    env->agents[0].rewards[0] = env->base_reward + env->last_bonus;
    env->agents[0].terminals[0] = terminal;
    env->episode_bonus += env->last_bonus;
    env->steps++;
    if (terminal) {
        env->log.perf += success;
        env->log.score += success;
        env->log.length += env->ticks;
        env->log.left += env->route == -1;
        env->log.right += env->route == 1;
        env->log.bonus += env->episode_bonus;
        env->log.n++;
        env->boundary_reached = 1;
        puf_reset(env);
    } else {
        env->boundary_reached = 0;
        md_observe(env);
    }
}

void puf_log(Log* log, Dict* out) {
    dict_set(out, "perf", log->perf);
    dict_set(out, "score", log->score);
    dict_set(out, "length", log->length);
    dict_set(out, "left", log->left);
    dict_set(out, "right", log->right);
    dict_set(out, "bonus", log->bonus);
    dict_set(out, "n", log->n);
}

void puf_render(Env* env) {
    if (!IsWindowReady()) {
        InitWindow(550, 610, "Mirror detour");
        SetTargetFPS(30);
    }
    BeginDrawing();
    ClearBackground(RAYWHITE);
    for (int y = 0; y < MD_SIZE; y++) {
        for (int x = 0; x < MD_SIZE; x++) {
            if (md_blocked(x, y, env->half_width)) {
                DrawRectangle(x*50, y*50, 49, 49, DARKGRAY);
            }
        }
    }
    DrawRectangle(250, 0, 49, 49, GREEN);
    DrawCircle(env->x*50 + 25, env->y*50 + 25, 16, BLUE);
    DrawText(TextFormat("step %llu  base %.0f  bonus %.3f",
        (unsigned long long)env->steps, env->base_reward, env->last_bonus), 10, 565, 18, BLACK);
    EndDrawing();
    puf_web_vsync();
}

void puf_close(Env* env) {
    if (IsWindowReady()) {
        CloseWindow();
    }
}
