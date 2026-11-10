"""Start run.py twice and check that /api/health answers each time (used by .github/workflows/install.yml).

    python tools/ci_launch_check.py

The first launch creates .venv and installs the requirements; the second reuses them. Exit code 1 if either
launch does not answer within 10 minutes (the first) or 2 minutes (the second).
"""
from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def stop(proc: subprocess.Popen) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
    else:
        proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


def launch(label: str, wait_s: int) -> bool:
    port = free_port()
    proc = subprocess.Popen([sys.executable, "run.py", "--no-browser", "--port", str(port)], cwd=ROOT)
    try:
        end = time.time() + wait_s
        while time.time() < end:
            if proc.poll() is not None:
                print(f"{label}: run.py exited with code {proc.returncode}")
                return False
            try:
                body = urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2).read().decode()
                print(f"{label}: /api/health answered {body[:60]}")
                return '"ok"' in body
            except OSError:
                time.sleep(1)
        print(f"{label}: no answer within {wait_s} s")
        return False
    finally:
        stop(proc)


def main() -> int:
    ok = launch("first launch", 600)
    ok = launch("second launch", 120) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
