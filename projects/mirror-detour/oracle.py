#!/usr/bin/env python3
"""Independent specification oracle plus compiling mutation calibration."""
import argparse
from collections import deque
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
PROJECT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.output and args.output.exists():
        raise SystemExit('Refusing to overwrite oracle evidence')
    spec = json.loads((PROJECT / 'oracle-spec.json').read_text())
    size, goal = spec['grid_size'], tuple(spec['goal'])
    actions = [tuple(a) for a in spec['actions']]
    worlds, distances = {}, {}
    for width, cells in spec['obstacles'].items():
        free = set(itertools.product(range(size), repeat=2)) - set(map(tuple, cells))
        graph = {p: [q if q in free else p for dx, dy in actions
                     for q in [(p[0] + dx, p[1] + dy)]] for p in free}
        dist = {goal: 0}
        queue = deque([goal])
        while queue:
            p = queue.popleft()
            for q in graph[p]:
                if q not in dist:
                    dist[q] = dist[p] + 1
                    queue.append(q)
        # Bellman certificate calibrates every distance, not just selected starts.
        assert dist[goal] == 0 and set(dist) == free
        for p in free - {goal}:
            assert dist[p] == 1 + min(dist[q] for q in graph[p])
        # Independent analytic bound for crossing the rectangular obstacle.
        for sx in range(2, 9):
            sides = [5 - int(width) - 1, 5 + int(width) + 1]
            lower_bound = 10 + min(abs(sx - side) + abs(5 - side) for side in sides)
            assert dist[sx, 10] == lower_bound
        worlds[int(width)] = graph
        distances[width] = {str(s): dist[tuple(s)] for s in
                            spec['start_cells'] + spec['heldout_start_cells']}

    cases = []
    for width, graph in worlds.items():
        for x, y in sorted(set(graph) - {goal}):
            for route, tick, action in itertools.product((-1, 0, 1), (0, 78, 79), range(4)):
                if route == 0 and y < 3:
                    continue
                cases.append((width, x, y, tick, route, action, 0, 0, 37, 0, 0))
    # All shaping modes, both sides, paid/unpaid events, boundary times,
    # evaluation gates, persistent schedules, and timeout precedence.
    for width, graph in worlds.items():
        for x in range(size):
            if (x, 3) not in graph:
                continue
            for mode, sign, step, evaluate, schedule, route, tick in itertools.product(
                    range(1, 5), (-1, 0, 1), (0, 99, 100), (0, 1), (0, 1), (-1, 0, 1), (0, 79)):
                cases.append((width, x, 3, tick, route, 2, mode, sign, step,
                              evaluate, schedule))

    def expected(case):
        width, x, y, tick, route, action, mode, sign, step, evaluate, schedule = case
        nx, ny = worlds[width][x, y][action]
        terminal = (nx, ny) == goal or tick + 1 == spec['timeout']
        base = spec['success_reward'] if (nx, ny) == goal else spec['other_reward']
        event = 0
        if route == 0 and ny < 3:
            route = -1 if nx < 5 else 1
            event = route
        bonus = 0
        if not evaluate and mode and sign and (schedule or step < 100):
            feature = event
            if mode == 2 and event:
                key = (x + 11*y)*4 + action
                key = ((key ^ 0x9e3779b9)*0x85ebca6b) & 0xffffffff
                key ^= key >> 16
                feature = 1 if key & 1 else -1
            elif mode == 3:
                before = -(abs(x - goal[0]) + abs(y - goal[1]))/20
                after = 0 if terminal else -(abs(nx - goal[0]) + abs(ny - goal[1]))/20
                feature = spec['shaping']['gamma']*after - before
            elif mode == 4:
                feature = abs(event)
            weight = spec['shaping']['strength']*(1 if schedule else 1 - step/100)
            bonus = weight*sign*feature
        # Reset positions may use either specified paired start. No RNG algorithm
        # from the candidate is copied into the reference.
        result = [nx, ny, tick + 1, route, step + 1, base + bonus,
                  int(terminal), base, bonus, base if terminal else 0, int(terminal)]
        if terminal:
            result[2:4] = [0, 0]
        return result

    expected_rows = [expected(c) for c in cases]
    input_text = ''.join(' '.join(map(str, c)) + '\n' for c in cases)
    header = (ROOT / 'ocean/mirror_detour/mirror_detour.h').read_text()
    mutations = {
        'remove_obstacle': ('|| (abs(x - 5) <= half_width', '|| (0 && abs(x - 5) <= half_width'),
        'invert_horizontal_actions': ('int dx[4] = {-1, 1, 0, 0};', 'int dx[4] = {1, -1, 0, 0};'),
        'wrong_goal': ('int success = env->x == 5', 'int success = env->x == 4'),
        'early_timeout': ('env->ticks == MD_HORIZON;', 'env->ticks == MD_HORIZON - 1;'),
        'double_base_reward': ('env->base_reward = success;', 'env->base_reward = 2*success;'),
        'stale_terminal': ('env->agents[0].terminals[0] = terminal;', 'env->agents[0].terminals[0] += terminal;'),
        'evaluation_leak': ('!env->evaluate && env->mode', 'env->mode'),
        'break_even_feature': ('feature = fabsf(feature);', 'feature = feature;'),
        'reset_schedule': ('env->ticks = 0;', 'env->ticks = 0; env->steps = 0;'),
    }
    report = dict(spec_sha256=sha(PROJECT / 'oracle-spec.json'),
                  checker_sha256=sha(PROJECT / 'oracle.py'),
                  probe_sha256=sha(PROJECT / 'oracle-probe.c'),
                  candidate_sha256=sha(ROOT / 'ocean/mirror_detour/mirror_detour.h'),
                  cases=len(cases), shortest_paths=distances, mutations={},
                  independence='Separate representation and algorithm; same author, editable CI')
    include = os.environ.get('RAYLIB_INCLUDE', str(ROOT / 'raylib-5.5_linux_amd64/include'))
    with tempfile.TemporaryDirectory(prefix='mirror-oracle-') as tmp:
        tmp = Path(tmp)
        for name in ['original', *mutations]:
            candidate = header
            if name != 'original':
                old, new = mutations[name]
                assert header.count(old) == 1, name
                candidate = header.replace(old, new)
            (tmp / 'mirror_detour.h').write_text(candidate)
            cmd = [os.environ.get('CC', 'cc'), '-std=c11', '-O1', '-ffunction-sections',
                   '-fdata-sections', '-I' + str(tmp), '-I' + str(ROOT / 'src'),
                   '-I' + include, str(PROJECT / 'oracle-probe.c'), '-Wl,--gc-sections',
                   '-lm', '-o', str(tmp / 'probe')]
            # Compile errors fail calibration; never count as detected behavior.
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            output = subprocess.check_output([str(tmp / 'probe')], input=input_text, text=True)
            rows = output.splitlines()
            assert len(rows) == len(cases), 'probe must answer every case'
            mismatch = None
            for index, (line, want) in enumerate(zip(rows, expected_rows)):
                got = list(map(float, line.split()))
                assert len(got) == len(want)
                if want[6]:
                    valid_start = tuple(got[:2]) in map(tuple, spec['start_cells'])
                    pairs = zip(got[2:], want[2:])
                else:
                    valid_start = True
                    pairs = zip(got, want)
                if not valid_start or not all(math.isclose(a, b, rel_tol=1e-5, abs_tol=1e-6)
                                              for a, b in pairs):
                    mismatch = dict(case=list(cases[index]), expected=want, observed=got)
                    break
            if name == 'original':
                assert mismatch is None, json.dumps(mismatch)
                report['original'] = 'pass'
            else:
                assert mismatch is not None, f'Oracle failed to reject mutant: {name}'
                report['mutations'][name] = dict(compiled=True, detected=True, witness=mismatch)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
