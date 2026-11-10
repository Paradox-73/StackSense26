"""How stable is a pick? The knowledge base's 1-5 scores are judgement calls, so this re-runs the
engine with every score shifted by seeded random noise and counts how often each layer keeps its pick.

The noise is applied to a copy of each item's scores; the cached knowledge base is never changed.
The seed comes from a hash of the answers, so the same answers always give the same percentages."""
from __future__ import annotations

import hashlib
import json
import random
from copy import deepcopy

from .kb import LAYERS, load_kb
from .recommender import _core, _picks

NOISE_LEVELS = (0.25, 0.5)  # +/- uniform shift on every 1-5 score
RUNS = 30


def _seed(raw: dict, noise: float) -> int:
    key = json.dumps(raw, sort_keys=True, default=str) + f"|{noise}"
    return int(hashlib.sha256(key.encode()).hexdigest()[:12], 16)


def _noisy_kb(rng: random.Random, noise: float) -> dict:
    kb = load_kb()
    out = {"rules": kb["rules"]}
    for layer in LAYERS:
        out[layer] = [dict(it, scores={k: min(5.0, max(1.0, v + rng.uniform(-noise, noise)))
                                       for k, v in it.get("scores", {}).items()}) for it in kb[layer]]
    out["index"] = {it["id"]: dict(it, layer=layer) for layer in LAYERS for it in out[layer]}
    return out


def robustness(raw: dict | None, runs: int = RUNS, levels: tuple = NOISE_LEVELS) -> dict:
    raw = deepcopy(raw or {})
    kb = load_kb()
    base = _picks(_core(deepcopy(raw)))
    if not base:
        return {"feasible": False}
    out = {"feasible": True, "runs": runs, "levels": list(levels),
           "base": {l: kb["index"][base[l]]["name"] for l in LAYERS}, "layers": {l: [] for l in LAYERS}}
    for noise in levels:
        rng = random.Random(_seed(raw, noise))
        counts = {l: {} for l in LAYERS}
        for _ in range(runs):
            picks = _picks(_core(deepcopy(raw), kb=_noisy_kb(rng, noise)))
            for l in LAYERS:
                pid = picks.get(l)
                counts[l][pid] = counts[l].get(pid, 0) + 1
        for l in LAYERS:
            held = counts[l].get(base[l], 0)
            others = sorted(((n, kb["index"][i]["name"] if i else "no feasible option") for i, n in counts[l].items()
                             if i != base[l]), reverse=True)
            out["layers"][l].append({"noise": noise, "held_pct": round(100 * held / runs),
                                     "others": [{"name": nm, "pct": round(100 * n / runs)} for n, nm in others[:3]]})
    return out
