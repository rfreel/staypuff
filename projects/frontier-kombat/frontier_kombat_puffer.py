#!/usr/bin/env python3
"""Frontier Kombat: 20 synthetic OOD fighting-game control tasks.

The C11 simulation uses a shared-memory SoA ABI. This is a research game, NOT an
accurate reproduction of commercial fighting games or actual GGPO netcode.
"""
from __future__ import annotations
import argparse
import ctypes
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from multiprocessing import shared_memory

import numpy as np

NUM_ELITE_ENVS = 20
OBS_DIM = 24
ACTION_COUNT = 72

NAMES = (
    "HadoukenDopplerShift", "ShoryukenInverseIFrame", "SonicBoomChargeCapacitor",
    "KarateCancelPolytope", "ZangiefSPDNonEuclideanReach", "KombatDialDyckGrammar",
    "ScorpionTetherNonMarkov", "SubZeroFreezeEntropyFloor", "ShangTsungMorphLatentMirror",
    "FatalitySweepDistanceCompiler", "GGPORollbackDesyncMirage", "DhalsimPhantomLimbHurtbox",
    "BisonPsychoReflectorParity", "VegaWallClimbHomotopy", "RaidenTeleportPhaseAliasing",
    "SuperComboThermodynamicGauge", "OkizemeMinimaxWakeupGame", "ChipDamageZenoParadox",
    "RedParryFrameTrapChaos", "ShaoKahnBossTauntMetaCritic",
)
DOMAINS = ("Nonstationary physics", "Input grammar", "Partial observation", "Resource game")

@dataclass(frozen=True)
class EliteEnvSpec:
    code: str
    env_id: int
    name: str
    domain: str
    mechanism: str

