"""Take every screenshot used in the report from the running app, and check each one shows what the engine says.

    python tools/capture_screenshots.py            # write report/screenshots/*.png (20 images)
    python tools/capture_screenshots.py --check    # write nothing; exit 1 if any page disagrees with the engine
    python tools/capture_screenshots.py --only f02-why-hosting

Starts the app on a free local port and opens each deep link (a URL fragment such as #preset=<id>&panel=why)
in the installed Chrome through Playwright (build-time only, see requirements-dev.txt). Each shot lists
text that must appear on the page, computed from the engine's own output for the same answers. A shot
whose page lacks that text is a mismatch. Set CHROME to a browser path if Chrome is not found.

Three shots (f09, f10, f11) show the language-model features, so they need an API key in `.env` or the environment
(they send real requests; replies are cached in data/llm_cache/). Without a key they are skipped with a printed note and
the other 17 are taken as usual. With a key set, the shots that do not click a model button are taken the same way.
"""
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine import llm, recommend  # noqa: E402
from engine.kb import LAYERS, load_presets  # noqa: E402

OUT = ROOT / "report" / "screenshots"
MAX_H = 1250  # pixels; taller panels are cut at the bottom so they print at a readable size
CHROME_EXE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"


def _result(preset: str, **override) -> dict:
    inp = dict(next(p for p in load_presets() if p["id"] == preset)["input"])
    inp.update(override)
    return recommend(inp, with_counterfactuals=False)


def _stack_names(preset: str, **override) -> list[str]:
    r = _result(preset, **override)
    return [r["stack"][l]["pick"]["name"].split(" (")[0] for l in LAYERS]  # the page shows the name without its bracket


# name, deep link, element to crop to (None = the window), caption, function giving text that must appear on the page
SHOTS = [
    ("f01-result-hipaa", "#preset=hipaa_telehealth", "#out",
     "The result for the HIPAA telehealth example: four picks, cost and architecture style.",
     lambda: _stack_names("hipaa_telehealth")),
    ("f02-why-hosting", "#preset=hipaa_telehealth&panel=why&layer=hosting", "#panel-why",
     "The Why panel for hosting: reasons, the answers that moved the score and the runner-up.",
     lambda: _stack_names("hipaa_telehealth")[3:]),
    ("f03-alternatives", "#preset=hipaa_telehealth&panel=alts", "#panel-alts",
     "Alternatives: each layer's runner-ups, and the exclusions with their cause.",
     lambda: _stack_names("hipaa_telehealth")[3:]),
    ("f04-growth-path", "#preset=hipaa_telehealth&panel=growth", "#panel-growth",
     "Growth path: the stack at 1x, 10x and 100x the users, with cost.",
     lambda: _stack_names("hipaa_telehealth")[3:]),
    ("f05-not-sure", "#preset=startup_mvp&unsure=dau", "#out",
     "Not sure about daily users: the Depends-on panel shows which picks hold and where each flips.",
     lambda: ["Depends on"]),
    ("f06-glossary", "#preset=hipaa_telehealth&term=hipaa", None,
     "A glossary popover: plain-English definition, who it applies to, official source.",
     lambda: ["HIPAA"]),
    ("f07-refine-form", "#refine=1&open=1", "#form",
     "Refine: all 32 questions in five groups, with help text and Not sure on each.",
     lambda: ["Daily active users"]),
    ("f08-knowledge-base", "#view=kb", None,
     "The knowledge base browser: every technology with its scores and sources.",
     lambda: ["Next.js"]),
    ("e01-contradictory", "#preset=contradictory", "#out",
     "Contradictory inputs: warnings with the stated resolution.",
     lambda: _stack_names("contradictory")),
    ("e02-hipaa-zero-budget", "#preset=hipaa_telehealth&whatif=budget_monthly:0", "#out",
     "HIPAA with a zero budget: compliance is not relaxed, and a warning states the minimum compliant cost.",
     lambda: _stack_names("hipaa_telehealth", budget_monthly=0)),
    ("e03-dau-clamped", "#preset=startup_mvp&whatif=dau:-5", "#out",
     "A negative user count is replaced by a valid one and a warning says so.",
     lambda: ["Clamped to 0."]),
]
GALLERY = ["startup_mvp", "hipaa_telehealth", "india_ecommerce_scale", "iot_telemetry", "student_project", "content_site"]
for _p in GALLERY:
    SHOTS.append((f"gallery/{_p}", f"#preset={_p}", "#out", f"Sample result: {_p}.", (lambda p=_p: _stack_names(p))))


