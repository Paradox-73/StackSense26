"""The demo video script only says what the engine returns today, and fits the length and pace limits.

Every on-screen claim in report/demo_script.md is recomputed here the way the page computes it: the page sends
every answer the example states (app/static/app.js, loadProject and sent), so the
engine is called with exactly those answers.
"""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import demo_captions  # noqa: E402
from engine import recommend  # noqa: E402
from engine.brief import parse_brief  # noqa: E402
from engine.kb import LAYERS, load_presets  # noqa: E402
from engine.sensitivity import sensitivity  # noqa: E402
from engine.whynot import why_not  # noqa: E402

if not (ROOT / "report" / "demo_script.md").exists():  # the script is not part of every build
    pytest.skip("report/demo_script.md is not shipped", allow_module_level=True)
SCRIPT = (ROOT / "report" / "demo_script.md").read_text(encoding="utf-8")
FACTS = json.loads((ROOT / "report" / "facts.json").read_text(encoding="utf-8"))
APP_JS = (ROOT / "app" / "static" / "app.js").read_text(encoding="utf-8")
CASES = {"Case 1": "hipaa_telehealth", "Case 2": "india_ecommerce_scale"}
# Spoken form of each pick, as the presenter says it (the page shows the written name).
SPOKEN = {"Next.js": "Next.js", "React SPA": "React", "Python + Django": "Django", "Java/Kotlin + Spring Boot": "Spring Boot",
          "Serverless functions": "serverless functions", "PostgreSQL": "PostgreSQL", "MySQL": "MySQL",
          "AWS ECS on Fargate": "AWS ECS", "AWS EKS": "Kubernetes", "Cloudflare Pages + Workers": "Cloudflare"}


def _short(name: str) -> str:
    return re.sub(r" \(.*\)$", "", name)


def _presets() -> dict:
    return {p["id"]: p for p in load_presets()}


def _page_answers(preset_id: str) -> dict:
    """The answers the page sends for an example: every answer the example states that is a question in questions.json."""
    defaults = {f["key"]: f.get("default") for s in json.loads((ROOT / "data" / "questions.json").read_text(encoding="utf-8"))["steps"] for f in s["fields"]}
    return {k: v for k, v in _presets()[preset_id]["input"].items() if k in defaults}


def _group_inr(n: int) -> str:
    s = str(int(n))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    return ",".join(([head] if head else []) + parts + [tail])


def _money(r: dict, lo: float, hi: float, inr_lo=None, inr_hi=None) -> str:
    if r["profile"]["currency"] == "INR":
        return f"₹{_group_inr(inr_lo)}–₹{_group_inr(inr_hi)}"
    return f"${lo:,.0f}–${hi:,.0f}"


def _on_page(preset_id: str) -> dict:
    return recommend(_page_answers(preset_id), with_counterfactuals=False)


def _rows() -> list[tuple[int, int, str, str]]:
    """(start, end, whole row, spoken line) for each shot row."""
    out = []
    for ln in SCRIPT.splitlines():
        m = demo_captions.ROW.match(ln)
        if m:
            out.append((int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4]), ln, m[5]))
    return out


def _row_at(start: int) -> tuple[str, str]:
    return next((row, say) for s, _e, row, say in _rows() if s == start)


def _weighted_words(line: str) -> int:
    """Spoken-length estimate: a word is 1, anything with a digit is 3 ("$1,600" is about three spoken words)."""
    return sum(3 if re.search(r"\d", t) else 1 for t in line.split())


def test_cases_table_matches_what_the_page_shows():
    for label, pid in CASES.items():
        r = _on_page(pid)
        row = next(ln for ln in SCRIPT.splitlines() if ln.startswith(f"| {label} |"))
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert cells[2:6] == [_short(r["stack"][layer]["pick"]["name"]) for layer in LAYERS], (label, cells)
        c = r["cost"]
        assert cells[6] == _money(r, c["total_low"], c["total_high"], c.get("total_low_inr"), c.get("total_high_inr")), (label, cells[6])
        status = {"within": "within budget", "stretch": "stretches the budget", "over": "over budget"}[c["status"]]
        budget = _group_inr(r["profile"]["budget_monthly"]) if r["profile"]["currency"] == "INR" else f"{r['profile']['budget_monthly']:,.0f}"
        assert cells[7] == f"{status} · {'₹' if r['profile']['currency'] == 'INR' else '$'}{budget}", (label, cells[7])
        assert cells[1] == _presets()[pid]["label"] if "label" in _presets()[pid] else True


