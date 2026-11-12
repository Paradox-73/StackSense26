"""Regenerates report assets from the engine:
  report/samples/<preset>.md   full Markdown recommendation for every preset
  report/sources.md            register of every URL cited in data/ (KB, rules, questions, glossary)
  report/pairs.md              one-answer-apart project pairs
  report/inputs_appendix.md    Appendix B: question catalogue, what each answer changes, derived quantities
  report/report.md             the generated blocks between <!-- BEGIN x --> and <!-- END x --> markers:
                               test counts, knowledge-base evidence table, sample gallery, pairs, benchmark table

    python tools/build_assets.py            # rewrite everything
    python tools/build_assets.py --check    # change nothing; exit 1 and list files that differ
Screenshots are separate: python tools/capture_screenshots.py (needs requirements-dev.txt)
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from engine import recommend  # noqa: E402
from engine.export import to_markdown  # noqa: E402
from engine.kb import LAYERS, load_glossary, load_kb, load_presets, load_questions  # noqa: E402
from engine.profile import TIER_LABELS  # noqa: E402
from engine.scoring import REGULATED_SOURCES  # noqa: E402

# Appendix D's evidence table: the hosts the six public scenarios pick or rank second, then their two database picks.
EVIDENCE_ROWS = [("hosting", i) for i in ("netlify", "cloudflare", "digitalocean", "gcp_cloud_run", "flyio", "aws_ecs",
                                          "aws_lambda", "azure_apps")] + [("database", "postgres"), ("database", "sqlserver")]


def evidence_block() -> str:
    """The knowledge-base facts behind the hard filters for EVIDENCE_ROWS, with the vendor pages they come from. The
    compliance filter checks the host, not a database it manages (engine/scoring.py), so database rows say 'host'."""
    kb = load_kb()
    yes = lambda b: "yes" if b else "no"
    out = ["The table prints the knowledge-base facts for the hosting options that the six public scenarios pick or rank second, "
           "and for their two database picks; `tools/build_assets.py` generates it from `data/kb/`. SLA is the highest uptime that "
           "the vendor's SLA page commits to. India and EU mark a region that meets a data-residency rule. A price in the BAA column "
           "is the least a month at which the vendor signs one. Ops is the operations-burden score from Appendix C, where 5 means "
           f"the least work. Cost is the monthly band at the scale tier {TIER_LABELS[2]}, for the app alone on a host and for the "
           "managed service on a database. A managed database takes the SLA, regions and attestations of the host's service, so "
           "those cells read host. The source column gives the vendor's compliance and SLA pages, or the database's documentation; "
           "`report/sources.md` lists every other source.", "",
           "| Option | SLA | India | EU | HIPAA BAA | PCI DSS | ISO 27001 | Ops | Cost a month | Source |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for layer, kid in EVIDENCE_ROWS:
        it = next(x for x in kb[layer] if x["id"] == kid)
        lo, hi = it["cost_usd"][2]
        if layer == "database":
            cells, urls = ["host"] * 6, it["sources"][:1]
        else:
            c, sla = it["compliance"], it.get("sla")
            regions = it.get("residency_regions", it["regions"])  # the lookup the residency filter uses
            baa = (f"from ${c['hipaa_min_usd']:,}" if c.get("hipaa_min_usd") else "yes") if c["hipaa"] else "no"
            cells = [f"{sla['percent']:g}%" if sla else "none", yes("india" in regions), yes("europe" in regions), baa,
                     yes(c["pci"]), yes(c["iso27001"])]
            urls = c["maturity_sources"][:1] + ([sla["source"]] if sla else [])
        out.append(f"| {it['name']} | " + " | ".join(cells) + f" | {it['scores']['ops']}/5 | ${lo:,}–${hi:,} | "
                   + "<br>".join(f"<{u}>" for u in urls) + " |")
    return "\n".join(out)


def bench_block() -> str:
    import bench
    rows = bench.run()
    sr = bench.split_rates(rows)
    ag = bench.agreement()["all"]
    n_t = sum(1 for r in rows if not r["held_out"])
    n_h = len(rows) - n_t
    pc = lambda c: f"{100 * c[0] / c[1]:.0f}% ({c[0]}/{c[1]})"
    out = ["- **Benchmark against an answer key** (`python tools/bench.py`, `tests/test_benchmark.py`): 40 project briefs, each with a best pick "
           "and an acceptable set per layer, from an answer key written before measurement, with sources. The labels were written by a language model playing three architect "
           "personas (a startup CTO, an enterprise architect, a cloud engineer), blind to the engine, not by human raters. A pick counts as acceptable "
           f"if at least 2 of 3 personas accept it. The personas agree on the best pick {100 * ag['pairwise']:.0f}% of the time (Krippendorff alpha {ag['alpha']:.2f}, "
           "a measure of agreement between the personas, not between human raters). "
           f"{n_h} briefs were held out and never used for tuning.", "",
           "| Layer | Tuning top-1 | Tuning acceptable | Held-out top-1 | Held-out acceptable |", "|---|---|---|---|---|"]
    for layer in bench.LAYERS + ("all",):
        t, h = sr["tuning"][layer], sr["held_out"][layer]
        out.append(f"| {layer if layer != 'all' else 'All layers'} | {pc(t['top1'])} | {pc(t['acceptable'])} | {pc(h['top1'])} | {pc(h['acceptable'])} |")
    base = json.loads((ROOT / "tests" / "benchmark" / "baseline_before_fixes.json").read_text(encoding="utf-8"))["held_out"]["all"]
    out += ["", f"Before the general rule fixes made on the {n_t} tuning briefs, the held-out briefs scored {pc(base['top1'])} top-1 and "
            f"{pc(base['acceptable'])} acceptable. The picks outside the acceptable set are listed by `python tools/bench.py --briefs`."]
    return "\n".join(out)


CATEGORIES = {
    "Scoring, constraints and cost": ["test_engine", "test_deployment_models", "test_data_fit", "test_team_skills", "test_cloud_preference", "test_diversity",
                                      "test_app_defaults", "test_cost_model", "test_cost_in_tier", "test_static_and_budget", "test_special_workloads",
                                      "test_split_hosting", "test_services_lint", "test_runs_here", "test_kb_facts", "test_requirements_bind",
                                      "test_hosting_limits", "test_budget_search", "test_skills_ties",
                                      "test_entry_plans", "test_hiring_pool", "test_search_shape", "test_sqlite_traffic",
                                      "test_timescale_and_regions", "test_buildpack_languages", "test_ml_streaming",
                                      "test_mobile_primary", "test_platform_skills", "test_zero_data", "test_background_work", "test_concurrency",
                                      "test_system_of_record", "test_tenancy_sso", "test_vendor_sla", "test_research_refresh",
                                      "test_cloud_skill_tie", "test_data_estimate", "test_side_store_cost", "test_zero_budget",
                                      "test_stored_files", "test_static_site_rules", "test_service_constraints",
                                      "test_one_product_per_service", "test_supporting_explained", "test_self_run_db_cost"],
    "Explanations match the engine": ["test_explanations", "test_reasoning_text", "test_switch_reasons", "test_whynot", "test_adr",
                                      "test_faithfulness", "test_robustness", "test_wording", "test_baseline_grading", "test_redteam_cost",
                                      "test_redteam_text", "test_paragraph_wording", "test_scenario_wording"],
    "Inputs, edge cases and warnings": ["test_standard", "test_edge_cases", "test_input_validation", "test_input_questions", "test_questions", "test_next",
                                        "test_sensitivity", "test_defaults_used", "test_scale_warnings", "test_question_influence", "test_question_wording"],
    "Stability and properties": ["test_stability", "test_invariants", "test_scenarios"],
    "Language-model layer (checks and fallbacks)": ["test_llm_off", "test_llm", "test_brief", "test_brief_audit", "test_brief_regression", "test_summary", "test_whatif", "test_llm_baseline"],
    "Accuracy against the answer key": ["test_benchmark"],
    "App, packaging and documents": ["test_scenario_api", "test_api", "test_launcher", "test_no_network", "test_share", "test_links", "test_docs",
                                     "test_package", "test_ci", "test_openapi", "test_demo_script"],
}


def test_counts() -> dict[str, int]:
    """Tests per file, from pytest's own collection (parametrised tests count once per case)."""
    import subprocess
    py = next((str(p) for p in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python") if p.exists()), sys.executable)
    out = subprocess.run([py, "-m", "pytest", "--collect-only", "-q"], cwd=ROOT, capture_output=True, text=True).stdout
    counts: dict[str, int] = {}
    for ln in out.splitlines():
        m = re.match(r"tests[/\\](test_\w+)\.py::", ln)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def validation_files() -> tuple[str, str]:
    """(table for the report grouped by category, full per-file table for report/validation.md)."""
    counts = test_counts()
    total = sum(counts.values())
    known = {f for fs in CATEGORIES.values() for f in fs}
    unfiled = sorted(set(counts) - known)
    if unfiled:
        raise SystemExit(f"tools/build_assets.py CATEGORIES has no entry for: {', '.join(unfiled)}")
    rows = ["| What is checked | Tests |", "|---|---|"]
    rows += [f"| {cat} | {sum(counts.get(f, 0) for f in fs)} |" for cat, fs in CATEGORIES.items()]
    rows.append(f"| **All** | **{total}** |")
    full = ["# Validation: tests by file", "", f"`pytest` collects {total} tests (`python -m pytest --collect-only -q`). Generated by `python tools/build_assets.py`.", "",
            "| File | Tests | What it checks |", "|---|---|---|"]
    for cat, fs in CATEGORIES.items():
        for f in fs:
            if counts.get(f):
                doc = ast.get_docstring(ast.parse((ROOT / "tests" / f"{f}.py").read_text(encoding="utf-8"))) or ""
                full.append(f"| `{f}.py` ({cat}) | {counts[f]} | {doc.splitlines()[0] if doc else ''} |")
    full += ["", f"Total: {total} tests."]
    return "\n".join(rows), "\n".join(full) + "\n"

DEMO_CASES = [("Case 1", "hipaa_telehealth"), ("Case 2", "india_ecommerce_scale")]


def page_answers(preset: dict) -> dict:
    """The answers the page sends for an example: every answer it states that is a question (app.js loadProject)."""
    defaults = {f["key"]: f.get("default") for s in load_questions()["steps"] for f in s["fields"]}
    return {k: v for k, v in preset["input"].items() if k in defaults}


def _group_inr(n: float) -> str:
    """Indian digit grouping: 588480 -> 5,88,480."""
    s = str(int(n))
    head, tail, parts = s[:-3], s[-3:], []
    if not head:
        return tail
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + parts + [tail])


def demo_block(results: dict) -> str:
    """What the page shows for the two preset cases in the video, from the engine called with the page's own answers.
    tests/test_demo_script.py recomputes every cell independently."""
    presets = {p["id"]: p for p in load_presets()}
    out = ["| Case | Example to click | Frontend | Backend | Database | Hosting | Cost shown | Budget line shown |", "|---|---|---|---|---|---|---|---|"]
    for label, pid in DEMO_CASES:
        r = recommend(page_answers(presets[pid]), with_counterfactuals=False)
        picks = [re.sub(r" \(.*\)$", "", r["stack"][l]["pick"]["name"]) for l in LAYERS]
        c, inr = r["cost"], r["profile"]["currency"] == "INR"
        cost = f"₹{_group_inr(c['total_low_inr'])}–₹{_group_inr(c['total_high_inr'])}" if inr else f"${c['total_low']:,.0f}–${c['total_high']:,.0f}"
        status = {"within": "within budget", "stretch": "stretches the budget", "over": "over budget"}[c["status"]]
        budget = f"₹{_group_inr(r['profile']['budget_monthly'])}" if inr else f"${r['profile']['budget_monthly']:,.0f}"
        out.append(f"| {label} | {presets[pid]['name']} | " + " | ".join(picks) + f" | {cost} | {status} · {budget} |")
    return "\n".join(out)


def replace_block(text: str, name: str, body: str) -> str:
    pat = re.compile(rf"(<!-- BEGIN {name} -->\n).*?(\n?<!-- END {name} -->)", re.S)
    if not pat.search(text):
        raise SystemExit(f"report.md has no BEGIN/END markers for {name}")
    return pat.sub(lambda m: m.group(1) + body + "\n" + m.group(2).lstrip("\n"), text)


def build() -> dict[Path, str]:
    """Every generated file as {path: text}."""
    import build_pairs
    files: dict[Path, str] = {}
    results = {}
    for p in load_presets():
        results[p["id"]] = recommend(p["input"])
        files[ROOT / "report" / "samples" / f"{p['id']}.md"] = to_markdown(results[p["id"]])
    kb = load_kb()
    refs = [(f"{l}: {it['name']}", s) for l in LAYERS for it in kb[l] for s in it["sources"]]
    refs += [(f"rule {r['id']}", r["source"]) for r in kb["rules"] if r.get("source")]
    refs += [(f"{l}: {it['name']} (compliance maturity)", s) for l in LAYERS for it in kb[l]
             for s in it.get("compliance", {}).get("maturity_sources", [])]
    refs += [("criterion: compliance maturity for regulated data at scale", s) for s in REGULATED_SOURCES]
    refs += [(f"input: {f['key']}", s) for st in load_questions()["steps"] for f in st["fields"] for s in f.get("sources", [])]
    refs += [(f"glossary: {g['term']}", g["source"]) for g in load_glossary()["terms"].values()]
    seen, lines = set(), ["# Source register", "",
                          "Every URL cited by the knowledge base, compatibility rules, questionnaire and glossary (generated from `data/`).", ""]
    for who, s in refs:
        if s not in seen:
            seen.add(s)
            lines.append(f"- {who}: {s}")
    files[ROOT / "report" / "sources.md"] = "\n".join(lines) + "\n"
    import inputs_appendix
    files[ROOT / "report" / "inputs_appendix.md"] = inputs_appendix.appendix_markdown()
    pairs = build_pairs.pairs_markdown()
    files[ROOT / "report" / "pairs.md"] = "# One answer apart\n\n" + pairs
    rp = ROOT / "report" / "report.md"
    raw = rp.read_bytes().decode("utf-8")
    nl = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")
    vtable, vfull = validation_files()
    files[ROOT / "report" / "validation.md"] = vfull
    kg, kp = build_pairs.KEY_GALLERY, build_pairs.KEY_PAIRS
    for name, body in (("validation", vtable), ("evidence", evidence_block()),
                       ("gallery", build_pairs.gallery_markdown(0, kg).rstrip()), ("gallery_more", build_pairs.gallery_markdown(kg).rstrip()),
                       ("pairs", build_pairs.pairs_markdown(0, kp).rstrip()), ("pairs_more", build_pairs.pairs_markdown(kp).rstrip()),
                       ("bench", bench_block())):
        text = replace_block(text, name, body)
    files[rp] = text.replace("\n", nl)
    dp = ROOT / "report" / "demo_script.md"
    draw = dp.read_bytes().decode("utf-8")
    dnl = "\r\n" if "\r\n" in draw else "\n"
    files[dp] = replace_block(draw.replace("\r\n", "\n"), "stacks", demo_block(results)).replace("\n", dnl)
    return files


def _norm(t):
    return None if t is None else t.replace("\r\n", "\n")


def main() -> int:
    check = "--check" in sys.argv
    files = build()
    stale = []
    for path, text in files.items():
        old = path.read_bytes().decode("utf-8") if path.exists() else None
        if _norm(old) != _norm(text):
            stale.append(path)
            if not check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(text.encode("utf-8"))
    if check:
        for p in stale:
            print("differs:", p.relative_to(ROOT))
        print(f"{len(files)} generated files checked, {len(stale)} differ")
        return 1 if stale else 0
    print(f"wrote {len(files)} generated files ({len(stale)} changed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
