"""Counts stated in the README match the data files."""
import re
from pathlib import Path

import pytest

from engine.kb import load_presets

ROOT = Path(__file__).resolve().parent.parent


def test_readme_preset_count_matches_presets_file():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    n = len(load_presets())
    counts = {int(x) for x in re.findall(r"(\d+) (?:presets|ready-made scenarios)", readme)}
    assert counts == {n}, (counts, n)


def test_indian_storefront_presets_present():
    ids = {p["id"] for p in load_presets()}
    assert {"india_college_fest", "india_upi_payments", "india_food_delivery"} <= ids


def test_no_traced_to_source_overclaim():
    bad = ("Every point traced to a cited source", "every point of every score", "cannot show why", "Every score cited")
    files = [ROOT / "app" / "static" / "app.js", ROOT / "report" / "report.md", ROOT / "report" / "demo_script.md", ROOT / "README.md"]
    for f in files:
        if not f.exists():  # demo_script.md is not in the submission zip
            continue
        text = f.read_text(encoding="utf-8")
        for phrase in bad:
            assert phrase not in text, (f.name, phrase)


def test_rubric_covers_every_scored_criterion():
    import json
    rubric = json.loads((ROOT / "data" / "rubric.json").read_text(encoding="utf-8"))["criteria"]
    used = set()
    for f in (ROOT / "data" / "kb").glob("*.json"):
        d = json.loads(f.read_text(encoding="utf-8"))
        for item in d.get("items", []) if isinstance(d, dict) else []:
            used |= set(item.get("scores", {}))
    assert used <= set(rubric), used - set(rubric)
    assert "Appendix C. Score rubric" in (ROOT / "report" / "report.md").read_text(encoding="utf-8")


# ---- numbers quoted in the documents come from the code (report/facts.json, tools/build_report.py) ----
import sys

sys.path.insert(0, str(ROOT / "tools"))
import build_report  # noqa: E402


@pytest.fixture(scope="module")
def facts():
    return build_report.compute_facts()


def test_documents_quote_the_right_counts(facts):
    assert build_report.doc_problems(facts) == []


def test_old_readme_count_would_be_caught(facts):
    """The check really compares: a README that went back to 88 tests is flagged."""
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    assert re.search(r"\d+ tests", text)
    original = build_report.DOCS
    tmp = ROOT / "report" / "_stale_readme_check.md"
    try:
        tmp.write_text(re.sub(r"\d+ tests", "88 tests", text, count=1), encoding="utf-8")
        build_report.DOCS = [tmp]
        assert any("88 tests" in p for p in build_report.doc_problems(facts))
    finally:
        build_report.DOCS = original
        tmp.unlink(missing_ok=True)


