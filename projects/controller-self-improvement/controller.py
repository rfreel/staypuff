"""Fixed 12-bit policy, also used to search its own configuration space."""
import math
import random


def search(config, n, budget, score, seed, initial=None, trace=False):
    rng = random.Random(seed)
    patience = (8, 16, 32, 64)[config & 3]
    radius = 1 + ((config >> 2) & 3)
    acceptance = (config >> 4) & 3
    # Remaining six bits independently control random jumps and best-state proposals.
    jumps = (0, .02, .1, .25)[(config >> 6) & 3]
    from_best = (0, .25, .5, 1)[(config >> 8) & 3]
    temperature = (.001, .005, .02, .08)[(config >> 10) & 3]
    x = rng.getrandbits(n) if initial is None else initial
    value = score(x)
    best, best_value, stale = x, value, 0
    history = [(x, value)] if trace else None
    for _ in range(1, budget):
        if stale >= patience or rng.random() < jumps:
            y = rng.getrandbits(n)
            restart = True
        else:
            y = best if rng.random() < from_best else x
            for bit in rng.sample(range(n), rng.randint(1, min(radius, n))):
                y ^= 1 << bit
            restart = False
        trial = score(y)
        if history is not None:
            history.append((y, trial))
        delta = trial - value
        accept = delta > 0
        if acceptance == 1:
            accept = delta >= 0
        elif acceptance == 2:
            accept = delta >= 0 or rng.random() < math.exp(delta / temperature)
        elif acceptance == 3:
            accept = delta >= -temperature
        if restart or accept:
            x, value = y, trial
        stale = 0 if restart or trial > best_value else stale + 1
        if trial > best_value:
            best, best_value = y, trial
    return dict(config=best, score=best_value, trace=history)


def random_search(n, budget, score, seed):
    rng = random.Random(seed)
    best, best_value = None, -float('inf')
    for _ in range(budget):
        x = rng.getrandbits(n)
        value = score(x)
        if value > best_value:
            best, best_value = x, value
    return dict(config=best, score=best_value)
