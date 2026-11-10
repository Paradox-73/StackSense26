"""Regression guard on the answer key (tests/benchmark/answer_key.json).

The key was written before any measurement. These floors sit a little under the measured rates, so a
change that makes picks agree less with the key fails here. They are not targets to tune towards.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import bench  # noqa: E402

KEY_DIR = ROOT / "tests" / "benchmark"

# Measured on the final engine: tuning 86/118 top-1, 106/120 acceptable; held-out 24/40 and 37/40.
FLOORS = {
    "tuning": {"top1": 0.68, "acceptable": 0.85},
    "held_out": {"top1": 0.60, "acceptable": 0.85},
}
LAYER_ACCEPTABLE_FLOOR = 0.75


@pytest.fixture(scope="module")
def results():
    rows = bench.run()
    return rows, bench.split_rates(rows)


def test_answer_key_is_unchanged():
    want = (KEY_DIR / "answer_key.sha256").read_text(encoding="utf-8").split()[0]
    assert hashlib.sha256(bench.key_bytes()).hexdigest() == want


def test_key_shape_and_sources():
    key = bench.load_key()
    briefs = key["briefs"]
    assert len(briefs) == 40
    assert sum(b["held_out"] for b in briefs) == 10
    for b in briefs:
        assert set(b["layers"]) == set(bench.LAYERS)
        for spec in b["layers"].values():
            assert len(spec["votes"]) == 3
            assert spec["acceptable"]
            for v in spec["votes"]:
                assert v["source"].startswith("http"), b["id"]


@pytest.mark.parametrize("part", ["tuning", "held_out"])
def test_hit_rate_floors(results, part):
    _, sr = results
    allc = sr[part]["all"]
    assert allc["top1"][0] / allc["top1"][1] >= FLOORS[part]["top1"]
    assert allc["acceptable"][0] / allc["acceptable"][1] >= FLOORS[part]["acceptable"]


@pytest.mark.parametrize("layer", bench.LAYERS)
def test_every_layer_mostly_acceptable(results, layer):
    _, sr = results
    h, n = sr["all"][layer]["acceptable"]
    assert h / n >= LAYER_ACCEPTABLE_FLOOR


def test_labellers_agree_with_each_other():
    ag = bench.agreement()
    assert ag["all"]["alpha"] > 0.8
