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


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    return ps.build(tmp_path_factory.mktemp("dist"))


def test_folder_has_the_section_9_3_layout_and_passes_its_checks(built):
    dest, problems = built
    assert problems == []
    full = "_".join(json.loads((ROOT / "report" / "cover.json").read_text(encoding="utf-8"))["author"].split())
    assert dest.name == f"StackSense26_{full}"
    assert sorted(p.name for p in dest.iterdir()) == ["Report_" + full + ".pdf", "outputs", "source"]
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
    assert ps.check(dest) == ["outputs/P3_output.json is not what the engine returns for P3.json now"]


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
