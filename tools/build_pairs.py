"""One-answer-apart project pairs and the sample gallery text, written from the engine's own output.

    python tools/build_pairs.py          # prints the pairs and the gallery captions

tools/build_assets.py puts the same text into report/report.md (section 5) and report/pairs.md.
"""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import recommend  # noqa: E402
from engine.recommender import switch_reasons  # noqa: E402
from engine.kb import LAYERS, load_presets  # noqa: E402

LAYER_LABEL = {"frontend": "Frontend", "backend": "Backend", "database": "Database", "hosting": "Hosting"}

# (title, base preset, answers to change {key: new value, None = leave out})
PAIRS = [
    ("Startup SaaS MVP, then add HIPAA", "startup_mvp", {"compliance": ["gdpr", "hipaa"]}),
    ("IoT telemetry, 40,000 devices vs 5 million", "iot_telemetry", {"dau": 5_000_000, "peak_rps": None}),
    ("Internal tool, own servers vs cloud", "internal_tool", {"deployment": "cloud"}),
]

GALLERY = ["startup_mvp", "hipaa_telehealth"]  # the two sample screenshots of tools/capture_screenshots.py
KEY_GALLERY = 1  # report.md blocks: the first sample is block gallery, the rest gallery_more
KEY_PAIRS = 1    # report.md blocks: the first pair is block pairs, the rest pairs_more


def _preset(pid: str) -> dict:
    return next(p for p in load_presets() if p["id"] == pid)


def _run(inp: dict) -> dict:
    return recommend(inp, with_counterfactuals=False)


def _picks(r: dict) -> dict:
    return {l: r["stack"][l]["pick"]["name"] for l in LAYERS}


def _cost(r: dict) -> str:
    c = r["cost"]
    lo, hi = round(c["total_low"]), round(c["total_high"])
    return f"${lo:,}" if lo == hi else f"${lo:,}–${hi:,}"


def _value(v) -> str:
    if isinstance(v, list):
        return ", ".join(map(str, v))
    return f"{v:,}" if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v)


def pair_results() -> list[dict]:
    out = []
    for title, pid, edit in PAIRS:
        base = deepcopy(_preset(pid)["input"])
        changed = deepcopy(base)
        for k, v in edit.items():
            if v is None:
                changed.pop(k, None)
            else:
                changed[k] = v
        a, b = _run(base), _run(changed)
        why = switch_reasons(base, changed)
        out.append({"title": title, "preset": pid, "why": {l: w["why"] for l, w in why.items()},
                    "edit": {k: (base.get(k), v) for k, v in edit.items() if v is not None},
                    "before": _picks(a), "after": _picks(b), "cost_before": _cost(a), "cost_after": _cost(b)})
    return out


def pairs_markdown(start: int = 0, stop: int | None = None) -> str:
    """The pairs pair_results()[start:stop] as Markdown."""
    lines = []
    for p in pair_results()[start:stop]:
        edits = "; ".join(f"`{k}`: {_value(a)} → {_value(b)}" for k, (a, b) in p["edit"].items())
        lines += [f"**{p['title']}** (preset `{p['preset']}`; changed answer: {edits})", "",
                  "| Layer | Before | After |", "|---|---|---|"]
        for l in LAYERS:
            mark = "**" if p["before"][l] != p["after"][l] else ""
            lines.append(f"| {LAYER_LABEL[l]} | {p['before'][l]} | {mark}{p['after'][l]}{mark} |")
        lines += [f"| Est. cost / month | {p['cost_before']} | {p['cost_after']} |", ""]
        lines += [f"- {LAYER_LABEL[l]}: {w}" for l, w in p["why"].items() if w] + [""]
    return "\n".join(lines).rstrip() + "\n"


def _first_reason(r: dict, layer: str) -> str:
    why = r["stack"][layer]["explanation"]["why"]
    return why[0].split(" - ")[0].rstrip(".") if why else ""


def gallery_markdown(start: int = 0, stop: int | None = None) -> str:
    """The samples GALLERY[start:stop] as Markdown."""
    lines = []
    for pid in GALLERY[start:stop]:
        p = _preset(pid)
        r = _run(p["input"])
        picks = " + ".join(_picks(r)[l] for l in LAYERS)
        name = p.get("name") or p["input"].get("project_name") or pid
        lines += [f"![{name}](screenshots/gallery/{pid}.png)", "",
                  f"**{name}.** {picks}, about {_cost(r)} a month.",
                  f"Why it fits: backend, {_first_reason(r, 'backend').lower()}; hosting, {_first_reason(r, 'hosting').lower()}.", ""]
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(pairs_markdown())
    print(gallery_markdown())