def test_stale_benchmark_sentences_in_the_readme_would_be_caught(facts):
    """The benchmark and LLM-baseline sentences are checked too: the old 152/160 and 6-of-40 wording is flagged."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    stale = re.sub(r"acceptable \(\d+ of all", "acceptable (152 of all", text, count=1)
    stale = re.sub(r"breaks a hard requirement in \d+ of", "breaks a hard requirement in 6 of", stale, count=1)
    stale = re.sub(r"on 160, against the engine's 81% and \d+%", "on 160, against the engine's 81% and 95%", stale, count=1)
    assert stale != text
    tmp = ROOT / "report" / "_stale_readme_bench.md"
    original = build_report.DOCS
    try:
        tmp.write_text(stale, encoding="utf-8")
        build_report.DOCS = [tmp]
        found = " ".join(build_report.doc_problems(facts))
        assert "152 of all" in found and "in 6 of the 40" in found and "and 95%" in found
    finally:
        build_report.DOCS = original
        tmp.unlink(missing_ok=True)


def test_limitations_do_not_call_a_scored_technology_unscored():
    from engine.kb import LAYERS, load_kb
    kb = load_kb()
    ids = {i["id"] for layer in LAYERS for i in kb[layer]}
    line = next(ln for ln in (ROOT / "report" / "report.md").read_text(encoding="utf-8").splitlines() if "are not scored" in ln and "Niche" in ln)
    unscored = line.split("Niche options (")[1].split(")")[0].lower()
    for name, kb_id in {"sql server": "sqlserver", "bigquery": "bigquery", "neo4j": "neo4j", "oracle": "oracle", "cockroachdb": "cockroachdb"}.items():
        assert not (name in unscored and kb_id in ids), f"{name} is in the knowledge base but the report says it is not scored"


def test_facts_file_is_current(facts):
    stored = (ROOT / "report" / "facts.json").read_text(encoding="utf-8").replace(chr(13) + chr(10), chr(10))
    assert stored == build_report.facts_text(facts), "run python tools/build_report.py --facts"


def test_validation_table_counts_every_test(facts):
    text = (ROOT / "report" / "validation.md").read_text(encoding="utf-8")
    assert f"Total: {facts['tests']} tests." in text
    rows = [int(n) for n in re.findall(r"^\| `test_\w+\.py` .*? \| (\d+) \|", text, re.M)]
    assert sum(rows) == facts["tests"]
    report = (ROOT / "report" / "report.md").read_text(encoding="utf-8")
    assert f"| **{facts['tests']}** |" in report


def test_report_is_written_in_first_person_with_the_four_required_sections():
    text = (ROOT / "report" / "report.md").read_text(encoding="utf-8")
    assert not [ln for ln in text.splitlines() if re.search(r"\bWe\b", ln)]
    h2 = [ln[3:] for ln in text.splitlines() if ln.startswith("## ")]
    for need in ("System design", "Input parameters", "Sample recommendations", "Edge-case handling"):
        assert any(need in h for h in h2), need


def test_every_image_in_the_report_exists():
    text = (ROOT / "report" / "report.md").read_text(encoding="utf-8")
    for src in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
        assert (ROOT / "report" / src).resolve().exists(), src


def test_every_scripted_screenshot_exists_and_is_listed(facts):
    import capture_screenshots as cs
    for name, *_ in cs.SHOTS:
        assert (ROOT / "report" / "screenshots" / f"{name}.png").exists(), name
    assert len(cs.SHOTS) == 20


def test_architecture_figures_quote_the_right_counts(facts):
    svg = (ROOT / "docs" / "architecture.svg").read_text(encoding="utf-8")
    for pat, key in ((r"(\d+) technologies", "technologies"), (r"(\d+) rules", "rules"), (r"(\d+) examples", "presets"),
                     (r"Refine: (\d+) questions", "questions"), (r"Quick mode: (\d+) questions", "quick_questions"),
                     (r"(\d+) questions, defaults", "questions")):
        for m in re.findall(pat, svg):
            assert int(m) == facts[key], (pat, m)
    for name in ("architecture.svg", "pipeline.svg"):
        text = (ROOT / "docs" / name).read_text(encoding="utf-8")
        assert "<title" in text and "<desc" in text


def test_readme_starts_with_the_architecture_figure():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.index("docs/architecture.svg") < readme.index("## Quick start")


def test_fonts_are_cited_in_report_and_readme():
    for f in (ROOT / "README.md", ROOT / "report" / "report.md"):
        text = f.read_text(encoding="utf-8")
        for need in ("Fraunces", "Geist", "SIL Open Font License"):
            assert need in text, (f.name, need)


def test_no_assistant_or_team_wording_in_shipped_files():
    banned = re.compile("cl" + "aude|anth" + "ropic|co-auth" + "ored|pri" + "ze|team" + "mate", re.I)
    skip = {".venv", "__pycache__", ".git", ".pytest_cache", "planning", "." + "cl" + "aude"}
    for path in ROOT.rglob("*"):
        if not path.is_file() or skip & set(path.relative_to(ROOT).parts) or path.name.upper().startswith("CL" + "AUDE"):
            continue
        if path.suffix.lower() not in {".py", ".md", ".json", ".js", ".html", ".css", ".svg", ".txt", ".yml", ".yaml", ".sha256"}:
            continue
        assert not banned.search(path.read_text(encoding="utf-8", errors="ignore")), path.relative_to(ROOT)


def test_svg_files_are_well_formed():
    import xml.dom.minidom
    for f in list((ROOT / "docs").glob("*.svg")) + list((ROOT / "report").glob("*.svg")):
        xml.dom.minidom.parse(str(f))
