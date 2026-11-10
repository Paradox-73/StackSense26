"""Launcher (run.py) checks that do not start a server."""
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import run  # noqa: E402


def test_in_venv_matches_this_interpreter():
    # The test suite runs from .venv; the launcher must recognise that even when
    # .venv/bin/python is a symlink (macOS/Linux).
    in_project_venv = Path(sys.prefix).resolve() == run.VENV.resolve()
    assert run._in_venv() is in_project_venv


def test_in_venv_false_for_other_prefix(monkeypatch, tmp_path):
    monkeypatch.setattr(run, "VENV", tmp_path)
    assert run._in_venv() is False


def test_busy_port_moves_to_next_free_port():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        port = busy.getsockname()[1]
        chosen = run._free_port("127.0.0.1", port)
    assert chosen != port
    assert port < chosen <= port + 9


def test_broken_venv_gives_hint_instead_of_traceback(monkeypatch, tmp_path, capsys):
    fake = tmp_path / "python"
    fake.write_text("")
    monkeypatch.setattr(run, "VPY", fake)
    monkeypatch.setattr(run, "_runs", lambda code: False)
    assert run.bootstrap() == 1
    assert "delete the .venv folder" in capsys.readouterr().out


def test_pip_failure_gives_hint(monkeypatch, tmp_path, capsys):
    fake = tmp_path / "python"
    fake.write_text("")
    monkeypatch.setattr(run, "VPY", fake)
    monkeypatch.setattr(run, "_runs", lambda code: code == "import pip")

    class Failed:
        returncode = 1

    monkeypatch.setattr(run.subprocess, "run", lambda *a, **k: Failed())
    assert run.bootstrap() == 1
    assert "pip install failed" in capsys.readouterr().out

