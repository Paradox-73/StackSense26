"""The scenario-file page and the home page driven in a real browser (Playwright and the installed Chrome, both
build-time tools from requirements-dev.txt; the tests skip without them). The app runs in a subprocess with the
language model switched off and no key."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

pw_api = pytest.importorskip("playwright.sync_api")

ROOT = Path(__file__).resolve().parent.parent
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PUBLIC = sorted((ROOT / "scenarios" / "public").glob("P*.json"))


def _free_port() -> int:
    for port in range(8812, 8900):  # above the ports the developers use; 8821 is one of theirs
        if port == 8821:
            continue
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("no free port")


@pytest.fixture(scope="module")
def base_url():
    port = _free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith("STACKSENSE_LLM") and k != "OPENROUTER_API_KEY"}
    env["STACKSENSE_LLM"] = "off"
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
                              cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.25)
        else:
            raise RuntimeError("the app did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.terminate()
        server.wait(timeout=10)


@pytest.fixture(scope="module")
def browser():
    with pw_api.sync_playwright() as pw:
        exe = os.environ.get("CHROME") or (CHROME_EXE if os.path.exists(CHROME_EXE) else None)
        b = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch(channel="chrome")
        yield b
        b.close()


@pytest.fixture
def page(browser):
    p = browser.new_page()
    yield p
    p.close()


def _result(page):
    """Wait for a run to finish and return the status badge text."""
    return page.wait_for_selector("#sc-out .sc-status", timeout=30000).inner_text()


def test_an_array_file_offers_each_scenario_and_runs_the_chosen_one(page, base_url, tmp_path):
    """The organisers publish the six public scenarios as one JSON array; the page must let the user pick one."""
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in PUBLIC]
    f = tmp_path / "stacksense_public_scenarios.json"
    f.write_text(json.dumps(docs), encoding="utf-8")
    page.goto(f"{base_url}/scenario")
    page.wait_for_selector("#sc-form fieldset")
    page.set_input_files("#sc-file", str(f))
    choices = page.locator("#sc-out button")
    choices.first.wait_for(timeout=5000)
    assert choices.all_inner_texts() == [f"{d['scenario_id']}: {d['project']['name']}" for d in docs]
    choices.nth(2).click()
    assert _result(page) in ("ok", "ok_with_warnings")
    assert page.input_value("#f-project-name") == docs[2]["project"]["name"]
    assert page.evaluate("S.doc") == docs[2]


def _set(page, selector, value):
    page.fill(selector, value)
    page.dispatch_event(selector, "change")


def test_the_output_download_belongs_to_the_form_as_it_stands(page, base_url):
    page.goto(f"{base_url}/scenario?example=P1")
    assert _result(page) == "ok" and page.is_enabled("#sc-dl-out")
    _set(page, "#f-team-size", "4")
    assert not page.is_enabled("#sc-dl-out"), "edited since the run, so the output no longer matches"
    held = []
    page.route("**/api/scenario", lambda route: held.append(route))
    page.click("#sc-run")
    for _ in range(40):
        if held:
            break
        page.wait_for_timeout(50)
    _set(page, "#f-team-size", "5")  # edited while the run is in flight
    held[0].continue_()
    page.wait_for_function("() => document.querySelector('#sc-msg').textContent !== 'Running...'")
    assert not page.is_enabled("#sc-dl-out"), "the output that arrived is for the form as it was sent"
    page.unroute("**/api/scenario")
    page.click("#sc-run")
    page.wait_for_function("() => document.querySelector('#sc-msg').textContent.startsWith('Done')")
    assert page.is_enabled("#sc-dl-out") and page.evaluate("S.out.scenario_id") == "P1"


def test_the_form_sends_each_allowed_empty_value(page, base_url):
    """Statement table 3.1: team.languages is required but may be empty, p95_latency_ms is an integer or null, the other
    lists may be empty. Emptying such a field sends that value; emptying a scalar still falls back to its default."""
    p2 = json.loads((ROOT / "scenarios" / "public" / "P2.json").read_text(encoding="utf-8"))
    page.goto(f"{base_url}/scenario?example=P2")
    _result(page)
    for sel in ("#f-team-languages", "#f-infrastructure-existing_systems", "#f-requirements-p95_latency_ms", "#f-scale-users_12_months"):
        _set(page, sel, "")
    for group in ("#f-compliance", "#f-project-platforms"):
        for box in page.locator(f"{group} input").all():
            box.uncheck()
    doc = page.evaluate("S.doc")
    assert doc["team"].get("languages", "absent") == []
    assert doc["infrastructure"].get("existing_systems", "absent") == []
    assert doc["requirements"].get("p95_latency_ms", "absent") is None
    assert doc["compliance"] == [] and doc["project"]["platforms"] == []
    assert "users_12_months" not in doc["scale"], "an emptied scalar takes its default"
    assert doc["scale"]["users_at_launch"] == p2["scale"]["users_at_launch"], "an untouched field stays as loaded"
    page.click("#sc-run")
    _result(page)
    out = page.evaluate("S.out")
    assert "team.languages" not in [f for w in out["warnings"] for f in w["fields"]], "an empty list is not a missing field"


def test_the_load_file_control_shows_keyboard_focus(page, base_url):
    page.goto(f"{base_url}/scenario")
    page.wait_for_selector("#sc-form fieldset")
    for _ in range(12):
        page.keyboard.press("Tab")
        if page.evaluate("document.activeElement.id") == "sc-file":
            break
    assert page.evaluate("document.activeElement.id") == "sc-file"
    style, width = page.evaluate("""() => { const s = getComputedStyle(document.querySelector('label[for=sc-file]'));
        return [s.outlineStyle, s.outlineWidth]; }""")
    assert style != "none" and width != "0px", "the visible control must show the focus ring"
