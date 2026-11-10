"""tools/llm_baseline.py: scoring, resuming and stopping on a quota error, with a fake transport."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import bench  # noqa: E402
import llm_baseline  # noqa: E402


def test_picks_outside_the_allowed_ids_are_invalid_and_score_as_misses():
    opts = llm_baseline.allowed_options()
    picks = llm_baseline.read_picks({"frontend": "nextjs", "backend": "made_up", "database": "postgres", "hosting": None}, opts)
    assert picks == {"frontend": "nextjs", "backend": None, "database": "postgres", "hosting": None}
    brief = bench.load_key()["briefs"][0]
    row = llm_baseline.score_picks(brief, picks)
    assert row["layers"]["backend"]["ok"] is False and row["layers"]["backend"]["pick"] is None
    assert row["layers"]["frontend"]["top1"] == (brief["layers"]["frontend"]["best"] == "nextjs")


def test_picking_the_keys_best_ids_scores_full_marks():
    brief = bench.load_key()["briefs"][0]
    picks = {layer: brief["layers"][layer]["best"] for layer in llm_baseline.LAYERS}
    row = llm_baseline.score_picks(brief, picks)
    assert all(c["top1"] and c["ok"] for c in row["layers"].values())


def test_none_ids_count_as_the_keys_none():
    brief = {"id": "T", "title": "t", "held_out": False,
             "layers": {"frontend": {"best": "nextjs", "acceptable": ["nextjs"]}, "backend": {"best": "none", "acceptable": ["none"]},
                        "database": {"best": "none", "acceptable": ["none"]}, "hosting": {"best": "vercel", "acceptable": ["vercel"]}}}
    row = llm_baseline.score_picks(brief, {"frontend": "nextjs", "backend": "no_custom_backend", "database": "none_static", "hosting": "vercel"})
    assert all(c["ok"] for c in row["layers"].values())


def test_run_is_resumable_and_stops_on_quota(fake_llm, tmp_path):
    key = bench.load_key()["briefs"]
    out = tmp_path / "baseline.json"
    answer = {"frontend": "nextjs", "backend": "express", "database": "postgres", "hosting": "vercel"}
    fake = fake_llm(answer)
    llm_baseline.run(str(out), limit=2, out=lambda *_: None)
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert list(saved["briefs"]) == [b["id"] for b in key[:2]] and saved["done"] == 2
    assert saved["briefs"][key[0]["id"]]["model"] == "model/a:free" and saved["rates"]["all"]["all"]["acceptable"][1] == 8
    assert len(fake.calls) == 2

    fake2 = fake_llm(answer)
    llm_baseline.run(str(out), limit=1, out=lambda *_: None)  # skips the two finished briefs
    assert json.loads(out.read_text(encoding="utf-8"))["done"] == 3 and len(fake2.calls) == 1

    messages = []
    fake_llm((429, {}))
    llm_baseline.run(str(out), out=messages.append)  # quota exhausted: keeps what is done, says so
    assert json.loads(out.read_text(encoding="utf-8"))["done"] == 3 and "stopped at" in messages[0]


def test_prompt_lists_only_knowledge_base_ids():
    msgs = llm_baseline.build_messages("a brief", llm_baseline.allowed_options())
    assert "hosting:" in msgs[1]["content"] and "nextjs = Next.js (React)" in msgs[1]["content"]


def test_grading_a_row_finds_breaks_and_grades_the_engines_own_stack_clean():
    brief = next(b for b in bench.load_key()["briefs"] if b["id"] == "A01")  # the LLM chose flutter for a web-only target
    row = llm_baseline.score_picks(brief, {"frontend": "flutter", "backend": "express", "database": "postgres", "hosting": "vercel"})
    llm_baseline.grade_row(brief, row)
    assert "frontend" in row["grade"]["breaks"] and row["engine_grade"]["breaks"] == {} and row["engine_grade"]["gap"] == 0
    saved = {"briefs": {"A02": row}}
    m = llm_baseline.metrics(saved)
    assert m["graded"] == 1 and m["llm_breaks"]["briefs"] == 1 and m["engine_check"]["breaks"] == 0


def test_repeat_is_resumable_bypasses_the_cache_and_measures_agreement(fake_llm, tmp_path):
    first, rep = tmp_path / "first.json", tmp_path / "rep.json"
    answer = {"frontend": "nextjs", "backend": "express", "database": "postgres", "hosting": "vercel"}
    fake = fake_llm(answer)
    llm_baseline.run(str(first), limit=3, out=lambda *_: None)
    assert len(fake.calls) == 3
    fake2 = fake_llm(answer)
    llm_baseline.run_repeat(str(rep), str(first), limit=2, out=lambda *_: None)
    assert len(fake2.calls) == 2  # the cache would have answered these for free: it is bypassed
    llm_baseline.run_repeat(str(rep), str(first), out=lambda *_: None)  # resumes: only the third brief is asked
    assert len(fake2.calls) == 3
    m = llm_baseline.repeat_metrics(llm_baseline.load_saved(str(first)), llm_baseline.load_saved(str(rep)))
    assert m["asked"] == 3 and m["same_stack"] == 3 and m["same_model"] == 3
    assert llm_baseline.repeat_metrics(llm_baseline.load_saved(str(first)), None) == {"asked": 0}


def test_show_prints_every_metric_without_network(tmp_path):
    lines = []
    saved = llm_baseline.load_saved(str(llm_baseline.OUT_PATH))
    llm_baseline.show(saved, out=lines.append)
    text = "\n".join(lines)
    assert "hard-requirement breaks" in text and "over budget" in text and "repeatability: not measured yet" in text
