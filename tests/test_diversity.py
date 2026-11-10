"""No single stack answers every project: bundle bonuses must not outweigh the projects' own differences."""
import json
from collections import Counter
from pathlib import Path

from engine.kb import LAYERS
from engine.recommender import _core, _picks

AUDIT = Path(__file__).parent / "scenarios_extra"


def test_distinct_stacks():
    """Judge-style and consumer projects: no 4-layer stack is picked for more than 15% of them."""
    inputs = [s["input"] for f in ("quick.json", "consumer.json")
              for s in json.loads((AUDIT / f).read_text(encoding="utf-8"))]
    stacks = Counter()
    for inp in inputs:
        p = _picks(_core(inp))
        if p:
            stacks[tuple(p[l] for l in LAYERS)] += 1
    stack, n = stacks.most_common(1)[0]
    assert n <= 0.15 * len(inputs), (stack, n, len(inputs))
    assert len(stacks) >= 0.5 * len(inputs), len(stacks)
