// Adapter only. All expected answers are supplied by the separate Python oracle.
#include "mirror_detour.h"

int main(void) {
    int width, x, y, ticks, route, action, mode, sign, step, evaluate, schedule;
    while (scanf("%d %d %d %d %d %d %d %d %d %d %d", &width, &x, &y, &ticks,
        &route, &action, &mode, &sign, &step, &evaluate, &schedule) == 11) {
        float obs[OBS_SIZE];
        float act = action;
        float reward = 99;
        float terminal = 99;
        Env env = {0};
        env.agents[0] = (Agent){.observations = obs, .actions = &act,
            .rewards = &reward, .terminals = &terminal};
        env.rng = 100;
        env.x = x;
        env.y = y;
        env.ticks = ticks;
        env.route = route;
        env.half_width = width;
        env.start_radius = 1;
        env.mode = mode;
        env.sign = sign;
        env.steps = step;
        env.evaluate = evaluate;
        env.schedule = schedule;
        env.anneal_steps = 100;
        env.strength = 0.2f;
        env.gamma = 0.99f;
        puf_step(&env);
        printf("%d %d %d %d %llu %.9g %.9g %.9g %.9g %.9g %.9g\n",
            env.x, env.y, env.ticks, env.route, (unsigned long long)env.steps,
            reward, terminal, env.base_reward, env.last_bonus, env.log.score, env.log.n);
    }
    return ferror(stdin) ? 1 : 0;
}
