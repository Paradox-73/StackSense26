"""Build the report from the code: recompute every count, check the documents against them, print the PDF.

    python tools/build_report.py --facts      # write report/facts.json (every count the documents quote)
    python tools/build_report.py --sync       # rewrite quoted counts that disagree with the facts, then write facts.json
    python tools/build_report.py --check      # exit 1 if facts.json is stale or README.md / report/report.md quote a wrong count
    python tools/build_report.py --draft      # facts, check, then report/StackSense_Report.pdf; "TODO" placeholders allowed
    python tools/build_report.py              # final build: fails on any "TODO" or missing image

The PDF is made by turning report/report.md (plus the generated appendices) into HTML with markdown-it-py and
printing it with Chrome headless; a second pass reads each heading's page with pypdf and fills the contents and
the page numbers in the criteria map. Screenshots come from tools/capture_screenshots.py, tables from
tools/build_assets.py, and the LLM-only baseline table (section 6.2) from benchmark/llm_baseline.json when that file exists.
Build-only packages: requirements-dev.txt. Set CHROME to a browser path if Chrome is not found.
"""
from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from engine.kb import LAYERS, load_glossary, load_kb, load_presets, load_questions  # noqa: E402
from engine.kb import CRITERION_LABELS  # noqa: E402

REPORT = ROOT / "report"
PDF = REPORT / "StackSense_Report.pdf"
CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


# --------------------------------------------------------------------------------------------- facts
def _test_python() -> str:
    if os.environ.get("TEST_PYTHON"):  # a Python with the app's packages, when this script runs under another one
        return os.environ["TEST_PYTHON"]
    for p in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if p.exists():
            return str(p)
    return sys.executable


def _count_tests() -> int:
    out = subprocess.run([_test_python(), "-m", "pytest", "--collect-only", "-q"], cwd=ROOT, capture_output=True, text=True).stdout
    m = re.search(r"(\d+) tests? collected", out) or re.search(r"^(\d+) tests", out, re.M)
    if not m:
        raise SystemExit("could not count tests:\n" + out[-500:])
    return int(m.group(1))


def _warning_codes() -> tuple[int, int]:
    pat = re.compile(r'_warn\(\s*"([A-Z][A-Z0-9_]+)"')
    every, conflicts = set(), set()
    for f in (ROOT / "engine").glob("*.py"):
        found = set(pat.findall(f.read_text(encoding="utf-8")))
        every |= found
        if f.name == "conflicts.py":
            conflicts = found
    return len(every), len(conflicts)


def _quick_questions() -> int:
    js = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
    block = re.search(r"const QUICK = \[(.*?)\n\];", js, re.S).group(1)
    return len(re.findall(r"\{ id: \"", block))


def _sources() -> int:
    return sum(1 for ln in (REPORT / "sources.md").read_text(encoding="utf-8").splitlines() if ln.startswith("- "))


def _llm_facts(bench) -> dict:
    """The LLM-only baseline's rates (from benchmark/llm_baseline.json) as facts; None when the file is absent."""
    path = ROOT / "benchmark" / "llm_baseline.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    done = list(saved.get("briefs", {}).values())
    if not done:
        return {k: None for k in ("llm_top1_pct", "llm_acceptable_pct", "llm_top1_picks", "llm_acceptable_picks", "llm_break_briefs")}
    r = bench.rates(done)["all"]
    pct = lambda c: round(100 * c[0] / c[1])
    return {"llm_top1_pct": pct(r["top1"]), "llm_acceptable_pct": pct(r["acceptable"]),
            "llm_top1_picks": r["top1"][1], "llm_acceptable_picks": r["acceptable"][1],
            "llm_break_briefs": (saved.get("metrics") or {}).get("llm_breaks", {}).get("briefs")}