# The language-model features. Each needs a key; the act function clicks the button the shot is about and waits for the answer.
BRIEF = ("We are 3 students building a ticketing site for our college fest, about 20,000 visitors a day, "
         "₹5,000 a month for hosting. We know React and Node.")


def _act_brief(page) -> None:
    page.locator("#brief-text").fill(BRIEF)
    page.locator("#brief-btn").click()
    page.wait_for_selector("#brief-out .b-list", timeout=90000)


def _act_summary(page) -> None:
    page.locator("#sum-go").click()
    page.wait_for_selector("#summary .sum-badge", timeout=90000)


def _act_second(page) -> None:
    page.locator("#second-go").click()
    page.wait_for_selector("#second .so-t", timeout=90000)


SHOTS += [
    ("f09-describe-project", "#", ".brief",
     "Describe your project: the answers read from a description, each with its source and the words it came from.",
     lambda: ["answers filled", "20,000 visitors a day", "₹5,000 a month"]),
    ("f10-plain-summary", "#preset=hipaa_telehealth", "#summary",
     "The plain-English summary for the HIPAA example, badged as checked against the engine's facts.",
     lambda: ["checked against engine facts"]),
    ("f11-second-opinion", "#preset=hipaa_telehealth", "#second",
     "Second opinion: a language model's own stack graded by the rules; it disagrees on two layers and one of its picks is ruled out.",
     lambda: ["Second opinion", "ruled out"]),
]
# Shots that leave out panels which are empty until a model button is pressed (they would show only a button).
HIDE = {"f01-result-hipaa": ["#summary", "#second"]}
ACTS = {"f09-describe-project": _act_brief, "f10-plain-summary": _act_summary, "f11-second-opinion": _act_second}

CAPTIONS = {n: c for n, _l, _s, c, _e in SHOTS}
LINKS = {n: l for n, l, *_ in SHOTS}


def content_h(page, sel: str, box: dict) -> float:
    """Height of the element down to its lowest visible child, so no empty strip is printed under the content."""
    h = page.evaluate("""(s) => { const e = document.querySelector(s); let m = 0;
        e.querySelectorAll('*').forEach(c => { const r = c.getBoundingClientRect(); if (r.height > 0 && r.width > 0 && !c.closest('.cites')) m = Math.max(m, r.bottom); });
        const f = document.querySelector('footer.foot'), top = e.getBoundingClientRect().top;
        return Math.min(m - top + 20, f && f.getBoundingClientRect().top > top ? f.getBoundingClientRect().top - top : 1e9); }""", sel)  # never into the page footer
    return min(box["height"], max(h, 100))


def content_w(page, sel: str, box: dict) -> float:
    """Width of the element out to its rightmost visible child (a wide table or long word can overflow the element's own box),
    so nothing is cut at the right edge. Capped at the window width."""
    w = page.evaluate("""(s) => { const e = document.querySelector(s); const l = e.getBoundingClientRect().left; let m = e.getBoundingClientRect().right;
        e.querySelectorAll('*').forEach(c => { const r = c.getBoundingClientRect(); if (r.height > 0 && r.width > 0 && !c.closest('.cites')) m = Math.max(m, r.right, r.left + c.scrollWidth); });
        return m - l + 8; }""", sel)
    return min(max(box["width"], w), page.viewport_size["width"] - box["x"])