MECHANISMS = (
    "Periodically shifting projectile velocity and recovery",
    "Invulnerability starts later under low input diversity",
    "Charge accumulation and overcharge discharge",
    "Cancel acceptance depends on a rotating phase window",
    "Non-Euclidean distance proxy for grapple reach",
    "Dyck-like two-token balance for combo damage",
    "Delayed tether impulse depends on historical input parity",
    "Repeated input sequences trigger freeze backfire",
    "Opponent counter-archetype morphs over time",
    "Finish requires a range-specific terminal token",
    "Opponent visual coordinate delayed and extrapolated",
    "Attack and hurtbox offsets change independently",
    "Odd movement parity reflects non-grab damage",
    "Vortex deflection and counterdirection anti-air",
    "Cross-up swaps directional interpretation",
    "Heat accumulation and cooling during idle frames",
    "Rotating minimax mixup on wakeup",
    "Repeated attacks suffer geometric damage decay",
    "Logistic-map frame trap with parry window",
    "Opponent predicts last-button class and counterattacks",
)
ELITE_20_SPECS = tuple(EliteEnvSpec(f"E{i+1:02d}", i, name, DOMAINS[i//5], MECHANISMS[i]) for i, name in enumerate(NAMES))

# Public zero-copy observation/action/terminal buffers use separate contiguous
# blocks; state is a NumPy structured array matching an explicit C ABI.
STATE_DTYPE = np.dtype([
    ("env_idx", "i4"), ("env_id", "i4"), ("ood", "i4"), ("step", "i4"),
    ("episodes", "i4"), ("seed", "u4"), ("severity", "f4"),
    ("p1_x", "f4"), ("p1_y", "f4"), ("p1_vx", "f4"), ("p1_hp", "f4"),
    ("p1_meter", "f4"), ("p1_heat", "f4"), ("p1_state", "i4"),
    ("p1_move", "i4"), ("p1_frame", "i4"), ("p1_stun", "i4"),
    ("p1_invuln", "i4"), ("p1_charge", "i4"), ("dyck", "i4"),
    ("p2_x", "f4"), ("p2_y", "f4"), ("p2_vx", "f4"), ("p2_hp", "f4"),
    ("p2_state", "i4"), ("p2_move", "i4"), ("p2_frame", "i4"),
    ("p2_stun", "i4"), ("p2_morph", "i4"), ("proj_x", "f4"),
    ("proj_v", "f4"), ("proj_active", "i4"), ("metric", "f4"),
    ("phase", "f4"), ("parity", "i4"), ("fatality", "i4"),
    ("history", "u1", 16), ("buttons", "u1", 16), ("hist_idx", "i4"), ("last_button", "i4"),
    ("p1_input_dir", "i4"), ("p1_input_btn", "i4"),
    ("wins_p1", "i4"), ("wins_p2", "i4"),
    ("cumulative", "f4"), ("last_episode_return", "f4"),
    ("verdict", "i4"), ("rng", "u4"),
], align=True)

SRC = Path(__file__).with_name("frontier_kombat_kernel.c")
LIB_CACHE: ctypes.CDLL | None = None


def build_library(output: Path | None = None) -> Path:
    """Build from the tracked source, never run Python-generated untrusted source."""
    if output is None:
        output = Path(tempfile.gettempdir()) / f"libfrontier_kombat_{os.getpid()}.so"
    cmd = [os.environ.get("CC", "gcc"), "-std=c11", "-O3", "-fopenmp", "-fPIC", "-shared",
           str(SRC), "-lm", "-o", str(output)]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return output


def load_library() -> ctypes.CDLL:
    global LIB_CACHE
    if LIB_CACHE is not None:
        return LIB_CACHE
    lib = ctypes.CDLL(str(build_library()))
    lib.kombat_state_size.restype = ctypes.c_size_t
    if lib.kombat_state_size() != STATE_DTYPE.itemsize:
        raise RuntimeError(f"ABI mismatch: C {lib.kombat_state_size()}, NumPy {STATE_DTYPE.itemsize}")
    lib.kombat_state_offset.argtypes = [ctypes.c_int]
    lib.kombat_state_offset.restype = ctypes.c_size_t
    for i, field in enumerate(STATE_DTYPE.names):
        if lib.kombat_state_offset(i) != STATE_DTYPE.fields[field][1]:
            raise RuntimeError(f"ABI offset mismatch for {field}")
    lib.c_reset_batch.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p]
    lib.c_step_batch.argtypes = [ctypes.c_void_p, ctypes.c_int32, ctypes.c_void_p,
                                 ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    LIB_CACHE = lib
    return lib


def _aligned(pos: int, alignment: int = 64) -> int:
    return (pos + alignment - 1) // alignment * alignment


class FrontierKombatPufferEnv:
    """Zero-copy contiguous I/O views; state and buffers share a POSIX memory slab.

    PufferLib-shaped interface, not automatically a native PufferLib registered env.
    """
    def __init__(self, num_envs: int = 2048, env_id: int | None = None,
                 ood_active: bool = True, ood_severity: float = 1., seed: int = 42):
        if num_envs <= 0 or (env_id is not None and not 0 <= env_id < 20):
            raise ValueError("num_envs must be positive and env_id must be 0..19")
        if not 0 <= ood_severity <= 2 or not np.isfinite(ood_severity):
            raise ValueError("ood_severity must be finite in 0..2")
        self.lib = load_library()
        self.num_envs = int(num_envs)
        pos = 0
        spans = {}
        for name, shape, dtype in [
            ("slots", (num_envs,), STATE_DTYPE),
            ("observations", (num_envs, OBS_DIM), np.float32),
            ("actions", (num_envs,), np.int32),
            ("rewards", (num_envs,), np.float32),
            ("terminals", (num_envs,), np.uint8),
            ("truncations", (num_envs,), np.uint8),
        ]:
            pos = _aligned(pos)
            spans[name] = (pos, shape, dtype)
            pos += int(np.prod(shape)) * np.dtype(dtype).itemsize
        self.shm = shared_memory.SharedMemory(create=True, size=pos)
        self.closed = False
        for name, (offset, shape, dtype) in spans.items():
            setattr(self, name, np.ndarray(shape, dtype=dtype, buffer=self.shm.buf, offset=offset))
        self.slots.fill(0)
        self.observations.fill(0)
        self.actions.fill(0)
        self.rewards.fill(0)
        self.terminals.fill(0)
        self.truncations.fill(0)
        self.slots["env_idx"] = np.arange(num_envs)
        self.slots["env_id"] = (np.arange(num_envs) % 20) if env_id is None else env_id
        self.slots["ood"] = int(bool(ood_active))
        self.slots["severity"] = ood_severity
        self.slots["seed"] = (np.arange(num_envs, dtype=np.uint32) + np.uint32(seed))
        self.reset()

    @staticmethod
    def _ptr(arr: np.ndarray) -> ctypes.c_void_p:
        return ctypes.c_void_p(arr.ctypes.data)

    def reset(self, seed: int | None = None):
        if self.closed:
            raise RuntimeError("closed")
        if seed is not None:
            self.slots["seed"] = np.arange(self.num_envs, dtype=np.uint32) + np.uint32(seed)
            self.slots["episodes"].fill(0)
        self.lib.c_reset_batch(self._ptr(self.slots), self.num_envs, self._ptr(self.observations))
        self.rewards.fill(0)
        self.terminals.fill(0)
        self.truncations.fill(0)
        return self.observations, []

    def step(self, actions: np.ndarray | None = None):
        if self.closed:
            raise RuntimeError("closed")
        if actions is not None:
            a = np.asarray(actions)
            if a.shape != (self.num_envs,) or not np.issubdtype(a.dtype, np.integer):
                raise ValueError("actions must be a 1D integral vector of length num_envs")
            if np.any(a < 0) or np.any(a >= 72):
                raise ValueError("actions outside 0..71")
            np.copyto(self.actions, a, casting="unsafe")
        self.lib.c_step_batch(self._ptr(self.slots), self.num_envs,
                              self._ptr(self.actions), self._ptr(self.observations),
                              self._ptr(self.rewards), self._ptr(self.terminals),
                              self._ptr(self.truncations))
        return self.observations, self.rewards, self.terminals, self.truncations, []

    def close(self):
        if not self.closed:
            self.closed = True
            self.shm.close()
            self.shm.unlink()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def policy_arcade(slots: np.ndarray) -> np.ndarray:
    return np.where((slots["step"] & 1) == 0, 5 * 8 + 2, 1 * 8 + 5).astype(np.int32)


def policy_reactive(slots: np.ndarray) -> np.ndarray:
    """A causal heuristic from observable approximations; not a trained policy."""
    a = np.full(len(slots), 5 * 8 + 3, dtype=np.int32)
    eid = slots["env_id"]
    for i in range(len(slots)):
        k = int(eid[i]); s = slots[i]
        if k == 2:
            a[i] = 5 * 8 + 5 if 3 <= s["p1_charge"] <= 8 else 3 * 8
        elif k == 5:
            a[i] = 5 * 8 + (4 if s["dyck"] else 1)
        elif k == 9:
            a[i] = 5 * 8 + (7 if s["p2_hp"] < 24 and abs(s["p2_x"] - s["p1_x"]) <= 85 else 3)
        elif k == 15:
            a[i] = 4 * 8 + (6 if s["p1_heat"] > 4 else 3)
        elif k == 16:
            a[i] = 5 * 8 + (1 + ((s["parity"] + s["step"] // 45) & 3))
        elif k == 17:
            a[i] = 5 * 8 + (4 if s["last_button"] == 3 else 3)
        elif k == 18:
            a[i] = 5 * 8 + (6 if s["metric"] > .65 else 4)
        elif k == 19:
            a[i] = 5 * 8 + (4 if s["last_button"] == 3 else 3)
    return a


def run_benchmark(envs_per_spec: int = 32, rollout_steps: int = 200,
                  speed_envs: int = 1024, speed_steps: int = 200) -> dict:
    if envs_per_spec <= 0 or rollout_steps <= 0 or speed_envs <= 0 or speed_steps <= 0:
        raise ValueError("all benchmark counts must be positive")
    with FrontierKombatPufferEnv(num_envs=speed_envs, seed=90) as env:
        rng = np.random.default_rng(199)
        fixed = rng.integers(0, 72, size=speed_envs, dtype=np.int32)
        t = time.perf_counter()
        for _ in range(speed_steps):
            env.step(fixed)
        elapsed = time.perf_counter() - t
        good = bool(np.all(env.slots["verdict"] == 1))
        rate = speed_envs * speed_steps / elapsed

    reports = []
    total = 20 * envs_per_spec
    outcomes = {}
    for label, ood, pol in (("id_arcade", False, policy_arcade),
                            ("ood_arcade", True, policy_arcade),
                            ("ood_reactive", True, policy_reactive)):
        with FrontierKombatPufferEnv(num_envs=total, ood_active=ood, seed=2026) as env:
            wins0 = env.slots["wins_p1"].copy()
            total_reward = np.zeros(total, dtype=np.float64)
            for _ in range(rollout_steps):
                _, rewards, _, _, _ = env.step(pol(env.slots))
                total_reward += rewards
            outcomes[label] = {
                "wins": (env.slots["wins_p1"] - wins0).reshape(20, envs_per_spec).sum(axis=1).tolist(),
                "return": total_reward.reshape(20, envs_per_spec).mean(axis=1).tolist(),
                "invariants": bool(np.all(env.slots["verdict"] == 1)),
            }
    for spec in ELITE_20_SPECS:
        i = spec.env_id
        reports.append({"code": spec.code, "name": spec.name, "domain": spec.domain,
                        "id_arcade_return": round(outcomes["id_arcade"]["return"][i], 3),
                        "ood_arcade_return": round(outcomes["ood_arcade"]["return"][i], 3),
                        "ood_reactive_return": round(outcomes["ood_reactive"]["return"][i], 3),
                        "ood_arcade_wins": outcomes["ood_arcade"]["wins"][i],
                        "ood_reactive_wins": outcomes["ood_reactive"]["wins"][i]})
    return {"suite": "Frontier Kombat 20 synthetic OOD tests", "num_environments": 20,
            "observation_dim": 24, "actions": 72,
            "throughput": {"steps": speed_envs * speed_steps,
                           "seconds": elapsed, "frames_per_second": rate,
                           "invariants": good},
            "evaluation": {"total_envs": total, "steps": rollout_steps,
                           "all_invariants": all(x["invariants"] for x in outcomes.values()),
                           "return_definition": "sum of step rewards over rollout for each slot, averaged by environment"},
            "environments": reports}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--envs-per-spec", type=int, default=32)
    p.add_argument("--steps", type=int, default=200)
    p.add_argument("--speed-envs", type=int, default=1024)
    p.add_argument("--speed-steps", type=int, default=200)
    p.add_argument("--json-out")
    args = p.parse_args()
    report = run_benchmark(args.envs_per_spec, args.steps, args.speed_envs, args.speed_steps)
    result = json.dumps(report, indent=2)
    if args.json_out:
        Path(args.json_out).write_text(result + "\n")
    print(result)


if __name__ == "__main__":
    main()