def compute_facts() -> dict:
    import bench
    kb = load_kb()
    rows = bench.run()
    sr = bench.split_rates(rows)
    pct = lambda c: round(100 * c[0] / c[1])
    both = lambda k: round(100 * (sr["tuning"]["all"][k][0] + sr["held_out"]["all"][k][0]) / (sr["tuning"]["all"][k][1] + sr["held_out"]["all"][k][1]))
    n_all, n_conf = _warning_codes()
    q = load_questions()
    fuzz_path = REPORT / "fuzz_summary.json"
    fuzz = json.loads(fuzz_path.read_text(encoding="utf-8")) if fuzz_path.exists() else {}
    flip = fuzz.get("violations", {}).get("no_flip_back")
    allr = sr["all"]["all"]
    llm = _llm_facts(bench)
    facts = {
        "technologies": sum(len(kb[l]) for l in LAYERS),
        "frontends": len(kb["frontend"]), "backends": len(kb["backend"]),
        "databases": len(kb["database"]), "hosting_platforms": len(kb["hosting"]),
        "rules": len(kb["rules"]),
        "criteria": len(CRITERION_LABELS),
        "questions": sum(len(s["fields"]) for s in q["steps"]),
        "question_groups": len(q["steps"]),
        "quick_questions": _quick_questions(),
        "presets": len(load_presets()),
        "scenario_fixtures": len(list((ROOT / "tests" / "scenarios").glob("*.json"))),
        "glossary_terms": len(load_glossary()["terms"]),
        "source_urls": _sources(),
        "tests": _count_tests(),
        "warning_codes": n_all,
        "conflict_warning_codes": n_conf,
        "benchmark_briefs": len(rows),
        "benchmark_held_out": sum(1 for r in rows if r["held_out"]),
        "benchmark_top1_pct": both("top1"),
        "benchmark_acceptable_pct": both("acceptable"),
        "benchmark_top1_hits": allr["top1"][0], "benchmark_top1_picks": allr["top1"][1],
        "benchmark_acceptable_hits": allr["acceptable"][0], "benchmark_acceptable_picks": allr["acceptable"][1],
        **llm,
        "benchmark_held_out_top1_pct": pct(sr["held_out"]["all"]["top1"]),
        "benchmark_held_out_acceptable_pct": pct(sr["held_out"]["all"]["acceptable"]),
        "fuzz_projects": fuzz.get("projects"),
        "fuzz_rules": fuzz.get("rules"),
        "fuzz_seed": fuzz.get("seed"),
        "fuzz_growth_projects": fuzz.get("growth_projects"),
        "fuzz_clean_rules": sum(1 for v in fuzz.get("violations", {}).values() if v == 0) if fuzz else None,
        "fuzz_flip_back": flip,
    }
    return facts


def facts_text(facts: dict) -> str:
    return json.dumps(facts, indent=1, sort_keys=True) + "\n"


