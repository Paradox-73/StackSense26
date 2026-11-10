"""Score the engine against the answer key in tests/benchmark/answer_key.json.

    python tools/bench.py                 # summary tables
    python tools/bench.py --briefs        # plus one line per brief
    python tools/bench.py --json-out r.json

The answer key was written before any measurement by a language model playing three architect
personas (see "labellers" in the key), blind to the engine: it had no access to the engine's code or
outputs. The labellers are personas, not human raters. 40 project briefs, three personas per layer,
each pick with a source. "best" is the pick chosen by at least 2 of 3
labellers; "acceptable" is every pick that at least 2 of 3 accept. Ten briefs are held out
and were never used for tuning.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import recommend  # noqa: E402

KEY_DIR = os.path.join(ROOT, "tests", "benchmark")
LAYERS = ("frontend", "backend", "database", "hosting")


def key_bytes():
    with open(os.path.join(KEY_DIR, "answer_key.json"), "rb") as f:
        return f.read().replace(b"\r\n", b"\n")


def verify_hash():
    want = open(os.path.join(KEY_DIR, "answer_key.sha256"), encoding="utf-8").read().split()[0]
    return hashlib.sha256(key_bytes()).hexdigest() == want


def load_key():
    return json.loads(key_bytes().decode("utf-8"))


# The key was written with one "none" option per layer. The engine has explicit items for it,
# and shows hosting as "Provided by <BaaS>" for a mobile-only app on a backend-as-a-service.
NONE_IDS = {"no_custom_backend", "none_static"}


def picks_for(inp):
    """{layer: set of ids that count for the pick}: its own id, plus "none" where it means none."""
    r = recommend(inp)
    out = {}
    for layer in LAYERS:
        pick = r["stack"][layer]["pick"]
        ids = {pick["id"]}
        if pick["id"] in NONE_IDS or str(pick["name"]).startswith("Provided by"):
            ids.add("none")
        out[layer] = ids
    return out


def score_brief(brief):
    return score_ids(brief, picks_for(brief["input"]))


def score_ids(brief, got):
    """Score {layer: set of ids} against one brief's key. Shared with tools/llm_baseline.py so both use the same rule."""
    row = {"id": brief["id"], "title": brief["title"], "held_out": brief["held_out"], "layers": {}}
    for layer in LAYERS:
        spec = brief["layers"][layer]
        ids = got[layer]
        pick = sorted(ids, key=lambda i: i == "none")[0]
        row["layers"][layer] = {
            "pick": pick,
            "best": spec["best"],
            "acceptable": spec["acceptable"],
            "top1": None if spec["best"] is None else spec["best"] in ids,
            "ok": bool(ids & set(spec["acceptable"])),
        }
    return row


def run():
    key = load_key()
    return [score_brief(b) for b in key["briefs"]]


def rates(rows):
    """{layer or 'all': {top1: (hits, n), acceptable: (hits, n)}}"""
    out = {}
    for layer in LAYERS + ("all",):
        t = [0, 0]
        a = [0, 0]
        for row in rows:
            for ly, cell in row["layers"].items():
                if layer not in (ly, "all"):
                    continue
                if cell["top1"] is not None:
                    t[1] += 1
                    t[0] += cell["top1"]
                a[1] += 1
                a[0] += cell["ok"]
        out[layer] = {"top1": tuple(t), "acceptable": tuple(a)}
    return out


def split_rates(rows):
    return {
        "tuning": rates([r for r in rows if not r["held_out"]]),
        "held_out": rates([r for r in rows if r["held_out"]]),
        "all": rates(rows),
    }


def agreement(key=None):
    """How much the three labellers agree on the best pick, per layer."""
    key = key or load_key()
    out = {}
    for layer in LAYERS + ("all",):
        pair_hits = pair_n = unanimous = n = 0
        units = []
        for b in key["briefs"]:
            for ly, spec in b["layers"].items():
                if layer not in (ly, "all"):
                    continue
                votes = [v["best"] for v in spec["votes"]]
                units.append(votes)
                n += 1
                unanimous += len(set(votes)) == 1
                for x, y in itertools.combinations(votes, 2):
                    pair_n += 1
                    pair_hits += x == y
        out[layer] = {
            "pairwise": pair_hits / pair_n,
            "unanimous": unanimous / n,
            "alpha": krippendorff_alpha(units),
            "units": n,
        }
    return out


def krippendorff_alpha(units):
    """Nominal Krippendorff's alpha; every unit has the same number of ratings."""
    m = len(units[0])
    values = sorted({v for u in units for v in u}, key=str)
    n_total = len(units) * m
    counts = {v: sum(u.count(v) for u in units) for v in values}
    d_o = 0.0
    for u in units:
        disagree = sum(1 for x, y in itertools.permutations(u, 2) if x != y)
        d_o += disagree / (m - 1)
    d_o /= n_total
    d_e = sum(counts[a] * counts[b] for a in values for b in values if a != b) / (n_total * (n_total - 1))
    return 1.0 if d_e == 0 else 1 - d_o / d_e


def pct(pair):
    h, n = pair
    return f"{h}/{n} = {100 * h / n:.0f}%" if n else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--briefs", action="store_true", help="print one line per brief")
    ap.add_argument("--json-out")
    args = ap.parse_args()
    if not verify_hash():
        print("ANSWER KEY HASH MISMATCH: tests/benchmark/answer_key.json changed", file=sys.stderr)
        return 2
    rows = run()
    sr = split_rates(rows)
    print("Answer key hash verified (SHA-256 0797b657...).")
    for part in ("tuning", "held_out", "all"):
        n = len([r for r in rows if (part == "all" or r["held_out"] == (part == "held_out"))])
        print(f"\n{part} ({n} briefs)")
        print(f"  {'layer':10} {'top-1 hit rate':22} acceptable rate")
        for layer in LAYERS + ("all",):
            c = sr[part][layer]
            print(f"  {layer:10} {pct(c['top1']):22} {pct(c['acceptable'])}")
    ag = agreement()
    print("\nAgreement between the 3 labeller personas on the best pick")
    print(f"  {'layer':10} {'pairwise':10} {'all three':10} alpha")
    for layer in LAYERS + ("all",):
        a = ag[layer]
        print(f"  {layer:10} {100 * a['pairwise']:.0f}%{'':6} {100 * a['unanimous']:.0f}%{'':6} {a['alpha']:.2f}")
    if args.briefs:
        print("\nPer brief (x = pick outside the acceptable set, ~ = acceptable but not best)")
        for r in rows:
            marks = []
            for layer in LAYERS:
                c = r["layers"][layer]
                m = "ok" if c["top1"] else ("~" if c["ok"] else "x")
                marks.append(f"{layer[:2]}:{m}")
            top = sum(1 for c in r["layers"].values() if c["top1"])
            acc = sum(1 for c in r["layers"].values() if c["ok"])
            print(f"  {r['id']} {'H' if r['held_out'] else 'T'} top1 {top}/4 acceptable {acc}/4  {' '.join(marks)}  {r['title']}")
            for layer in LAYERS:
                c = r["layers"][layer]
                if not c["ok"]:
                    print(f"        {layer}: engine {c['pick']}, key best {c['best']} acceptable {c['acceptable']}")
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump({"rates": sr, "agreement": ag, "briefs": rows}, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
