"""Build the submission zip from an allowlist, then check it.

    python tools/package_submission.py                  # dist/StackSense_submission.zip, with the self-checks below
    python tools/package_submission.py --out my.zip
    python tools/package_submission.py --verify         # also unzip it, answer /api/health and run every preset from the unzipped copy
    python tools/package_submission.py --verify --pytest   # and run the whole test suite there (about 2 minutes)
    python tools/package_submission.py --list           # print what would be included

Only paths on the allowlist go in, so a stray file in the working folder cannot reach the zip. Self-checks:
  * every required file is present (the 8 data files, the launcher, the README, the report PDF)
  * no .venv, caches, .git, tool-settings folders or planning notes
  * no file name or text file that mentions a local path or a name that should not ship
  * the zip is under 10 MB
Exit code 1 if any check fails.
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_BYTES = 10 * 1024 * 1024

# Top-level files and folders that may be packaged (everything else is left out).
ALLOW_FILES = ["README.md", "run.py", "cli.py", "requirements.txt", "requirements.lock.txt", "requirements-dev.txt", ".gitignore", ".env.example"]
ALLOW_DIRS = ["app", "engine", "data", "docs", "tests", "tools", "report", "benchmark", "scenarios", "outputs", ".github"]
# spec_10nov holds the organisers' own statement files (kept out of git): never ours to ship.
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv", ".git", "node_modules", "dist", "spec_10nov"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".tmp", ".log"}
# Paths that never ship: the internal recording checklist, the local counter of language-model calls, and any
# secrets file. The allowlist already leaves them out; this is a second, explicit guard.
EXCLUDE_PATHS = {"data/llm_cache/.usage.json"}


def _excluded(rel: Path) -> bool:
    if rel.as_posix() in EXCLUDE_PATHS or rel.name == "api.md":
        return True
    return rel.name.startswith(".env") and rel.name != ".env.example"

REQUIRED = [
    "README.md", "run.py", "cli.py", "requirements.txt", "app/main.py", "app/static/index.html", "app/static/app.js",
    "engine/__init__.py", "report/StackSense_Report.pdf", "report/report.md", "report/sources.md",
    "data/kb/frontend.json", "data/kb/backend.json", "data/kb/database.json", "data/kb/hosting.json", "data/kb/compat_rules.json",
    "data/questions.json", "data/glossary.json", "data/presets.json", "data/rubric.json", "data/explain_templates.json",
    "app/static/fonts/OFL.txt", "docs/architecture.svg", "docs/pipeline.svg",
]
TEXT_SUFFIXES = {".py", ".md", ".json", ".js", ".html", ".css", ".svg", ".txt", ".yml", ".yaml", ".sha256", ".toml", ".cfg"}
# Written in pieces so that this file does not trip its own check.
FORBIDDEN_TEXT = ["cl" + "aude", "anth" + "ropic", "E:" + chr(92) + "Projects", "E:" + "/Projects", "C:" + chr(92) + "Users", "C:" + "/Users", "/Us" + "ers/kan",
                  "PLAN" + ".md", "kav" + "yab@", "Co-Auth" + "ored"]
FORBIDDEN_NAMES = ["cl" + "aude", "plan" + ".md", "planning", ".venv", ".git/", "__pycache__", "api.md"]


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


def build(out: Path) -> list[str]:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in allowed_files():
            z.write(p, "stacksense/" + p.relative_to(ROOT).as_posix())
    return check(out)


def check(zip_path: Path) -> list[str]:
    """Return the list of problems (empty = the zip passes)."""
    bad: list[str] = []
    with zipfile.ZipFile(zip_path) as z:
        names = [n[len("stacksense/"):] for n in z.namelist() if n.startswith("stacksense/")]
        if len(names) != len(z.namelist()):
            bad.append("an entry is outside the stacksense/ folder")
        have = set(names)
        for need in REQUIRED:
            if need not in have:
                bad.append(f"missing required file: {need}")
        for n in names:
            low = n.lower()
            if Path(n).name.startswith(".env") and Path(n).name != ".env.example":
                bad.append(f"secrets file in zip: {n}")
            for f in FORBIDDEN_NAMES:
                if f in low:
                    bad.append(f"forbidden name in zip: {n}")
            if Path(n).suffix.lower() in TEXT_SUFFIXES:
                text = z.read("stacksense/" + n).decode("utf-8", errors="ignore")
                for f in FORBIDDEN_TEXT:
                    if f.lower() in text.lower():
                        bad.append(f"{n} contains {f!r}")
        data_files = [n for n in names if n.startswith("data/") and n.endswith(".json")]
        if len(data_files) < 8:
            bad.append(f"only {len(data_files)} data files")
    size = zip_path.stat().st_size
    if size >= MAX_BYTES:
        bad.append(f"zip is {size / 1e6:.1f} MB, over the 10 MB limit")
    return sorted(set(bad))


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def verify(zip_path: Path, run_pytest: bool) -> list[str]:
    """Unzip into a temporary folder and use the unzipped copy: presets from the command line, then the server."""
    bad: list[str] = []
    td = tempfile.mkdtemp()
    try:
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(td)
        root = Path(td) / "stacksense"
        py = next((str(p) for p in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python") if p.exists()), sys.executable)
        r = subprocess.run([py, "cli.py", "--all"], cwd=root, capture_output=True, text=True)
        if r.returncode != 0 or "hipaa_telehealth" not in r.stdout + r.stderr:
            bad.append("cli.py --all failed in the unzipped copy: " + (r.stderr or r.stdout)[-300:])
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
                bad.append("the server from the unzipped copy did not start")
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
                bad.append("pytest failed in the unzipped copy:\n" + r.stdout[-800:])
    finally:
        _remove_tree(td)
    return bad


def _remove_tree(path: str) -> None:
    """Delete the temporary copy. On Windows a stopped server can hold its files for a few more seconds
    (the .venv python.exe starts the real interpreter as a child process), so retry before giving up."""
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
    ap.add_argument("--out", default=str(ROOT / "dist" / "StackSense_submission.zip"))
    ap.add_argument("--verify", action="store_true", help="unzip and run the copy")
    ap.add_argument("--pytest", action="store_true", help="with --verify: run the test suite in the unzipped copy")
    ap.add_argument("--list", action="store_true", help="print the allowlisted files and stop")
    a = ap.parse_args()
    if a.list:
        for p in allowed_files():
            print(p.relative_to(ROOT).as_posix())
        return 0
    out = Path(a.out)
    problems = build(out)
    n = len(zipfile.ZipFile(out).namelist())
    print(f"{out}: {n} files, {out.stat().st_size / 1e6:.2f} MB")
    if a.verify and not problems:
        problems += verify(out, a.pytest)
    for p in problems:
        print("PROBLEM:", p)
    print(f"{len(problems)} problems")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