def cards_bottom(page, sel: str) -> float:
    """Distance from the top of the element to the bottom of the lowest pick card (plus any notes under the cards)."""
    return page.evaluate("""(s) => { const e = document.querySelector(s); let m = 0;
        e.querySelectorAll('.pick-b').forEach(b => { const c = b.closest('article, section, div'); const r = (b.parentElement.parentElement || c).getBoundingClientRect(); m = Math.max(m, r.bottom); });
        return m - e.getBoundingClientRect().top + 2; }""", sel)


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def python_for_server() -> str:
    if os.environ.get("SERVER_PYTHON"):  # a Python with the app's packages, when this script runs under another one
        return os.environ["SERVER_PYTHON"]
    for p in (ROOT / ".venv" / "Scripts" / "python.exe", ROOT / ".venv" / "bin" / "python"):
        if p.exists():
            return str(p)
    return sys.executable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="write nothing")
    ap.add_argument("--only", help="one shot name")
    a = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright is missing: pip install -r requirements-dev.txt", file=sys.stderr)
        return 2
    port = free_port()
    server = subprocess.Popen([python_for_server(), "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
                              cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mismatches, written = [], 0
    try:
        for _ in range(80):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1)
                break
            except OSError:
                time.sleep(0.5)
        else:
            print("server did not start", file=sys.stderr)
            return 1
        with sync_playwright() as pw:
            exe = os.environ.get("CHROME") or (CHROME_EXE if os.path.exists(CHROME_EXE) else None)
            browser = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch(channel="chrome")
            for name, link, sel, _cap, expect in SHOTS:
                if a.only and a.only != name:
                    continue
                if name in ACTS and not llm.available():
                    print(f"skipped  {name}: no language-model API key is set, so the model features cannot be shown")
                    continue
                page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=1.5)
                page.goto(f"http://127.0.0.1:{port}/?theme=light{link}")
                page.wait_for_selector("#out .pick-b, #view-kb .kb-sec", timeout=30000)
                page.wait_for_timeout(2000)
                if name in ACTS:
                    ACTS[name](page)
                    page.wait_for_timeout(800)
                for hidden in HIDE.get(name, []):
                    page.evaluate("(s) => { const e = document.querySelector(s); if (e) e.style.display = 'none'; }", hidden)
                if name.startswith("e"):  # edge cases: open the warnings list so the resolutions are on the picture
                    page.evaluate("document.querySelectorAll('#out details').forEach(d => { if (d.querySelector('.wb-more')) d.open = true; })")
                    page.wait_for_timeout(400)
                text = page.evaluate("document.body.innerText")
                missing = [t for t in expect() if t.lower() not in text.lower()]
                if missing:
                    mismatches.append((name, missing))
                    print(f"MISMATCH {name}: page lacks {missing}")
                else:
                    print(f"ok       {name}")
                if not a.check:
                    dest = OUT / f"{name}.png"
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if sel:
                        page.locator(sel).first.scroll_into_view_if_needed()
                        box = page.locator(sel).first.bounding_box()
                        sy = page.evaluate("window.scrollY")
                        height = content_h(page, sel, box)
                        if name.startswith("gallery/"):  # the picks and the cost only; the what-if sliders and links add nothing to a gallery
                            height = min(height, cards_bottom(page, sel))
                        clip = {"x": box["x"], "y": box["y"] + sy, "width": content_w(page, sel, box), "height": min(height, MAX_H)}
                        page.screenshot(path=str(dest), full_page=True, clip=clip)
                    else:
                        page.screenshot(path=str(dest))
                    written += 1
                page.close()
            if not a.only:  # phone widths must not scroll sideways
                for width in (320, 360, 390):
                    page = browser.new_page(viewport={"width": width, "height": 740})
                    page.goto(f"http://127.0.0.1:{port}/?theme=light#preset=hipaa_telehealth")
                    page.wait_for_selector("#out .pick-b", timeout=30000)
                    page.wait_for_timeout(1000)
                    sw = page.evaluate("document.documentElement.scrollWidth")
                    if sw > width:
                        mismatches.append((f"phone-{width}", [f"page is {sw} px wide"]))
                        print(f"MISMATCH phone width {width}: scrollWidth {sw}")
                    else:
                        print(f"ok       phone width {width}")
                    page.close()
            browser.close()
    finally:
        server.terminate()
    print(f"{written} images written, {len(mismatches)} mismatches")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
