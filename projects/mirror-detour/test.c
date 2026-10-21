#include "../../ocean/mirror_detour/mirror_detour.h"

void setup(Env* env, float* buffers, int mode, int sign) {
    memset(env, 0, sizeof(*env));
    env->agents[0].observations = buffers;
    env->agents[0].actions = buffers + OBS_SIZE;
    env->agents[0].rewards = buffers + OBS_SIZE + 1;
    env->agents[0].terminals = buffers + OBS_SIZE + 2;
    Ini ini = {0};
    puf_ini_load_env(&ini, "mirror_detour", 0, NULL);
    puf_init(env, puf_ini_section(&ini, "env", 0));
    puf_ini_free(&ini);
    env->mode = mode;
    env->sign = sign;
    env->strength = 0.2f;
    env->anneal_steps = 100;
    puf_reset(env);
}

int main(void) {
    Env a, b;
    float ab[OBS_SIZE + 3] = {0};
    float bb[OBS_SIZE + 3] = {0};
    setup(&a, ab, 1, 1);
    setup(&b, bb, 1, -1);
    unsigned long checked = 0;
    for (int width = 1; width <= 3; width++) {
        for (int y = 0; y < MD_SIZE; y++) {
            for (int x = 0; x < MD_SIZE; x++) {
                if (md_blocked(x, y, width) || (x == 5 && y == 0)) {
                    continue;
                }
                for (int route = -1; route <= 1; route++) {
                    for (int tick = 0; tick < MD_HORIZON; tick++) {
                        for (int action = 0; action < 4; action++) {
                            assert(md_mirror_action(md_mirror_action(action)) == action);
                            assert(10 - (10 - x) == x);
                            a.x = x;
                            b.x = 10 - x;
                            a.y = b.y = y;
                            a.ticks = b.ticks = tick;
                            a.route = route;
                            b.route = -route;
                            a.half_width = b.half_width = width;
                            a.steps = b.steps = 25;
                            a.rng = 100;
                            b.rng = 101; // Opposite reset parity, coupled mirror starts.
                            ab[OBS_SIZE] = action;
                            bb[OBS_SIZE] = md_mirror_action(action);
                            // route=0 above the obstacle is unreachable in actual episodes.
                            if (route == 0 && y < 3) {
                                continue;
                            }
                            puf_step(&a);
                            puf_step(&b);
                            assert(a.x == 10 - b.x && a.y == b.y);
                            assert(a.route == -b.route);
                            assert(a.ticks == b.ticks && a.steps == b.steps);
                            assert(a.base_reward == b.base_reward);
                            assert(ab[OBS_SIZE + 2] == bb[OBS_SIZE + 2]);
                            assert(ab[OBS_SIZE + 1] == bb[OBS_SIZE + 1]);
                            assert(a.last_bonus == b.last_bonus);
                            assert(ab[0] == -bb[0] && ab[3] == -bb[3]);
                            for (int i = 0; i < OBS_SIZE; i++) {
                                assert(isfinite(ab[i]) && fabsf(ab[i]) <= 1);
                            }
                            checked++;
                        }
                    }
                }
            }
        }
    }
    // Same trajectory: opposite signs reverse only the bonus, not the dynamics.
    for (int sign = -1; sign <= 1; sign++) {
        setup(&a, ab, 1, sign);
        a.x = 2;
        a.y = 3;
        ab[OBS_SIZE] = 2;
        puf_step(&a);
        assert(a.last_bonus == -sign*0.2f && a.route == -1);
        ab[OBS_SIZE] = 3;
        puf_step(&a);
        ab[OBS_SIZE] = 2;
        puf_step(&a);
        assert(a.last_bonus == 0); // Cannot farm the event.
    }
    // Equal-route control: same positive bonus under reflection, once only.
    setup(&a, ab, 4, 1);
    setup(&b, bb, 4, 1);
    a.x = 2;
    b.x = 8;
    a.y = b.y = 3;
    ab[OBS_SIZE] = bb[OBS_SIZE] = 2;
    puf_step(&a);
    puf_step(&b);
    assert(a.last_bonus == 0.2f && b.last_bonus == 0.2f);
    assert(a.route == -1 && b.route == 1);
    ab[OBS_SIZE] = bb[OBS_SIZE] = 3;
    puf_step(&a);
    puf_step(&b);
    ab[OBS_SIZE] = bb[OBS_SIZE] = 2;
    puf_step(&a);
    puf_step(&b);
    assert(a.last_bonus == 0 && b.last_bonus == 0);
    // Baseline parity across mode=0, sign=0, strength=0, and evaluation.
    for (int disabled = 0; disabled < 4; disabled++) {
        setup(&a, ab, 0, 0);
        setup(&b, bb, 1, 1);
        if (disabled == 0) {
            b.mode = 0;
        } else if (disabled == 1) {
            b.sign = 0;
        } else if (disabled == 2) {
            b.strength = 0;
        } else {
            b.evaluate = 1;
        }
        uint32_t rng = 42;
        for (int i = 0; i < 10000; i++) {
            rng = rng*1664525u + 1013904223u;
            ab[OBS_SIZE] = bb[OBS_SIZE] = (rng >> 24) % 4;
            puf_step(&a);
            puf_step(&b);
            assert(memcmp(ab, bb, sizeof(ab)) == 0);
            assert(a.rng == b.rng && a.steps == b.steps);
            assert(memcmp(&a.log, &b.log, sizeof(Log)) == 0);
        }
    }
    // Annealing endpoint, zero duration, episode reset and offset restoration.
    for (int step = 99; step <= 101; step++) {
        setup(&a, ab, 1, 1);
        a.steps = step;
        a.x = 2;
        a.y = 3;
        ab[OBS_SIZE] = 2;
        puf_step(&a);
        assert((a.last_bonus != 0) == (step == 99));
        puf_reset(&a);
        assert(a.steps == (uint64_t)step + 1);
    }
    setup(&a, ab, 1, 1);
    a.anneal_steps = 0;
    a.x = 2;
    a.y = 3;
    ab[OBS_SIZE] = 2;
    puf_step(&a);
    assert(a.last_bonus == 0 && isfinite(ab[OBS_SIZE + 1]));
    // Persistent control remains active; evaluation disables every mode.
    for (int mode = 1; mode <= 4; mode++) {
        setup(&a, ab, mode, 1);
        a.schedule = 1;
        a.steps = 10000;
        a.x = 2;
        a.y = 3;
        ab[OBS_SIZE] = 2;
        puf_step(&a);
        assert(isfinite(a.last_bonus) && a.last_bonus != 0);
        a.evaluate = 1;
        a.route = 0;
        a.x = 2;
        a.y = 3;
        puf_step(&a);
        assert(a.last_bonus == 0);
    }
    // Config offset must be respected by init, not just direct field assignment.
    Ini ini = {0};
    puf_ini_load_env(&ini, "mirror_detour", 0, NULL);
    puf_ini_put(&ini, "env.step_offset", "2500");
    puf_init(&a, puf_ini_section(&ini, "env", 0));
    puf_reset(&a);
    assert(a.steps == 2500);
    puf_ini_free(&ini);
    // Terminal success is retained while observations reset; next step clears it.
    setup(&a, ab, 0, 0);
    a.x = 5;
    a.y = 1;
    ab[OBS_SIZE] = 2;
    puf_step(&a);
    assert(a.base_reward == 1 && ab[OBS_SIZE + 1] == 1 && ab[OBS_SIZE + 2] == 1);
    assert(a.log.score == 1 && a.log.n == 1 && a.y == 10 && a.ticks == 0);
    puf_step(&a);
    assert(ab[OBS_SIZE + 1] == 0 && ab[OBS_SIZE + 2] == 0);
    Dict out = {0};
    puf_log(&a.log, &out);
    assert(dict_get(&out, "score") == 1 && dict_get(&out, "bonus") == 0);
    dict_clear(&out);
    printf("PASS: %lu mirrored transitions; baseline parity, reset, schedule, logging\n", checked);
}
