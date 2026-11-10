"""Build the submission folder of problem statement section 9.3 from an allowlist, then check it.

    python tools/package_submission.py                   # dist/StackSense26_<FullName>/, with the self-checks below
    python tools/package_submission.py --verify          # also run source/: presets, the public scenarios, /api/health
    python tools/package_submission.py --verify --pytest # and run the whole test suite there (a few minutes)
    python tools/package_submission.py --list            # print the files that would go into source/

The folder (FullName is the author in report/cover.json, spaces as underscores):

    StackSense26_<FullName>/
      source/                 allowlisted files only, with README.md and .env.example at its root
      outputs/P1_output.json ... P6_output.json   written now by the engine from scenarios/public
      Report_<FullName>.pdf   report/StackSense_Report.pdf, built by tools/build_report.py

Only paths on the allowlist go into source/, so a stray file in the working folder cannot reach it. Self-checks:
  * every required file is present, and each output equals what the engine returns for its scenario now
  * no .venv, caches, .git, tool-settings folders, planning notes or secrets files
  * no text file that mentions a local path or a name that should not ship; the report's section 11, the AI
    assistance declaration the statement asks for, is the one place allowed to name the coding assistant
  * source/ is under 25 MB and the whole folder under 1 GB
Exit code 1 if any check fails.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
MAX_BYTES = 25 * 1024 * 1024  # source/ budget (the statement allows 1 GB for the whole folder); screenshots are most of it
MAX_FOLDER_BYTES = 1024 ** 3
REPORT_PDF = ROOT / "report" / "StackSense_Report.pdf"
PUBLIC = ROOT / "scenarios" / "public"

# Top-level files and folders that may be packaged (everything else is left out).
ALLOW_FILES = ["README.md", "run.py", "cli.py", "requirements.txt", "requirements.lock.txt", "requirements-dev.txt", ".gitignore", ".env.example",
               "Dockerfile", "compose.yaml", ".dockerignore"]
ALLOW_DIRS = ["app", "engine", "data", "docs", "tests", "tools", "report", "benchmark", "scenarios", "outputs", ".github"]
# spec_10nov holds the organisers' own statement files (kept out of git): never ours to ship.
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv", ".git", "node_modules", "dist", "spec_10nov"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".tmp", ".log"}
# Paths that never ship: the local counter of language-model calls and any secrets file (the allowlist already leaves
# them out; this is a second, explicit guard), and the report PDF, which sits at the folder root instead.
EXCLUDE_PATHS = {"data/llm_cache/.usage.json", "report/StackSense_Report.pdf"}

REQUIRED = [
    "README.md", ".env.example", "run.py", "cli.py", "requirements.txt", "app/main.py", "app/static/index.html",
    "app/static/app.js", "app/static/scenario.html", "engine/__init__.py", "engine/standard.py", "report/report.md",
    "report/sources.md", "data/kb/frontend.json", "data/kb/backend.json", "data/kb/database.json", "data/kb/hosting.json",
    "data/kb/compat_rules.json", "data/questions.json", "data/glossary.json", "data/presets.json", "data/rubric.json",
    "data/explain_templates.json", "app/static/fonts/OFL.txt", "docs/architecture.svg", "docs/pipeline.svg",
] + [f"scenarios/public/P{i}.json" for i in range(1, 7)]
TEXT_SUFFIXES = {".py", ".md", ".json", ".js", ".html", ".css", ".svg", ".txt", ".yml", ".yaml", ".sha256", ".toml", ".cfg"}
# Written in pieces so that this file does not trip its own check.
# Local paths with one or two backslashes (JSON writes two).
FORBIDDEN_TEXT = ["cl" + "aude", "anth" + "ropic", "E:" + chr(92) + "Projects", "E:" + chr(92) * 2 + "Projects", "E:" + "/Projects",
                  "C:" + chr(92) + "Users", "C:" + chr(92) * 2 + "Users", "C:" + "/Users", "/Us" + "ers/kan",
                  "PLAN" + ".md", "kav" + "yab@", "Co-Auth" + "ored"]
FORBIDDEN_NAMES = ["cl" + "aude", "plan" + ".md", "planning", ".venv", ".git/", "__pycache__", "api.md", ".impeccable"]
# The first line of report section 11, the AI assistance declaration (statement 5.1, FAQ and template), must name the
# coding assistant; only this exact opening, at the start of a line of report/report.md, is exempt from the check.
DECLARATION = "- Cl" + "aude Code (Anth" + "ropic), an AI coding assistant: "


def _excluded(rel: Path) -> bool:
    if rel.as_posix() in EXCLUDE_PATHS or rel.name == "api.md":
        return True
    return rel.name.startswith(".env") and rel.name != ".env.example"


def shippable_text(rel: str, text: str) -> str:
    """The text the forbidden-word check reads: every file whole, except that the declaration's opening words are
    removed from the start of a line in report/report.md (the rest of that line is still checked)."""
    text = text.replace("\r\n", "\n")
    if rel != "report/report.md":
        return text
    return "\n".join(line[len(DECLARATION):] if line.startswith(DECLARATION) else line for line in text.split("\n"))


def folder_name() -> str:
    author = json.loads((ROOT / "report" / "cover.json").read_text(encoding="utf-8"))["author"]
    return "StackSense26_" + "_".join(author.split())


def allowed_files() -> list[Path]:
    out: list[Path] = []
    for name in ALLOW_FILES:
        p = ROOT / name
        if p.is_file() and not _excluded(p.relative_to(ROOT)):
            out.append(p)
    for d in ALLOW_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            rel = p.relative_to(ROOT)
            if not p.is_file() or SKIP_PARTS & set(rel.parts) or p.suffix in SKIP_SUFFIXES or _excluded(rel):
                continue
            out.append(p)
    return out


def build(parent: Path) -> tuple[Path, list[str]]:
    """Write <parent>/StackSense26_<FullName>/ (replacing an earlier build) and return it with its problems."""
    from engine.standard import run
    dest = parent / folder_name()
    if dest.exists():
        _remove_tree(str(dest))
    for p in allowed_files():
        target = dest / "source" / p.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(p, target)
    for f in sorted(PUBLIC.glob("*.json")):
        text = json.dumps(run(json.loads(f.read_text(encoding="utf-8"))), indent=2, ensure_ascii=False) + "\n"
        for folder in (dest / "outputs", dest / "source" / "outputs"):  # the copy in source/ is never older
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{f.stem}_output.json").write_text(text, encoding="utf-8")
    if REPORT_PDF.is_file():
        shutil.copyfile(REPORT_PDF, dest / f"Report_{folder_name()[len('StackSense26_'):]}.pdf")
    return dest, check(dest)


def _size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def check(dest: Path) -> list[str]:
    """Return the list of problems (empty = the folder passes)."""
    from engine.standard import run
    bad: list[str] = []
    source = dest / "source"
    names = sorted(p.relative_to(source).as_posix() for p in source.rglob("*") if p.is_file()) if source.is_dir() else []
    for need in REQUIRED:
        if need not in names:
            bad.append(f"missing required file: source/{need}")
    for n in names:
        low = n.lower()
        if Path(n).name.startswith(".env") and Path(n).name != ".env.example":
            bad.append(f"secrets file in source: {n}")
        for f in FORBIDDEN_NAMES:
            if f in low:
                bad.append(f"forbidden name in source: {n}")
        if Path(n).suffix.lower() in TEXT_SUFFIXES:
            text = shippable_text(n, (source / n).read_text(encoding="utf-8", errors="ignore")).lower()
            for f in FORBIDDEN_TEXT:
                if f.lower() in text:
                    bad.append(f"{n} contains {f!r}")
    if len([n for n in names if n.startswith("data/") and n.endswith(".json")]) < 8:
        bad.append("fewer than 8 data files in source")
    for f in sorted(PUBLIC.glob("*.json")):
        fresh = run(json.loads(f.read_text(encoding="utf-8")))
        for folder in ("outputs", "source/outputs"):
            out = dest / folder / f"{f.stem}_output.json"
            if not out.is_file():
                bad.append(f"missing {folder}/{out.name}")
            elif json.loads(out.read_text(encoding="utf-8")) != fresh:
                bad.append(f"{folder}/{out.name} is not what the engine returns for {f.name} now")
    pdfs = list(dest.glob("Report_*.pdf"))
    if [p.name for p in pdfs] != [f"Report_{dest.name[len('StackSense26_'):]}.pdf"] or pdfs[0].read_bytes()[:4] != b"%PDF":
        bad.append("the folder needs exactly one Report_<FullName>.pdf (run python tools/build_report.py first)")
    if source.is_dir() and _size(source) >= MAX_BYTES:
        bad.append(f"source/ is {_size(source) / 1e6:.1f} MB, over the 25 MB limit")
    if _size(dest) >= MAX_FOLDER_BYTES:
        bad.append("the folder is over 1 GB")
    return sorted(set(bad))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def verify(dest: Path, run_pytest: bool) -> list[str]:
    """Use a copy of source/ as a judge would: the presets and the public scenarios from the command line, then the server."""
    bad: list[str] = []
    td = tempfile.mkdtemp()
    try:
        root = Path(td) / "source"
        shutil.copytree(dest / "source", root)
        py = next((str(p) for p in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python") if p.exists()), sys.executable)
        r = subprocess.run([py, "cli.py", "--all"], cwd=root, capture_output=True, text=True)
        if r.returncode != 0 or "hipaa_telehealth" not in r.stdout + r.stderr:
            bad.append("cli.py --all failed in the copy: " + (r.stderr or r.stdout)[-300:])
        r = subprocess.run([py, "cli.py", "--scenario", "scenarios/public", "--out", str(Path(td) / "out"), "--no-llm"],
                           cwd=root, capture_output=True, text=True)
        for f in sorted((dest / "outputs").glob("*.json")):
            mine = Path(td) / "out" / f.name
            if r.returncode != 0 or not mine.is_file() or json.loads(mine.read_text(encoding="utf-8")) != json.loads(f.read_text(encoding="utf-8")):
                bad.append(f"cli.py --scenario in the copy did not reproduce outputs/{f.name}")
        port = _free_port()
        server = subprocess.Popen([py, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
                                  cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(60):
                try:
                    body = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1).read().decode()
                    if '"ok"' not in body:
                        bad.append("/api/health did not say ok")
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                bad.append("the server from the copy did not start")
        finally:
            server.terminate()
            try:
                server.wait(timeout=15)  # on Windows the temporary folder cannot be deleted while the server still runs
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait()
        if run_pytest:
            r = subprocess.run([py, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider"], cwd=root, capture_output=True, text=True)
            if r.returncode != 0:
                bad.append("pytest failed in the copy:\n" + r.stdout[-800:])
    finally:
        _remove_tree(td)
    return bad


def _remove_tree(path: str) -> None:
    """Delete a folder. On Windows a stopped server can hold its files for a few more seconds (the .venv python.exe
    starts the real interpreter as a child process), so retry before giving up."""
    for _ in range(20):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.5)
    shutil.rmtree(path, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "dist"), help="the folder that receives StackSense26_<FullName>/")
    ap.add_argument("--verify", action="store_true", help="run the copy in source/")
    ap.add_argument("--pytest", action="store_true", help="with --verify: run the test suite in the copy")
    ap.add_argument("--list", action="store_true", help="print the allowlisted files and stop")
    a = ap.parse_args()
    if a.list:
        for p in allowed_files():
            print(p.relative_to(ROOT).as_posix())
        return 0
    dest, problems = build(Path(a.out))
    files = [p for p in dest.rglob("*") if p.is_file()]
    print(f"{dest}: {len(files)} files, {_size(dest) / 1e6:.2f} MB")
    if a.verify and not problems:
        problems += verify(dest, a.pytest)
    for p in problems:
        print("PROBLEM:", p)
    print(f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
