"""The submission zip contains only allowlisted files and passes its own self-checks."""
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import package_submission as ps  # noqa: E402


def test_zip_builds_and_passes_self_checks(tmp_path):
    out = tmp_path / "s.zip"
    assert ps.build(out) == []
    names = zipfile.ZipFile(out).namelist()
    assert all(n.startswith("stacksense/") for n in names)
    assert "stacksense/data/kb/hosting.json" in names
    assert not [n for n in names if ".venv" in n or "__pycache__" in n or "planning" in n.lower() or n.endswith(".pyc")]
    assert out.stat().st_size < ps.MAX_BYTES


def test_self_check_catches_a_leaked_name_and_a_local_path(tmp_path):
    out = tmp_path / "bad.zip"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("stacksense/README.md", "see C:" + chr(92) + "Users" + chr(92) + "someone")
        z.writestr("stacksense/notes/PLAN" + ".md", "x")
    problems = ps.check(out)
    assert any("contains" in p for p in problems)
    assert any("forbidden name" in p for p in problems)
    assert any("missing required file" in p for p in problems)


def test_allowlist_leaves_out_working_folders():
    files = {p.relative_to(ROOT).as_posix() for p in ps.allowed_files()}
    assert "README.md" in files and "tools/package_submission.py" in files
    assert not [f for f in files if f.startswith((".venv", "dist", "planning", ".git/"))]


def test_secrets_and_notes_never_ship_and_the_video_script_does(tmp_path, monkeypatch):
    files = {p.relative_to(ROOT).as_posix() for p in ps.allowed_files()}
    assert "report/demo_script.md" in files and "benchmark/llm_baseline.json" in files and ".env.example" in files
    assert not [f for f in files if f.endswith("api.md") or (f.split("/")[-1].startswith(".env") and f != ".env.example")]
    assert not [f for f in files if f.endswith(".usage.json")]
    assert ps._excluded(Path("api.md")) and ps._excluded(Path(".env")) and ps._excluded(Path(".env.local"))
    assert not ps._excluded(Path(".env.example"))
    out = tmp_path / "bad.zip"
    with zipfile.ZipFile(out, "w") as z:
        z.writestr("stacksense/.env", "x")
        z.writestr("stacksense/api.md", "x")
    problems = ps.check(out)
    assert any("secrets file" in p for p in problems) and any("api.md" in p for p in problems)


def test_relative_links_in_the_readme_and_reference_point_to_shipped_files():
    import re
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