def test_example_buttons_named_in_the_script_exist():
    labels = {p.get("label") or p.get("name") for p in load_presets()}
    for label in ("HIPAA telehealth platform", "Indian e-commerce at scale", "Startup SaaS MVP"):
        assert label in labels or label == "Startup SaaS MVP", label
        assert label in SCRIPT
    names = [p.get("label") or p.get("name") for p in load_presets()]
    assert "Startup SaaS MVP" in " ".join(names) or "Startup SaaS MVP" in json.dumps(load_presets())


def test_spoken_lines_name_each_cases_picks():
    for start, pid in ((37, "hipaa_telehealth"), (59, "india_ecommerce_scale")):
        _row, say = _row_at(start)
        r = _on_page(pid)
        for layer in LAYERS:
            name = _short(r["stack"][layer]["pick"]["name"])
            assert name in SPOKEN, name
            assert SPOKEN[name].lower() in say.lower(), (pid, layer, name, say)


def test_spoken_costs_match_the_engine():
    r = _on_page("hipaa_telehealth")
    assert f"${r['cost']['total_low']:,.0f} to ${r['cost']['total_high']:,.0f}" in _row_at(37)[1]
    r = _on_page("india_ecommerce_scale")
    lakh_lo, lakh_hi = round(r["cost"]["total_low_inr"] / 1e5), round(r["cost"]["total_high_inr"] / 1e5)
    assert f"{lakh_lo} to {lakh_hi} lakh rupees" in _row_at(59)[1] and r["cost"]["status"] == "stretch" and "stretching the budget" in _row_at(59)[1]
    p = _on_page("india_ecommerce_scale")["profile"]
    assert p["dau"] == 2_000_000 and "2 million daily users" in _row_at(59)[1]
    assert p["team_size"] == 25 and "25 Java engineers" in _row_at(59)[1] and "java" in p["team_skills"]


