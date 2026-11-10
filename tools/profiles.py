"""Seeded random project profiles built from data/questions.json (used by tools/fuzz.py and the tests).

Every value comes from the questionnaire's own options and ranges, so each profile is a valid answer set.
Numbers are drawn log-uniformly over realistic ranges; about 10% of answers are left out so defaults apply.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.kb import field_specs  # noqa: E402

SPECS = field_specs()
NUM_RANGES = {"dau": (1, 5e7), "peak_rps": (0.1, 2e5), "data_volume_gb": (0.01, 2e5), "data_growth_gb_month": (0.0, 5e3),
              "latency_target_ms": (10, 5000), "team_size": (1, 300), "timeline_weeks": (1, 104), "budget_monthly": (0, 2e5),
              "peak_concurrent": (1, 1e6)}
INR_PER_USD = 96


def _num(rng: random.Random, key: str, spec: dict) -> float:
    a, b = NUM_RANGES.get(key, (spec.get("min", 0), spec.get("max", 1e6)))
    if a <= 0:
        if rng.random() < 0.15:
            return 0
        a = 0.01
    v = math.exp(rng.uniform(math.log(a), math.log(b)))
    return int(round(v)) if key in ("dau", "team_size", "timeline_weeks", "peak_concurrent") else round(v, 2)


def random_input(rng: random.Random, omit_p: float = 0.1) -> dict:
    out: dict = {}
    for key, spec in SPECS.items():
        if key == "project_name":
            out[key] = "Random project"
            continue
        if rng.random() < omit_p:
            continue
        t = spec["type"]
        if t == "number":
            if key in ("peak_rps", "peak_concurrent") and rng.random() < 0.6:
                continue
            out[key] = _num(rng, key, spec)
        elif t == "select":
            out[key] = rng.choice([o["value"] for o in spec["options"]])
        elif t == "bool":
            out[key] = rng.random() < 0.3
        elif t == "multiselect":
            opts = [o["value"] for o in spec["options"]]
            k = {"compliance": [0, 0, 1, 1, 2, 3], "team_skills": [0, 0, 1, 2, 3, 4, 6]}.get(key, [1, 1, 2, 3])
            vals = rng.sample(opts, min(rng.choice(k), len(opts)))
            if key in ("platforms", "data_shapes", "regions") and not vals:
                vals = [opts[0]]
            out[key] = vals
    if out.get("currency") == "INR" and "budget_monthly" in out:
        out["budget_monthly"] = round(out["budget_monthly"] * INR_PER_USD, 2)
    return out


def profiles(seed: int, n: int, omit_p: float = 0.1) -> list[dict]:
    rng = random.Random(seed)
    return [random_input(rng, omit_p) for _ in range(n)]
