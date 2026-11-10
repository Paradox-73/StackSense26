"""The LLM-off switch (problem statement 5.1) and the scenario command line (FR2, FR8): STACKSENSE_LLM=off stops
every model request and saved answer, the stack is the same with the switch on or off, and the CLI writes the
section 4 output for each scenario file."""
import json
from pathlib import Path

import pytest

import cli
from engine import llm, recommend
from engine.kb import LAYERS, load_presets
from engine.standard import run

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = sorted((ROOT / "scenarios" / "public").glob("P*.json"))
MSG = [{"role": "user", "content": "hello"}]


@pytest.mark.parametrize("value", ["off", "OFF", "0", "false", "no"])
def test_switch_values_turn_the_model_off(value, monkeypatch):
    monkeypatch.setenv("STACKSENSE_LLM", value)
    assert llm.switched_off() and not llm.available()


def test_switched_off_sends_no_request_and_serves_no_saved_answer(fake_llm, monkeypatch, tmp_path):
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    fake = fake_llm({"ok": 1}, {"ok": 2})
    assert llm.chat(MSG).text and len(fake.calls) == 1  # answered and saved
    monkeypatch.setenv("STACKSENSE_LLM", "off")
    with pytest.raises(llm.LLMError, match="switched off"):
        llm.chat(MSG)
    assert len(fake.calls) == 1


def _stacks():
    std = [run(json.loads(p.read_text(encoding="utf-8")))["stack"] for p in PUBLIC]
    app = [{l: recommend(x["input"], with_counterfactuals=False)["stack"][l]["pick"]["id"] for l in LAYERS}
           for x in load_presets()]
    return json.dumps([std, app], sort_keys=True)


def test_stack_is_identical_with_the_model_on_and_off(fake_llm, monkeypatch):
    fake_llm(*[{"frontend": "flutter", "summary": "x"}] * 200)
    assert llm.available() and not llm.switched_off()  # "on" really is on, whatever the shell sets
    on = _stacks()
    monkeypatch.setenv("STACKSENSE_LLM", "off")
    assert _stacks() == on


def test_cli_writes_one_output_file_per_scenario(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("STACKSENSE_LLM", "on")  # restored after the test, though --no-llm switches it off
    assert cli.main(["--scenario", str(ROOT / "scenarios" / "public"), "--out", str(tmp_path), "--no-llm"]) == 0
    assert sorted(f.name for f in tmp_path.iterdir()) == [f"P{i}_output.json" for i in range(1, 7)]
    for p in PUBLIC:
        written = json.loads((tmp_path / f"{p.stem}_output.json").read_text(encoding="utf-8"))
        assert written == run(json.loads(p.read_text(encoding="utf-8")))
    assert "P4" in capsys.readouterr().out


def test_cli_runs_each_scenario_of_an_array_file(tmp_path, capsys):
    """The organisers share the public scenarios as one JSON array: each element gets its own output file, or the
    printed output is a JSON array."""
    docs = [json.loads(p.read_text(encoding="utf-8")) for p in PUBLIC]
    del docs[1]["scenario_id"]
    src = tmp_path / "public_scenarios.json"
    src.write_text(json.dumps(docs), encoding="utf-8")
    assert cli.main(["--scenario", str(src), "--out", str(tmp_path / "out")]) == 0
    names = sorted(f.name for f in (tmp_path / "out").iterdir())
    assert names == ["P1_output.json", "P3_output.json", "P4_output.json", "P5_output.json", "P6_output.json",
                     "public_scenarios_2_output.json"], names
    assert json.loads((tmp_path / "out" / "P4_output.json").read_text(encoding="utf-8")) == run(docs[3])
    capsys.readouterr()
    assert cli.main(["--scenario", str(src)]) == 0
    assert json.loads(capsys.readouterr().out) == [run(d) for d in docs]
    assert cli.main(["--scenario", str(src), "--out", str(tmp_path / "all.json")]) == 0
    assert json.loads((tmp_path / "all.json").read_text(encoding="utf-8")) == [run(d) for d in docs]


def test_cli_reports_a_file_that_is_not_json_as_invalid_input(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text('{"scenario_id": "x", ', encoding="utf-8")
    assert cli.main(["--scenario", str(bad)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["status"] == "invalid_input" and out["stack"] is None
    assert out["validation_errors"][0]["field"] == "(file)"


def test_committed_outputs_match_the_engine():
    """outputs/P*_output.json are the files for the submission folder; they must be what the engine returns now."""
    for p in PUBLIC:
        committed = json.loads((ROOT / "outputs" / f"{p.stem}_output.json").read_text(encoding="utf-8"))
        assert committed == run(json.loads(p.read_text(encoding="utf-8"))), f"rerun: python cli.py --scenario {p}"


def test_each_public_scenario_is_answered_well_within_ten_seconds():
    """Statement 2.2: a recommendation within about 10 seconds on a normal laptop. Processor time of this process,
    so other programs do not fail the test; one scenario takes well under a second."""
    import time
    for p in PUBLIC:
        doc = json.loads(p.read_text(encoding="utf-8"))
        t = time.process_time()
        run(doc)
        assert time.process_time() - t < 5.0, p.stem


def test_cli_reads_utf16_files_and_keeps_outputs_with_the_same_id_apart(tmp_path, capsys):
    src = tmp_path / "in"
    src.mkdir()
    text = (ROOT / "scenarios" / "public" / "P2.json").read_text(encoding="utf-8")
    (src / "a.json").write_bytes(text.encode("utf-16"))  # what Windows PowerShell's > writes
    (src / "b.json").write_text(text, encoding="utf-8")
    (src / "c.json").write_bytes(b'{"scenario_id": "x", "project": "caf\xe9"}')  # Latin-1 byte, not UTF-8
    assert cli.main(["--scenario", str(src), "--out", str(tmp_path / "out")]) == 0
    names = sorted(f.name for f in (tmp_path / "out").iterdir())
    assert names == ["P2_b_output.json", "P2_output.json", "x_output.json"], names
    assert json.loads((tmp_path / "out" / "x_output.json").read_text(encoding="utf-8"))["status"] == "invalid_input"


def test_a_folder_run_survives_a_file_nested_past_the_recursion_limit_and_a_file_that_fails(tmp_path, capsys, monkeypatch):
    import engine.standard
    src = tmp_path / "in"
    src.mkdir()
    (src / "a_deep.json").write_text("[" * 3000, encoding="utf-8")
    (src / "b_boom.json").write_text('{"scenario_id": "boom"}', encoding="utf-8")
    (src / "c_ok.json").write_text((ROOT / "scenarios" / "public" / "P1.json").read_text(encoding="utf-8"), encoding="utf-8")
    real = engine.standard.run

    def run_or_fail(doc):
        if isinstance(doc, dict) and doc.get("scenario_id") == "boom":
            raise RuntimeError("injected failure")
        return real(doc)
    monkeypatch.setattr(engine.standard, "run", run_or_fail)
    assert cli.main(["--scenario", str(src), "--out", str(tmp_path / "out")]) == 1
    deep = json.loads((tmp_path / "out" / "a_deep_output.json").read_text(encoding="utf-8"))
    assert deep["status"] == "invalid_input" and deep["validation_errors"][0]["field"] == "(file)"
    assert json.loads((tmp_path / "out" / "P1_output.json").read_text(encoding="utf-8"))["status"] == "ok"
    assert "b_boom.json: not run (RuntimeError: injected failure)" in capsys.readouterr().err
