"""The submission folder (problem statement 9.3) holds only allowlisted files, the engine's current outputs and the
report PDF, and passes its own self-checks."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import package_submission as ps  # noqa: E402


# The report PDF ships beside source/, not in it: in a copy of source/ it is absent, and so is that problem's cause.
EXPECTED = {ps.NO_EMAIL} | (set() if ps.REPORT_PDF.exists() else {ps.NO_PDF})


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    return ps.build(tmp_path_factory.mktemp("dist"))


def test_folder_has_the_section_9_3_layout_and_passes_its_checks(built):
    dest, problems = built
    email = json.loads((ROOT / "report" / "cover.json").read_text(encoding="utf-8"))["email"]
    # The owner adds the email before submitting.
    assert [p for p in problems if p not in EXPECTED - {ps.NO_EMAIL}] == ([] if email.strip() else [ps.NO_EMAIL])
    full = "_".join(json.loads((ROOT / "report" / "cover.json").read_text(encoding="utf-8"))["author"].split())
    assert dest.name == f"StackSense26_{full}"
    pdf = ["Report_" + full + ".pdf"] if ps.REPORT_PDF.exists() else []
    assert sorted(p.name for p in dest.iterdir()) == pdf + ["outputs", "source"]
    assert (dest / "source" / "README.md").is_file() and (dest / "source" / ".env.example").is_file()
    assert sorted(p.name for p in (dest / "outputs").iterdir()) == [f"P{i}_output.json" for i in range(1, 7)]
    names = [p.relative_to(dest).as_posix() for p in dest.rglob("*") if p.is_file()]
    assert not [n for n in names if ".venv" in n or "__pycache__" in n or "planning" in n.lower() or n.endswith(".pyc")]
    assert not [n for n in names if n.startswith("source/") and n.endswith(".pdf")]


def test_an_output_that_is_not_the_engines_is_caught(built, tmp_path):
    import shutil
    dest = tmp_path / built[0].name
    shutil.copytree(built[0], dest)
    out = dest / "outputs" / "P3_output.json"
    doc = json.loads(out.read_text(encoding="utf-8"))
    doc["stack"]["database"]["choice"] = "A database typed in by hand"
    out.write_text(json.dumps(doc), encoding="utf-8")
    assert [p for p in ps.check(dest) if p not in EXPECTED] == ["outputs/P3_output.json is not what the engine returns for P3.json now"]


def test_an_output_file_for_no_public_scenario_is_caught(built, tmp_path):
    """A stray outputs/E1_output.json (say from a run over scenarios/edge) is copied with the allowlist; it is not one
    of the six outputs the folder must hold, and no check compares it with the engine."""
    import shutil
    dest = tmp_path / built[0].name
    shutil.copytree(built[0], dest)
    for folder in ("outputs", "source/outputs"):
        (dest / folder / "E1_output.json").write_text('{"status": "ok"}', encoding="utf-8")
    assert [p for p in ps.check(dest) if p not in EXPECTED] == [
        "outputs/E1_output.json is not the output of a public scenario",
        "source/outputs/E1_output.json is not the output of a public scenario"]


def test_a_title_page_without_the_registered_email_is_a_problem(built, tmp_path):
    import shutil
    dest = tmp_path / built[0].name
    shutil.copytree(built[0], dest)
    cover = dest / "source" / "report" / "cover.json"
    doc = json.loads(cover.read_text(encoding="utf-8"))
    for email, flagged in (("", True), ("  ", True), ("entrant@example.com", False)):
        cover.write_text(json.dumps(dict(doc, email=email)), encoding="utf-8")
        assert (ps.NO_EMAIL in ps.check(dest)) == flagged, email


def test_self_check_catches_a_leaked_name_a_local_path_and_secrets(built, tmp_path):
    import shutil
    dest = tmp_path / built[0].name
    shutil.copytree(built[0], dest)
    (dest / "source" / "README.md").write_text("see C:" + chr(92) + "Users" + chr(92) + "someone", encoding="utf-8")
    (dest / "source" / "notes").mkdir()
    (dest / "source" / "notes" / ("PLAN" + ".md")).write_text("x", encoding="utf-8")
    (dest / "source" / ".env").write_text("x", encoding="utf-8")
    (dest / "source" / "api.md").write_text("x", encoding="utf-8")
    (dest / "source" / "run.py").unlink()
    problems = ps.check(dest)
    for part in ("README.md contains", "forbidden name in source: notes/PLAN", "secrets file in source: .env",
                 "forbidden name in source: api.md", "missing required file: source/run.py"):
        assert any(part in p for p in problems), (part, problems)


def test_only_the_reports_declaration_line_may_name_the_coding_assistant():
    name = "Cl" + "aude"
    line = ps.DECLARATION + "used to write code and tests."
    report = f"# R\n\n## 11. AI assistance declaration\n{line}\n- A provider bullet.\n"
    assert name.lower() not in ps.shippable_text("report/report.md", report).lower()
    for leak in (f"- Built with {name}.", line + f" {name} also chose the stack.", "  " + line, f"## 11. {name} declaration"):
        assert name.lower() in ps.shippable_text("report/report.md", report + leak + "\n").lower(), leak
    assert name in ps.shippable_text("README.md", report)


def test_allowlist_leaves_out_working_folders():
    files = {p.relative_to(ROOT).as_posix() for p in ps.allowed_files()}
    assert "README.md" in files and "tools/package_submission.py" in files and "outputs/P1_output.json" in files
    assert not [f for f in files if f.startswith((".venv", "dist", "planning", ".git/", ".impeccable", "docs/spec_10nov"))]


def test_secrets_and_notes_never_ship_and_the_video_script_does():
    files = {p.relative_to(ROOT).as_posix() for p in ps.allowed_files()}
    assert "report/demo_script.md" in files and "benchmark/llm_baseline.json" in files and ".env.example" in files
    assert not [f for f in files if f.endswith("api.md") or (f.split("/")[-1].startswith(".env") and f != ".env.example")]
    assert not [f for f in files if f.endswith(".usage.json")]
    assert ps._excluded(Path("api.md")) and ps._excluded(Path(".env")) and ps._excluded(Path(".env.local"))
    assert not ps._excluded(Path(".env.example"))


def test_relative_links_in_the_readme_and_reference_point_to_shipped_files():
    files = {p.relative_to(ROOT).as_posix() for p in ps.allowed_files()}
    broken = []
    for doc in ("README.md", "docs/REFERENCE.md"):
        text = (ROOT / doc).read_text(encoding="utf-8")
        for target in re.findall(r"\]\(([^)\s]+)", text):
            if re.match(r"(?:[a-z]+:|#)", target):
                continue
            path = (ROOT / doc).parent.joinpath(target.split("#")[0]).resolve().relative_to(ROOT).as_posix()
            if path not in files and not any(f.startswith(path.rstrip("/") + "/") for f in files):
                broken.append(f"{doc} -> {target}")
    assert not broken, broken
