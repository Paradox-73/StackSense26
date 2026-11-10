import time

from engine.kb import LAYERS, field_specs, load_presets
from engine.recommender import _picks, _core
from engine.sensitivity import next_questions

ANS = {"app_type": "saas", "dau": 10000, "budget_monthly": 100, "team_size": 3, "team_skills": ["python"]}


def test_ranked_questions_really_change_a_pick():
    r = next_questions(ANS)
    assert r["ranked"], "a short answer set must leave something open"
    base = _picks(_core(ANS))
    for row in r["ranked"][:3]:
        assert row["can_change"] and set(row["can_change"]) <= set(LAYERS)
    assert r["base"] == {l: base.get(l) for l in LAYERS}


def test_questions_declared_settled_change_nothing():
    r = next_questions(ANS)
    specs = field_specs()
    from engine.sensitivity import options_for
    base = _picks(_core(ANS))
    for row in r["settled_questions"][:4]:
        for _l, v in options_for(row["key"], specs[row["key"]]):
            assert _picks(_core({**ANS, row["key"]: v})) == base, row["key"]


def test_same_answers_same_order():
    assert next_questions(ANS)["ranked"] == next_questions(dict(reversed(list(ANS.items()))))["ranked"]


def test_answered_and_implied_questions_are_not_asked():
    r = next_questions({"app_type": "mobile_first"})
    keys = {x["key"] for x in r["ranked"] + r["settled_questions"]}
    assert "app_type" not in keys and "platforms" not in keys and "platforms" in r["locked"]


def test_ask_next_card_is_fast_enough():
    """About 90 engine runs: 1-2 s of processor time on the development machine in one process
    (3-6 s before the speed-up), depending on load. The clock is this process's processor time, not
    wall time, so other programs competing for the processor do not fail the test. The bound is
    about three times the measured time, so a slow computer passes. Asking again with the same
    answers is served from the cache."""
    from engine import sensitivity
    for answers in (ANS, {}):
        sensitivity._NEXT_CACHE.clear()
        t = time.process_time()
        r = next_questions(answers)
        elapsed = time.process_time() - t
        assert r["runs"] > 50
        # One run costs about 0.07-0.12 s on a 2026 laptop, so the ~90 runs take 6-12 s on one core; the page spreads them over worker processes.
        assert elapsed < 15.0, f"{elapsed:.1f} s of processor time for {r['runs']} runs"
        t = time.process_time()
        assert next_questions(answers) == r
        assert time.process_time() - t < 1.0, "a repeated question set must come from the cache"


def test_worker_processes_give_the_same_answer():
    """Spreading the runs over worker processes must not change the result."""
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor
    from engine import sensitivity
    sensitivity._NEXT_CACHE.clear()
    serial = next_questions(ANS)
    sensitivity._NEXT_CACHE.clear()
    with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context("spawn")) as pool:
        assert next_questions(ANS, pool) == serial


def test_pruned_search_returns_the_same_top_stacks():
    """The growth path asks the stack search only for stacks within a window of the top one; the window
    keeps the best stacks exactly as the full search returns them, in the same order."""
    from engine.kb import load_kb
    from engine.profile import derive, normalize
    from engine.recommender import WALK_WINDOW, _score_layers
    from engine.scoring import build_weights
    from engine.stack import search
    kb = load_kb()
    for pr in [p["input"] for p in load_presets()]:
        p, assumptions, warnings = normalize(pr)
        d = derive(p, assumptions, warnings)
        scored, _, _ = _score_layers(kb, p, d, build_weights(p, d))
        full = search(scored, kb["rules"], p, d)
        part = search(scored, kb["rules"], p, d, window=WALK_WINDOW)
        top = full[0]["score"]
        want = [c for c in full if top - c["score"] <= WALK_WINDOW]
        assert [(c["score"], [c["picks"][l]["id"] for l in LAYERS]) for c in part] ==                [(c["score"], [c["picks"][l]["id"] for l in LAYERS]) for c in want]
