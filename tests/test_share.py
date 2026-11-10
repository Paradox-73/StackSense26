"""Share links and answers files (app/static/share.js), run under Node when it is installed."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is not installed")


def node(script: str):
    out = subprocess.run([NODE, "-e", f"const Share = require({json.dumps(str(ROOT / 'app/static/share.js'))});\n{script}"],
                         capture_output=True, text=True, check=True, timeout=30)
    return json.loads(out.stdout)


def test_link_round_trip_keeps_answers_and_not_sure():
    r = node("""
const a = {dau: 25000, app_type: "saas", team_skills: ["python", "go"], project_name: "Zażółć ₹ café", budget_monthly: 4999.5};
const enc = Share.encode(a, ["regions"]);
console.log(JSON.stringify({enc, back: Share.decode(enc), a}));""")
    assert r["back"] == {"answers": r["a"], "unknown": ["regions"]}
    assert r["enc"].startswith("v1.") and all(c.isalnum() or c in "-_." for c in r["enc"])


def test_bad_links_are_rejected_not_thrown():
    r = node("""console.log(JSON.stringify([Share.decode("nonsense"), Share.decode("v1.!!!"), Share.decode("v1." + Buffer.from("[1,2]").toString("base64url")),
      Share.decode(null), Share.decode("v1." + "A".repeat(30000))]));""")
    assert r == [None] * 5


def test_answers_file_round_trip_and_other_shapes():
    r = node("""
const isKey = (k) => ["dau", "app_type", "regions"].includes(k);
const text = Share.toFile({dau: 100, app_type: "saas"}, ["regions"]);
console.log(JSON.stringify({
  own: Share.fromFile(text, isKey),
  scenario: Share.fromFile(JSON.stringify({name: "x", input: {dau: 5, bogus: 1}}), isKey),
  bare: Share.fromFile(JSON.stringify({dau: 7}), isKey),
  broken: Share.fromFile("{not json", isKey),
}));""")
    assert r["own"] == {"answers": {"dau": 100, "app_type": "saas"}, "unknown": ["regions"], "ignored": []}
    assert r["scenario"]["answers"] == {"dau": 5} and r["scenario"]["ignored"] == ["bogus"]
    assert r["bare"]["answers"] == {"dau": 7}
    assert r["broken"] is None


def test_page_loads_share_script_before_the_app():
    html = (ROOT / "app/static/index.html").read_text(encoding="utf-8")
    assert html.index("/static/share.js") < html.index("/static/app.js")


def test_a_standard_scenario_file_is_told_apart_from_answers():
    """A file in the statement's scenario schema (or an array of them) is not an answers file: the page sends it to /scenario."""
    r = node("""
const isKey = (k) => ["dau", "platforms", "compliance", "existing_systems"].includes(k);
const scenario = {scenario_id: "P2", project: {name: "FixIt Now", platforms: ["web"]}, team: {size: 3}, compliance: ["dpdp"]};
console.log(JSON.stringify({
  one: Share.fromFile(JSON.stringify(scenario), isKey),
  many: Share.fromFile(JSON.stringify([scenario, scenario]), isKey),
  few: Share.fromFile(JSON.stringify({scenario_id: "E1", project: {name: "x"}}), isKey),
  answers: Share.fromFile(JSON.stringify({platforms: ["web"], compliance: ["gdpr"], existing_systems: []}), isKey),
  list: Share.fromFile("[1, 2]", isKey),
}));""")
    assert r["one"] == r["many"] == r["few"] == {"scenario": True}
    assert r["answers"] == {"answers": {"platforms": ["web"], "compliance": ["gdpr"], "existing_systems": []}, "unknown": [], "ignored": []}
    assert r["list"] is None