# --------------------------------------------------------------------------------------------- claims in the documents
# Every number followed by one of these phrases must equal the fact. A document with no match for a phrase is fine.
CLAIMS = [
    ("technologies", [r"(\d+) technologies"]),
    ("frontends", [r"(\d+) frontends"]),
    ("backends", [r"(\d+) backends"]),
    ("databases", [r"(\d+) databases"]),
    ("hosting_platforms", [r"(\d+) hosting platforms"]),
    ("rules", [r"(\d+) compatibility rules", r"(\d+) rules\b"]),
    ("criteria", [r"(\d+) criteria"]),
    ("questions", [r"(\d+) questions(?! in quick| are| a new)", r"(\d+)-question"]),
    ("quick_questions", [r"(\d+) quick questions", r"\((\d+) in quick mode\)"]),
    ("presets", [r"(\d+) (?:presets|ready-made scenarios|built-in examples)"]),
    ("glossary_terms", [r"(\d+) glossary terms", r"\((\d+) terms\)"]),
    ("source_urls", [r"(\d+) cited URLs", r"register of (\d+) URLs", r"(\d+) URLs"]),
    ("tests", [r"(\d+) (?:pytest )?tests\b(?! with| in)", r"`(\d+) passed in"]),
    ("warning_codes", [r"(\d+) (?:distinct )?warning codes"]),
    ("conflict_warning_codes", [r"(\d+) (?:cross-field|contradiction) checks"]),
    ("scenario_fixtures", [r"(\d+) scenario fixtures"]),
    ("benchmark_briefs", [r"(\d+) project briefs", r"has (\d+) briefs"]),
    ("benchmark_acceptable_pct", [r"(\d+)% of the 160 layer picks", r"and (\d+)% acceptable \(\d+ of all", r"against the engine's \d+% and (\d+)%"]),
    ("benchmark_top1_pct", [r"Result: (\d+)% top-1", r"against the engine's (\d+)% and \d+%"]),
    ("benchmark_top1_hits", [r"\((\d+) of the \d+ layer picks that have a best pick"]),
    ("benchmark_top1_picks", [r"\(\d+ of the (\d+) layer picks that have a best pick"]),
    ("benchmark_acceptable_hits", [r"acceptable \((\d+) of all \d+ layer picks"]),
    ("benchmark_acceptable_picks", [r"acceptable \(\d+ of all (\d+) layer picks"]),
    ("llm_top1_pct", [r"\(LLM (\d+)% top-1 on \d+ picks"]),
    ("llm_top1_picks", [r"\(LLM \d+% top-1 on (\d+) picks"]),
    ("llm_acceptable_pct", [r"(\d+)% acceptable on \d+, against"]),
    ("llm_acceptable_picks", [r"\d+% acceptable on (\d+), against"]),
    ("llm_break_briefs", [r"breaks a hard requirement in (\d+) of the 40 briefs"]),
    ("fuzz_projects", [r"([\d,]{6,}) (?:seeded )?random projects"]),
    ("fuzz_growth_projects", [r"([\d,]+) (?:random )?growth (?:walks|profiles)"]),
    ("fuzz_flip_back", [r"(\d+) of (?:the )?1,000 (?:random )?growth", r"violated in (\d+) of them"]),
    ("fuzz_clean_rules", [r"violations of (?:the )?(\d+) (?:hard-constraint|properties)"]),
    ("fuzz_rules", [r"checks (\d+) properties", r"(\d+) must-hold rules"]),
]
DOCS = [d for d in (ROOT / "README.md", REPORT / "report.md", REPORT / "demo_script.md") if d.exists()]  # the demo script is not in the zip


def doc_problems(facts: dict) -> list[str]:
    bad = []
    for doc in DOCS:
        text = doc.read_text(encoding="utf-8")
        for fact, pats in CLAIMS:
            for pat in pats:
                for m in re.finditer(pat, text):
                    if facts[fact] is not None and int(m.group(1).replace(",", "")) != facts[fact]:
                        line = text[: m.start()].count("\n") + 1
                        bad.append(f"{doc.relative_to(ROOT)}:{line}: says {m.group(0)!r}, but {fact} = {facts[fact]}")
    return bad


def sync_docs(facts: dict) -> list[str]:
    """Rewrite every quoted count that disagrees with the facts (README.md, report/report.md, report/demo_script.md)."""
    changed = []
    for doc in DOCS:
        raw = doc.read_bytes().decode("utf-8")
        text = raw
        for fact, pats in CLAIMS:
            for pat in pats:
                def fix(m):
                    if facts[fact] is None:
                        return m.group(0)
                    old = m.group(1)
                    want = f"{facts[fact]:,}" if "," in old else str(facts[fact])
                    return m.group(0)[: m.start(1) - m.start()] + want + m.group(0)[m.end(1) - m.start():]
                text = re.sub(pat, fix, text)
        if text != raw:
            doc.write_bytes(text.encode("utf-8"))
            changed.append(str(doc.relative_to(ROOT)))
    return changed


def check() -> int:
    facts = compute_facts()
    problems = doc_problems(facts)
    fp = REPORT / "facts.json"
    if not fp.exists() or fp.read_text(encoding="utf-8").replace("\r\n", "\n") != facts_text(facts):
        problems.append("report/facts.json is out of date: run python tools/build_report.py --facts")
    for p in problems:
        print(p)
    print(f"{len(problems)} problems")
    return 1 if problems else 0


# --------------------------------------------------------------------------------------------- HTML
def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"<[^>]+>", "", text).lower()).strip("-")


