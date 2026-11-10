"""Explanations must match the engine's own numbers: every score, margin and project figure quoted in
the text is checked against the structured result it claims to describe."""
import random
import re
from copy import deepcopy

import pytest

from engine import recommend
from engine.export import _num, to_markdown
from engine.kb import LAYERS, load_presets
from tools.profiles import random_input

WHY = re.compile(r"^(.+?): ([\d.]+)/5 vs ([\d.]+) average for this layer")
STRONGER = re.compile(r"(\S[^;.]*?) is stronger on ((?:[^;()]+ \([\d.]+ vs [\d.]+\)(?:, )?)+)")
PAIR = re.compile(r"([^,()]+?) \(([\d.]+) vs ([\d.]+)\)")


@pytest.fixture(scope="module")
def runs():
    inputs = [(p["id"], p["input"]) for p in load_presets()]
    rng = random.Random(51)
    inputs += [(f"random {i}", random_input(rng)) for i in range(120)]
    out = []
    for name, inp in inputs:
        r = recommend(deepcopy(inp), with_counterfactuals=False)
        if r["feasible"]:
            out.append((name, r))
    return out


def _bd(s):
    return {b["label"]: b for b in s["pick"]["breakdown"]}


def test_why_lines_quote_the_picks_own_scores(runs):
    for name, r in runs:
        for l in LAYERS:
            s = r["stack"][l]
            if s.get("optional_host"):
                continue
            bd = _bd(s)
            for line in s["explanation"]["why"]:
                m = WHY.match(line)
                if m:
                    assert m.group(1) in bd, (name, l, line)
                    assert abs(bd[m.group(1)]["score"] - float(m.group(2))) <= 0.051, (name, l, line)


def test_margin_and_runner_up_match_the_alternatives(runs):
    for name, r in runs:
        for l in LAYERS:
            s = r["stack"][l]
            vs = s["explanation"]["vs_runner_up"]
            if not vs or not s["alternatives"]:
                continue
            alt = s["alternatives"][0]
            assert vs["runner_up"] == alt["name"], (name, l)
            assert abs(vs["margin"] + alt["delta_vs_pick"]) <= 0.02, (name, l, vs["margin"], alt["delta_vs_pick"])
            # The text states the same margin, with the sign the number has.
            assert f"{abs(vs['margin']):.1f}" in vs["text"], (name, l, vs["text"])


def test_criterion_comparisons_quote_real_scores(runs):
    """'<pick> is stronger on X (a vs b)' must use the pick's breakdown score a for X."""
    for name, r in runs:
        for l in LAYERS:
            s = r["stack"][l]
            bd = {b["label"].lower(): b["score"] for b in s["pick"]["breakdown"]}
            texts = [x["text"] for x in s.get("why_not", [])]
            vs = s["explanation"]["vs_runner_up"]
            if vs and vs["tie"]:
                texts.append(vs["text"])
            for t in texts:
                for m in STRONGER.finditer(t):
                    if not m.group(1).strip().endswith(s["pick"]["name"]):
                        continue
                    for crit, a, _ in PAIR.findall(m.group(2)):
                        crit = crit.strip().lower()
                        if crit in bd:
                            assert abs(bd[crit] - float(a)) <= 0.051, (name, l, crit, a, t)


def test_contributions_and_paragraph_numbers_match(runs):
    for name, r in runs:
        p, d = r["profile"], r["derived"]
        for l in LAYERS:
            s = r["stack"][l]
            total = sum(c["points"] for c in s["explanation"]["input_contributions"])
            assert abs(total - s["pick"]["score"]) <= 0.5, (name, l, total, s["pick"]["score"])
            # The scale-tier labels name a range ("Hobby (<1k daily users)"), not the project's own count.
            para = s["explanation"]["paragraph"].replace(d["tier_label"], "").replace(d["db_tier_label"], "")
            if "daily users" in para:
                assert f"{p['dau']:,}" in para, (name, l, para)
            if "requests/s at peak" in para and d["peak_rps"]:
                assert _num(d["peak_rps"]) in para, (name, l, para)


def test_export_shows_signed_margins_correctly(runs):
    for name, r in runs[:40]:
        md = to_markdown(r)
        assert not re.search(r"[−-]-\d|\+-\d|by -\d", md), name
