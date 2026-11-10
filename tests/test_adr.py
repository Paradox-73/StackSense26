"""Decision-record export: one ADR per layer with five non-empty sections."""
import re
from copy import deepcopy

from fastapi.testclient import TestClient

from app.main import app
from engine import recommend
from engine.export import ADR_HEADINGS, to_adr
from engine.kb import LAYERS, load_presets

PRESETS = {p["id"]: p["input"] for p in load_presets()}


def _sections(md: str) -> dict:
    out, cur = {}, None
    for line in md.splitlines():
        m = re.match(r"### (.+)", line)
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
        elif cur and line.strip():
            out[cur].append(line)
    return out


def test_hipaa_records_have_five_non_empty_sections():
    md = to_adr(recommend(deepcopy(PRESETS["hipaa_telehealth"])))
    assert md.count("## ADR-") == len(LAYERS)
    for block in md.split("## ADR-")[1:]:
        secs = _sections(block)
        for h in ADR_HEADINGS:
            assert secs.get(h), (h, block[:200])
    assert "Business Associate Agreement" in md


def test_adr_api_and_determinism():
    c = TestClient(app)
    a = c.post("/api/export/adr", json=PRESETS["startup_mvp"]).text
    b = c.post("/api/export/adr", json=PRESETS["startup_mvp"]).text
    assert a == b and a.startswith("# Architecture decision records")