def _render(md_text: str) -> str:
    from markdown_it import MarkdownIt
    md = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
    out = md.render(md_text)
    # A long inline path may break only after a slash, never in the middle of a name.
    return re.sub(r"<code>([^<\n]*)</code>", lambda m: "<code>" + m.group(1).replace("/", "/<wbr>") + "</code>", out)


def _strip_front_matter(t: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", t, flags=re.S)


def _figures(html_text: str, fig_counter: list[int], missing: list[str]) -> str:
    """Turn a paragraph that holds only an image into a numbered figure."""
    def repl(m):
        alt, src = html.unescape(m.group(2)), m.group(1)
        path = (REPORT / src).resolve()
        if not path.exists():
            missing.append(src)
        fig_counter[0] += 1
        # Judges read the PDF and do not run code, so a figure carries no 'Reproduce' command; the appendix has one how-to paragraph.
        cap = f'<figcaption><b>Figure {fig_counter[0]}.</b> {html.escape(alt)}</figcaption>'
        cls = ' class="gal"' if src.startswith("screenshots/gallery/") else ""
        return f'<figure{cls}><img src="{html.escape(src)}" alt="{html.escape(alt)}">{cap}</figure>'

    return re.sub(r'<p><img src="([^"]+)" alt="([^"]*)"[^>]*></p>', lambda m: repl(m), html_text)


def _heading_ids(html_text: str) -> tuple[str, list[tuple[int, str, str]]]:
    heads = []

    def repl(m):
        lvl, inner = int(m.group(1)), m.group(2)
        sid = slug(inner)
        heads.append((lvl, re.sub(r"<[^>]+>", "", html.unescape(inner)), sid))
        return f'<h{lvl} id="{sid}">{inner}</h{lvl}>'

    return re.sub(r"<h([1-3])>(.*?)</h\1>", repl, html_text), heads


def _appendix_a() -> str:
    t = (REPORT / "samples" / "hipaa_telehealth.md").read_text(encoding="utf-8")
    # Keep the page budget: only the hosting layer prints its score table, alternatives and exclusions in full.
    t = re.sub(r"^\*\*Inputs that drove this score\*\*.*?(?=^### Hosting|^## )", "", t, flags=re.M | re.S)
    t = re.sub(r"^## Sources\n.*\Z", "", t, flags=re.M | re.S).rstrip() + "\n"  # the URL list is in report/sources.md
    body = re.sub(r"^(#{1,4}) ", lambda m: "#" * min(len(m.group(1)) + 2, 6) + " ", t, flags=re.M)  # demote every heading by two levels
    return ("## Appendix A. One recommendation in detail: HIPAA telehealth\n\nThe output for the `hipaa_telehealth` example, as "
            "`python cli.py --preset hipaa_telehealth` and the Markdown export print it. To fit the page budget, the frontend, backend and "
            "database layers stop after the runner-up comparison; the hosting layer is printed in full. The complete text is in "
            "`report/samples/hipaa_telehealth.md`. The source URLs behind the scores are in `report/sources.md`, not printed here.\n\n<div class=\"appx\">\n\n" + body + "\n\n</div>\n")


def _agreement_sentence(rates: dict, pct) -> str:
    """How the two rows compare against the key, worded from the numbers (top-1 and acceptable can point different ways)."""
    def frac(r):
        return r[0] / r[1]
    e, l = rates["e"], rates["l"]
    acc = f"engine {pct(e['acceptable'])}, LLM {pct(l['acceptable'])} acceptable"
    top = f"engine {pct(e['top1'])}, LLM {pct(l['top1'])} top-1"
    if frac(l["acceptable"]) > frac(e["acceptable"]):
        return f"The LLM agrees with the key slightly more often than the engine does ({acc})."
    if frac(l["acceptable"]) == frac(e["acceptable"]):
        return f"The LLM and the engine are level on acceptable picks ({acc}); on top-1 it is {top}."
    lead = "ahead of" if frac(l["top1"]) > frac(e["top1"]) else "not ahead of"
    return f"The engine's picks are acceptable to the key slightly more often than the LLM's ({acc}); the LLM is {lead} the engine on top-1 ({top})."


def _llm_baseline() -> str:
    """Section 6.2: an LLM-only baseline on the same briefs, read from benchmark/llm_baseline.json (tools/llm_baseline.py).

    The file is optional. Without it, or with no brief answered yet, the section says the baseline has not been run.
    Besides agreement with the key it reports what the rule engine's grade of the model's stacks found (hard-requirement
    breaks, over-budget) and, when benchmark/llm_baseline_repeat.json exists, how often the model repeats itself."""
    import bench
    import llm_baseline
    path = ROOT / "benchmark" / "llm_baseline.json"
    saved = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    done = list(saved.get("briefs", {}).values())
    intro = ("A language model with no rule engine was asked for the four picks of each benchmark brief (`python tools/llm_baseline.py`). "
             "It saw only the brief and the list of technologies in the knowledge base, and its picks are scored with the same rule as the engine's. "
             "Its stacks were then graded by the rule engine, offline, with the same check as the Why-not-this check. "
             "The answer key was itself written by a language model playing three architect personas, and this shared origin likely favours the LLM-only picker in the agreement rows below.")
    if not done:
        return intro + " The baseline has not been run in this build; the comparison appears here once `benchmark/llm_baseline.json` exists."
    ids = {r["id"] for r in done}
    engine_rows = [r for r in bench.run() if r["id"] in ids]
    m = saved.get("metrics") or {}
    graded = m.get("graded", 0)
    n = len(done)
    rep_path = ROOT / "benchmark" / "llm_baseline_repeat.json"
    rep = llm_baseline.repeat_metrics(saved, json.loads(rep_path.read_text(encoding="utf-8")) if rep_path.exists() else None)
    if rep["asked"]:
        repeat_cell = f"{rep['same_stack']}/{rep['asked']} briefs gave the same four picks twice"
    else:
        repeat_cell = "not measured yet"
    lines = [intro, "", f"Both rows cover the same {n} of {len(bench.run())} briefs.", "",
             "| Measure | Rule engine | LLM only |", "|---|---|---|"]
    rates = {name: bench.rates(rows)["all"] for name, rows in (("e", engine_rows), ("l", done))}
    lines.append(f"| Top-1 (the key's best pick) | {bench.pct(rates['e']['top1'])} | {bench.pct(rates['l']['top1'])} |")
    lines.append(f"| Acceptable (2 of 3 personas) | {bench.pct(rates['e']['acceptable'])} | {bench.pct(rates['l']['acceptable'])} |")
    if graded:
        lb, ec = m["llm_breaks"], m["engine_check"]
        lines.append(f"| Briefs with a pick a hard requirement rules out | {ec['breaks']}/{ec['graded']} (graded the same way) | {lb['briefs']}/{graded} |")
        lines.append(f"| Over the stated budget (INR at the engine's fixed rate) | {ec['over_budget']}/{ec['graded']} | {m['llm_over_budget']}/{graded} |")
        lines.append("| Costs, reasons, sources per pick | yes | no |")
    else:
        lines.append("| Briefs with a pick a hard requirement rules out | not graded yet | not graded yet |")
    lines.append(f"| Same four picks when asked twice | deterministic (same answers, same stack) | {repeat_cell} |")
    models = ", ".join(f"`{x}`" for x in saved.get("models_chain", []))
    lines += ["", "Model chain: " + (models or "not recorded") + "."]
    if graded:
        lb, ec = m["llm_breaks"], m["engine_check"]
        cases = "; ".join(f"{c['id']} {c['layer']} = {c['pick']} ({c['reasons'][0].rstrip('.')})" for c in lb["cases"])
        lines += ["", f"The model's stacks that break a hard requirement: {cases}." if cases else "No model stack broke a hard requirement.",
                  "",
                  f"{_agreement_sentence(rates, bench.pct)} "
                  f"It also gives a pick that a hard requirement rules out in {lb['briefs']} of {graded} briefs, "
                  f"which the engine cannot do (grading the engine's own picks the same way finds {ec['breaks']}), and it gives no costs, reasons or sources. "
                  f"{m['llm_over_budget']} of {graded} model stacks are over the stated budget, but the engine's own stack is over budget on {ec['over_budget']} of the same briefs, "
                  f"so those budgets are below the cheapest stack the engine can build; on {m['llm_over_budget_engine_fits']} briefs the model overspends where the engine fits. "
                  "StackSense therefore uses the model only as a reader of free text and an explainer, and lets the rules "
                  "decide; this comparison is an offline experiment (tools/llm_baseline.py), not part of the engine."]
    return "\n".join(lines)


def cover_html(cover: dict) -> str:
    links = "".join(f'<tr><td>{html.escape(k)}</td><td>{html.escape(v)}</td></tr>' for k, v in cover["links"].items())
    return (f'<section class="cover"><div class="kicker">{html.escape(cover["event"])}</div>'
            f'<h1 class="cover-title">{html.escape(cover["title"])}</h1>'
            f'<p class="cover-pitch">{html.escape(cover["pitch"])}</p>'
            f'<table class="cover-meta"><tr><td>Author</td><td>{html.escape(cover["author"])}</td></tr>'
            f'<tr><td>Institute</td><td>{html.escape(cover["institute"])}</td></tr>'
            f'<tr><td>Unstop registered email</td><td>{html.escape(cover.get("email") or "to be added by the entrant")}</td></tr>'
            f'<tr><td>Date</td><td>{html.escape(cover["date"])}</td></tr>{links}</table></section>')


def assemble(pages: dict[str, int], toc_pages: dict[str, int]) -> tuple[str, list[tuple[int, str, str]], list[str], str]:
    cover = json.loads((REPORT / "cover.json").read_text(encoding="utf-8"))
    src = _strip_front_matter((REPORT / "report.md").read_text(encoding="utf-8"))
    src = re.sub(r"^# StackSense\s*\n", "", src, count=1, flags=re.M)  # the cover carries the title
    inputs_md = (REPORT / "inputs_appendix.md").read_text(encoding="utf-8")
    src = src.replace("<!-- INSERT appendix-a -->", _appendix_a())
    src = src.replace("<!-- INSERT appendix-b -->", inputs_md)
    src = src.replace("<!-- INSERT llm-baseline -->", _llm_baseline())
    body = _render(src)
    missing: list[str] = []
    body = _figures(body, [0], missing)
    body, heads = _heading_ids(body)
    body = re.sub(r"\[\[page:([^\]]+)\]\]", lambda m: str(pages.get(m.group(1).strip(), "00")), body)
    toc_items = "".join(
        f'<li class="toc{lvl}"><a href="#{sid}">{html.escape(t)}</a><span class="dots"></span><span class="pg">{toc_pages.get(t, "00")}</span></li>'
        for lvl, t, sid in heads if lvl == 2 and not t.startswith("At a glance"))
    toc = f'<nav class="toc"><h2 class="toc-h">Contents</h2><ol>{toc_items}</ol></nav>'
    body = body.replace("<!-- TOC -->", toc)
    css = (ROOT / "tools" / "report_print.css").read_text(encoding="utf-8")
    fonts = ROOT / "app" / "static" / "fonts"
    ff = "".join(
        f"@font-face{{font-family:'{fam}';font-weight:{w};src:url('{(fonts / f).as_uri()}') format('woff2');}}"
        for fam, f, w in (("Fraunces", "fraunces-latin.woff2", "500 600"), ("Geist", "geist-latin.woff2", "400 700"), ("Geist Mono", "geist-mono-latin.woff2", "400 600")))
    doc = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>StackSense report</title>'
           f'<base href="{REPORT.as_uri()}/"><style>{ff}{css}</style></head><body>{cover_html(cover)}{body}</body></html>')
    return doc, heads, missing, src


