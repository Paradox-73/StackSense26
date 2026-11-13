"""Every supporting service is explained like a core pick (FR5): at least one alternative with the reason it lost, at
least one trade-off, and the scenario fields that drove it. A number a justification quotes is one the scenario gives;
the users the stack is sized for are stated once in the assumptions, not repeated on every service."""
import json
import re
from pathlib import Path

import pytest

from engine.standard import run

ROOT = Path(__file__).resolve().parent.parent
FILES = sorted((ROOT / "scenarios" / "public").glob("P*.json")) + sorted((ROOT / "scenarios" / "edge").glob("E*.json"))


def _numbers(doc) -> set[float]:
    if isinstance(doc, dict):
        return set().union(*map(_numbers, doc.values())) if doc else set()
    if isinstance(doc, list):
        return set().union(*map(_numbers, doc)) if doc else set()
    if isinstance(doc, bool):
        return set()
    if isinstance(doc, (int, float)):
        return {float(doc)}
    if isinstance(doc, str) and re.fullmatch(r"\d+(\.\d+)?", doc):
        return {float(doc)}
    return set()


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.stem)
def test_each_supporting_service_has_an_alternative_a_tradeoff_and_its_fields(path):
    doc = json.loads(path.read_text(encoding="utf-8"))
    out = run(doc)
    if not out.get("stack"):
        pytest.skip("no stack")
    given = _numbers(doc)
    for s in out["stack"]["supporting"]:
        assert s["alternatives"] and all(a["choice"] and a["why_not"] for a in s["alternatives"]), s
        assert s["tradeoffs"] and s["driven_by"], s
        assert "expected at 12 months" not in s["justification"], s["justification"]
        # The quoted number names the scenario field it comes from, e.g. "300,000 users ... (scale.users_12_months)".
        cited = re.findall(r"(\d[\d,]*(?:\.\d+)?)[^.(]*\(((?:scale|requirements|team|infrastructure)\.[a-z0-9_]+)\)",
                           s["justification"])
        quoted = {float(n.replace(",", "")) for n, _ in cited}
        assert not cited or quoted & given or not given, (s["layer"], s["choice"], s["justification"][-160:])
