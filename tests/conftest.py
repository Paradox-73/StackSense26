import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SCEN_DIR = Path(__file__).resolve().parent / "scenarios"


def load_scenarios():
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(SCEN_DIR.glob("*.json"))]


@pytest.fixture(scope="session")
def kb():
    from engine.kb import load_kb
    return load_kb()


@pytest.fixture(scope="session")
def presets():
    from engine.kb import load_presets
    return {p["id"]: p for p in load_presets()}


# ---------------------------------------------------------------- language-model isolation
# No test may reach a real model: the key is removed, the disk cache is a temporary folder, and the
# transport (the function that sends the HTTP request) refuses to run unless a test installs a fake.

class FakeTransport:
    """Stands in for engine.llm's HTTP transport. `replies` is a list of (status, body) or exceptions, used in order;
    when it runs out the last one repeats. Every request is kept in `calls` as (url, payload)."""

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def __call__(self, url, headers, payload, timeout):
        assert "Bearer" in headers.get("Authorization", "")
        self.calls.append((url, json.loads(json.dumps(payload))))
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return reply


def chat_body(content):
    """A chat-completions response body holding `content` (a dict is sent as JSON text)."""
    import json as _json
    return {"choices": [{"message": {"content": content if isinstance(content, str) else _json.dumps(content)}}]}


@pytest.fixture(autouse=True)
def _llm_isolated(monkeypatch, tmp_path):
    from engine import llm
    for name in ("STACKSENSE_LLM", "STACKSENSE_LLM_API_KEY", "OPENROUTER_API_KEY", "STACKSENSE_LLM_MODELS", "STACKSENSE_LLM_BASE_URL",
                 "STACKSENSE_LLM_DAILY_LIMIT"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(llm, "DOTENV_PATH", tmp_path / "no.env")
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path / "llm_cache")

    def refuse(*a, **k):
        raise AssertionError("a test tried to send a real LLM request")
    llm.set_transport(refuse)
    yield
    llm.set_transport(None)


@pytest.fixture
def fake_llm(monkeypatch):
    """Configure a fake key and install a fake transport: call fake_llm(replies) to script the answers."""
    from engine import llm
    monkeypatch.setenv("STACKSENSE_LLM_API_KEY", "test-key-not-real")
    monkeypatch.setenv("STACKSENSE_LLM_MODELS", "model/a:free,model/b:free")

    def install(*replies):
        fake = FakeTransport([(200, chat_body(r)) if not isinstance(r, (tuple, Exception)) else r for r in replies])
        llm.set_transport(fake)
        return fake
    return install