def find_chrome() -> str:
    env = os.environ.get("CHROME")
    if env:
        return env
    for c in CHROME_CANDIDATES:
        if os.path.exists(c):
            return c
    import shutil
    for n in ("google-chrome", "chromium", "chrome"):
        if shutil.which(n):
            return shutil.which(n)
    raise SystemExit("No Chrome found; set CHROME to the browser executable.")


def print_pdf(html_text: str, out: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        page = Path(td) / "report.html"
        page.write_text(html_text, encoding="utf-8")
        profile = Path(td) / "profile"
        subprocess.run([find_chrome(), "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profile}",
                        "--virtual-time-budget=20000", f"--print-to-pdf={out}", page.as_uri()],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=240, check=False)
    if not out.exists():
        raise SystemExit("Chrome did not write the PDF")


def heading_pages(pdf: Path, heads, first_body_page: int) -> tuple[dict[str, int], int]:
    from pypdf import PdfReader
    reader = PdfReader(str(pdf))
    texts = [re.sub(r"\s+", " ", (p.extract_text() or "")) for p in reader.pages]
    found: dict[str, int] = {}
    for lvl, title, _sid in heads:
        if lvl > 2:
            continue
        needle = re.sub(r"\s+", " ", title)
        for i in range(first_body_page, len(texts)):
            if needle in texts[i]:
                found[title] = i + 1
                break
    return found, len(reader.pages)


def build_pdf(draft: bool) -> int:
    facts = compute_facts()
    (REPORT / "facts.json").write_text(facts_text(facts), encoding="utf-8")
    problems = doc_problems(facts)
    if problems:
        print("\n".join(problems))
        return 1
    pages: dict[str, int] = {}
    doc, heads, missing, src = assemble(pages, {})
    if missing:
        print("missing images:", ", ".join(sorted(set(missing))))
        return 1
    todo = [m.group(0) for m in re.finditer(r"TODO[^<\"]{0,40}", doc)]
    if todo and not draft:
        print(f"{len(todo)} TODO placeholders left (first: {todo[0]!r}); fix them or build with --draft")
        return 1
    tmp = Path(tempfile.mkdtemp()) / "pass1.pdf"
    print_pdf(doc, tmp)
    pages, n = heading_pages(tmp, heads, 2)
    doc, heads, missing, src = assemble(pages, pages)
    print_pdf(doc, PDF)
    pages2, n2 = heading_pages(PDF, heads, 2)
    if pages2 != pages:  # contents grew a page or moved a heading: one more pass settles it
        doc, heads, missing, src = assemble(pages2, pages2)
        print_pdf(doc, PDF)
        pages2, n2 = heading_pages(PDF, heads, 2)
    print(f"{PDF.relative_to(ROOT)}: {n2} pages, {len(todo)} TODO placeholders{' (draft)' if draft else ''}")
    if not json.loads((REPORT / "cover.json").read_text(encoding="utf-8")).get("email"):
        print("NOTE: report/cover.json has no Unstop registered email; add it and rebuild before submitting")
    leaks = pdf_mentions(PDF)
    for leak in leaks:
        print("PDF names the coding assistant outside the declaration line:", leak)
    return 1 if leaks else 0


def pdf_mentions(pdf: Path) -> list[str]:
    """Places in the built PDF that name the coding assistant other than the one declaration line of section 11."""
    from pypdf import PdfReader
    sys.path.insert(0, str(ROOT / "tools"))
    from package_submission import DECLARATION
    text = " ".join(" ".join((page.extract_text() or "").split()) for page in PdfReader(str(pdf)).pages)
    opening = DECLARATION.lstrip("- ").strip()
    if text.count(opening) != 1:
        return [f"the declaration line appears {text.count(opening)} times, not once"]
    rest = text.replace(opening, " ", 1)
    banned = re.compile("cl" + "aude|anth" + "ropic", re.I)
    return [rest[max(0, m.start() - 40): m.end() + 40] for m in banned.finditer(rest)]


def main() -> int:
    args = sys.argv[1:]
    if "--facts" in args:
        facts = compute_facts()
        (REPORT / "facts.json").write_text(facts_text(facts), encoding="utf-8")
        print(facts_text(facts), end="")
        return 0
    if "--sync" in args:
        facts = compute_facts()
        (REPORT / "facts.json").write_text(facts_text(facts), encoding="utf-8")
        print("updated:", ", ".join(sync_docs(facts)) or "nothing")
        return 0
    if "--check" in args:
        return check()
    return build_pdf(draft="--draft" in args)


if __name__ == "__main__":
    sys.exit(main())
