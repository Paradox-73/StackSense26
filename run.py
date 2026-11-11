"""One-command launcher:  python run.py  [--port 8000] [--no-browser] [--no-llm]

Creates .venv and installs requirements on first run, then starts the server at
http://127.0.0.1:8000 . Works on Windows, macOS and Linux with Python 3.10 to 3.13 (CI tests 3.10 and 3.13).
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
VPY = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def say(msg: str) -> None:
    print(f"[stacksense] {msg}", flush=True)


def _in_venv() -> bool:
    # sys.prefix is the venv folder when this interpreter runs inside it. Comparing resolved
    # interpreter paths does not work on macOS/Linux, where .venv/bin/python is a symlink
    # to the system Python.
    return VENV.exists() and os.path.samefile(sys.prefix, VENV)


def _runs(code: str) -> bool:
    return subprocess.run([str(VPY), "-c", code], capture_output=True).returncode == 0


def bootstrap() -> int:
    if VPY.exists() and not _runs("import pip"):
        say("the .venv folder is broken or was copied from another computer.")
        say("delete the .venv folder, then run this command again.")
        return 1
    if not VPY.exists():
        say("creating virtual environment in .venv (first run only) ...")
        if subprocess.run([sys.executable, "-m", "venv", str(VENV)]).returncode != 0:
            say("could not create .venv. On Debian/Ubuntu: sudo apt install python3-venv,")
            say("then delete the .venv folder and run this command again.")
            return 1
    if not _runs("import fastapi, uvicorn"):
        say("installing requirements (first run only, needs internet, about 30 s) ...")
        pip = [str(VPY), "-m", "pip", "install", "-q", "--disable-pip-version-check", "-r", str(ROOT / "requirements.txt")]
        if subprocess.run(pip).returncode != 0:
            say("pip install failed. Check the internet connection.")
            say("If your Python is 3.15 or newer, install Python 3.12 or 3.13 from python.org and retry.")
            return 1
    cmd = [str(VPY), str(ROOT / "run.py"), *sys.argv[1:]]
    if os.name != "nt":
        os.execv(cmd[0], cmd)
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:  # Ctrl+C also reaches the server process, which shuts down cleanly
        return 0


def _free_port(host: str, port: int) -> int:
    for p in range(port, port + 10):
        with socket.socket() as s:
            try:
                s.bind((host, p))
                return p
            except OSError:
                say(f"port {p} is already in use, trying {p + 1}")
    sys.exit(f"[stacksense] ports {port}-{port + 9} are all in use; pick one with --port")


def _open_browser_when_ready(url: str) -> None:
    for _ in range(60):
        try:
            urllib.request.urlopen(url + "/api/health", timeout=1)
            webbrowser.open(url)
            return
        except OSError:
            time.sleep(0.5)


def main() -> int:
    if sys.version_info < (3, 10):
        say(f"Python 3.10 or newer is needed; this is Python {sys.version.split()[0]}.")
        say("Install Python 3.12 from https://www.python.org/downloads/ and run: python3 run.py")
        return 1
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="switch every language-model feature off (STACKSENSE_LLM=off)")
    a = ap.parse_args()
    if a.no_llm:
        os.environ["STACKSENSE_LLM"] = "off"
    try:
        import fastapi  # noqa: F401
        import uvicorn
    except ImportError:
        if _in_venv():
            say("dependencies are missing from .venv; delete the .venv folder and run again.")
            return 1
        return bootstrap()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    port = _free_port(a.host, a.port)
    url = f"http://{a.host}:{port}"
    say(f"starting on {url}  (Ctrl+C to stop)")
    if not a.no_browser:
        threading.Thread(target=_open_browser_when_ready, args=(url,), daemon=True).start()
    try:
        uvicorn.run("app.main:app", host=a.host, port=port, log_level="info")
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