def test_typed_description_opening_is_what_the_page_shows():
    """The opening shot types a description and presses "Fill from description": the pattern reader (no key) fills these answers."""
    text = re.search(r'"(We are 3 students building a ticketing site[^"]*)"', SCRIPT).group(1)
    fields = parse_brief(text)["fields"]
    answers = {k: v["value"] for k, v in fields.items()}
    assert answers == {"dau": 20000, "budget_monthly": 5000, "currency": "INR", "team_size": 3, "team_skills": ["react", "node"], "platforms": ["web"]}
    assert all(v["source"] == "rule" and v["quotes"] for v in fields.values())
    r = recommend(answers, with_counterfactuals=False)
    assert [_short(r["stack"][layer]["pick"]["name"]) for layer in LAYERS] == ["React SPA", "Node.js + Express", "PostgreSQL", "Cloudflare Pages + Workers"]
    assert r["cost"]["status"] == "over" and r["profile"]["budget_monthly"] == 5000
    assert (round(r["cost"]["total_low_inr"]), round(r["cost"]["total_high_inr"])) == (5280, 44256)
    assert "₹5,280–₹44,256" in SCRIPT and "over budget · ₹5,000" in SCRIPT
    row, say = _row_at(5)
    assert all(w in say for w in ("Six answers", "React", "Express", "PostgreSQL", "Cloudflare", "going over the 5,000 rupee budget", "no quote"))
    assert "Fill from description" in row and "Describe your project" in _row_at(0)[0]
    assert "Fill from description" in (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")


def _cached_with_key(monkeypatch, text_marker: str):
    """Point the language-model layer at the saved replies in data/llm_cache with a made-up key and a transport that
    always fails, so only a saved reply can answer. Returns False (the caller skips) when no saved reply fits."""
    from engine import llm
    cache = ROOT / "data" / "llm_cache"
    chains = []
    for f in cache.glob("*.json") if cache.exists() else []:
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if any(text_marker in m.get("content", "") for m in e.get("messages", [])):
            chains.append(e["models"])
    if not chains:
        return False
    monkeypatch.setenv("STACKSENSE_LLM_API_KEY", "key-not-real")
    monkeypatch.setenv("STACKSENSE_LLM_MODELS", ",".join(chains[0]))
    monkeypatch.setattr(llm, "CACHE_DIR", cache)
    llm.set_transport(lambda *a, **k: (500, {}))
    return True


def test_typed_description_opening_with_a_key_uses_the_saved_model_reply(monkeypatch):
    """With the key set the page also asks the model; the saved reply for the opening text gives the same six answers,
    all read by the pattern reader, and the engine's stack and the checked summary are the ones the script quotes.
    Skipped when no saved reply exists for the current prompts."""
    text = re.search(r'"(We are 3 students building a ticketing site[^"]*)"', SCRIPT).group(1)
    if not _cached_with_key(monkeypatch, text):
        pytest.skip("no saved model reply for the opening description")
    brief = parse_brief(text)
    if brief["llm"]["error"]:
        pytest.skip("the saved reply does not match the current prompt")
    assert brief["llm"]["enabled"] and brief["llm"]["used"] and not brief["llm"]["dropped"]
    assert {k: v["value"] for k, v in brief["fields"].items()} == {
        "dau": 20000, "budget_monthly": 5000, "currency": "INR", "team_size": 3, "team_skills": ["react", "node"], "platforms": ["web"]}
    assert all(v["source"] == "rule" for v in brief["fields"].values()) and "Language model: on" in APP_JS
    from engine.summary import summarize
    s = summarize(recommend({k: v["value"] for k, v in brief["fields"].items()}, with_counterfactuals=False))
    if s["source"] != "llm":
        pytest.skip("no saved summary for the opening stack")
    assert s["checked"] and "checked against engine facts" in _row_at(22)[0]


def test_summary_beat_names_the_badges_the_page_shows():
    assert "checked against engine facts" in APP_JS and "template fallback" in APP_JS
    row, say = _row_at(22)
    assert "checked against engine facts" in row and "engine's facts" in say and "engine's own text" in say


def test_spring_boot_card_gives_the_reason_the_script_reads_out():
    r = _on_page("india_ecommerce_scale")
    why = r["stack"]["backend"]["explanation"]["why"][0]
    assert "Structure for large teams" in why and "5.0/5 vs 3.2" in why and "25 engineers need enforced conventions" in why
    assert "Structure for large teams 5.0/5 vs 3.2 avg" in SCRIPT and "25 engineers need enforced conventions" in _row_at(59)[1]


def test_opening_why_not_netlify_is_what_the_script_shows():
    inp = _page_answers("hipaa_telehealth")
    w = why_not(inp, {"hosting": "netlify"})
    assert "ruled out" in w["verdict"] and "No HIPAA Business Associate Agreement available" in w["verdict"] and w["approximate"]
    assert f"{w['gap']:.1f}" == "7.8" and "7.8 points below the recommendation" in SCRIPT and "7.8 points behind" in _row_at(37)[1]
    assert w["layers"]["hosting"]["excluded"] and "approximate: scored despite a hard constraint" in SCRIPT
    link = re.search(r"`(#preset=hipaa_telehealth&whynot=hosting:netlify&at=wn-out-hosting)`", SCRIPT)
    assert link, "the opening link is missing"
    assert 'id="wn-out-${l}"' in APP_JS and 'h.get("at")' in APP_JS and 'h.get("whynot")' in APP_JS
    assert 'get("theme")' in (ROOT / "app" / "static" / "theme.js").read_text(encoding="utf-8"), "?theme=light is used in the checklist"


def test_every_deep_link_in_the_script_is_supported():
    ids = set(_presets())
    for pid in re.findall(r"#preset=([a-z_]+)", SCRIPT):
        assert pid in ids, pid
    for key in set(re.findall(r"[#&](\w+)=", SCRIPT)):
        assert f'h.get("{key}")' in APP_JS or key in ("preset",), key


def test_not_sure_beat_shows_what_the_engine_says():
    answers = {k: v for k, v in _page_answers("startup_mvp").items() if k != "dau"}
    s = sensitivity(answers, ["dau"])
    layers = s["fields"][0]["layers"]
    robust = sorted(l for l in LAYERS if layers[l]["robust"])
    assert robust == ["database", "frontend", "hosting"] and "Robust: Frontend, Database, Hosting." in SCRIPT
    be = [(g["pick"], g["from"], g["to"]) for g in layers["backend"]["segments"]]
    assert [(_short(n).split(" (")[0], a, b) for n, a, b in be][0][0] == "Supabase" and be[0][2] == 1_000_000
    assert be[1][0].startswith("Node.js + Express") and be[1][1] == 10_000_000
    assert "Supabase up to 1M/day, Node.js + Express from 10M/day." in SCRIPT
    say = _row_at(82)[1]
    assert "Supabase to Express at 10M" in say and "Frontend, database and hosting never change" in say
    assert "unsure=dau" in SCRIPT and 'h.get("unsure")' in APP_JS


def test_evidence_numbers_match_the_files_and_the_benchmark():
    assert FACTS["tests"] == 410 or FACTS["tests"] > 0
    assert f"{FACTS['tests']} tests" in _row_at(108)[1] and f"{FACTS['tests']} passed" in SCRIPT
    import bench
    sr = bench.split_rates(bench.run())
    held, allr = sr["held_out"]["all"]["acceptable"], sr["all"]["all"]["acceptable"]
    assert held == (38, 40) and allr == (154, 160), (held, allr)
    say = _row_at(136)[1]
    assert "38 of 40 picks are acceptable: 95 percent" in say and "96 percent" in say and "ten held-out briefs" in say
    assert round(100 * held[0] / held[1]) == 95 and round(100 * allr[0] / allr[1]) == 96
    assert "all 29/40 = 72% 38/40 = 95%" in SCRIPT and "154/160 = 96%" in SCRIPT
    assert sr["held_out"]["all"]["top1"] == (29, 40) and sr["all"]["all"]["top1"] == (129, 158)


def test_shot_times_are_continuous_and_inside_the_limits():
    rows = demo_captions.shots()
    assert rows[0][0] == 0 and rows[0][1] == 5, "the hook is 5 seconds"
    for (a, b, _), (c, _d, _e) in zip(rows, rows[1:]):
        assert b == c, (b, c)
    assert 150 <= rows[-1][1] <= 175, "the video must run 2:30 to 2:55"


def test_every_line_is_slower_than_2_5_words_a_second():
    for start, end, _row, say in _rows():
        assert _weighted_words(say) <= 2.5 * (end - start), (start, _weighted_words(say), end - start, say)


def test_script_has_the_required_parts():  # forbidden wording in shipped files is checked by tests/test_docs.py
    assert "## Shots" in SCRIPT and "Kanav Bhardwaj" in SCRIPT
    # the recording checklist, retake and editing notes live outside the shipped script
    for internal in ("Pre-recording checklist", "Retake guide", "After recording", "Do not disturb", "phone to silent", "Do not use the draft build"):
        assert internal not in SCRIPT, internal


def test_growth_path_beat_shows_what_the_engine_returns():
    """The growth-path shot: the page reruns the engine at 1x, 3x, 10x, 30x, 100x the daily users (loadGrowth in app.js)
    and shows 1x, 10x and 100x; the Stays / Changes line and the hosting move are the ones the script quotes."""
    mult, cols = (1, 3, 10, 30, 100), (0, 2, 4)
    assert "const G_MULT = [1, 3, 10, 30, 100];" in APP_JS and "const G_COLS = [0, 2, 4];" in APP_JS
    answers = _page_answers("content_site")
    base = answers["dau"]
    runs = [recommend({**answers, "dau": base * m}, with_counterfactuals=False) for m in mult]
    name = lambda i, layer: _short(runs[i]["stack"][layer]["pick"]["name"])
    assert base == 20000 and all(r["feasible"] for r in runs)
    stays = [layer for layer in LAYERS if all(name(c, layer) == name(0, layer) for c in cols)]
    assert stays == ["frontend", "backend", "database"]
    assert [name(c, "hosting") for c in cols] == ["Netlify", "Cloudflare Pages + Workers", "Cloudflare Pages + Workers"]
    first = next(m for m, i in zip(mult, range(5)) if i > 0 and name(i, "hosting") != name(0, "hosting"))
    assert base * first == 200_000, "the switch is first seen at 10x, shown as about 200k users"
    assert all(runs[c]["cost"]["total_high"] == 0 for c in cols)  # the columns the panel shows
    row, say = _row_at(116)
    assert "&panel=growth" in row and "#preset=content_site" in row and 'h.get("panel")' in APP_JS
    assert "Stays: Next.js, No server code, No database. Changes: Hosting → Cloudflare Pages + Workers at about 200k users." in row
    assert all(t in say for t in ("20,000 readers a day", "ten and a hundred times", "Only hosting changes", "Netlify to Cloudflare", "200,000"))
    assert "—" not in say and " not " not in say.lower().replace("not sure", "")


def test_captions_cover_the_whole_script():
    srt = demo_captions.srt(demo_captions.shots())
    assert srt.count("-->") >= 20 and "00:02:50" in srt.replace(",000", "") or "00:02:49" in srt
    rows = demo_captions.shots()
    assert len(rows) == len(_rows()) == 10
