"""The app must work with no internet: no external page resources, and no outbound connections."""
import re
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

STATIC = Path(__file__).resolve().parent.parent / "app" / "static"
TEXT_FILES = [STATIC / "index.html", STATIC / "styles.css", STATIC / "app.js", STATIC / "fonts" / "fonts.css",
              STATIC / "scenario.html", STATIC / "scenario.css", STATIC / "scenario.js", STATIC / "theme.js"]

# Constructs that make the browser load something: <link href>, <script src>, <img src>, CSS url()/@import, fetch().
LOADERS = [
    re.compile(r"<link\b[^>]*\bhref=[\"']([^\"']+)", re.I),
    re.compile(r"<(?:script|img|iframe|source|video|audio)\b[^>]*\bsrc=[\"']([^\"']+)", re.I),
    re.compile(r"url\(\s*[\"']?([^\"')]+)", re.I),
    re.compile(r"@import\s+[\"']([^\"']+)", re.I),
    re.compile(r"fetch\(\s*[\"'`]([^\"'`]+)", re.I),
]


def _loaded_refs():
    for path in TEXT_FILES:
        text = path.read_text(encoding="utf-8")
        for rx in LOADERS:
            for ref in rx.findall(text):
                yield path.name, ref


def test_no_external_resources():
    external = [(f, r) for f, r in _loaded_refs() if re.match(r"(https?:)?//", r, re.I)]
    assert external == []


def test_every_local_resource_is_served():
    client = TestClient(app)
    local = sorted({r for _, r in _loaded_refs() if r.startswith("/static/")})
    assert any(r.endswith(".woff2") for r in local)
    for ref in local:
        assert client.get(ref).status_code == 200, ref


def test_font_licence_shipped():
    text = (STATIC / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL Open Font License" in text and "Atkinson Hyperlegible Next" in text and "Atkinson Hyperlegible Mono" in text
    report = (STATIC.parent.parent / "report" / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL Open Font License" in report and "Fraunces" in report and "Geist" in report


@pytest.fixture
def no_sockets(monkeypatch):
    """Refuse every connection that leaves this machine (loopback stays allowed for the event loop)."""
    real_connect = socket.socket.connect

    def guarded(self, address, *a, **k):
        host = address[0] if isinstance(address, tuple) else str(address)
        if host not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"network access attempted: {address}")
        return real_connect(self, address, *a, **k)

    def refuse(*a, **k):
        raise AssertionError("network access attempted")

    monkeypatch.setattr(socket.socket, "connect", guarded)
    monkeypatch.setattr(socket, "create_connection", refuse)
    monkeypatch.setattr(socket, "getaddrinfo", refuse)


def test_full_api_runs_without_network(no_sockets, presets):
    client = TestClient(app)
    for path in ["/", "/api/health", "/api/questions", "/api/presets", "/api/kb", "/api/glossary"]:
        assert client.get(path).status_code == 200, path
    answers = presets["startup_mvp"]["input"]
    assert client.post("/api/recommend", json=answers).status_code == 200
    assert client.post("/api/sensitivity", json={"answers": answers, "unknown": ["dau"]}).status_code == 200
    assert client.post("/api/export/markdown", json=answers).status_code == 200
