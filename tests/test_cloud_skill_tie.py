"""A team that lists a cloud as a skill wins ties for that cloud before the hiring pool decides, and a pick that
scores below another stack always says which rule chose it."""
from engine import recommend
from engine.stack import TIE_BREAKERS, pick_tied, tie_reason


def _layer(id_, provider, hiring, lock_in=2):
    return {"id": id_, "name": id_, "score": 80.0, "raw": {"skill_fit": 3.0}, "adjustments": [],
            "item": {"id": id_, "provider": provider, "lock_in": lock_in, "scores": {"hiring": hiring}}}


def _combo(host, score):
    return {"picks": {"frontend": _layer("react_spa", "", 5), "backend": _layer("fastapi", "", 4),
                      "database": _layer("postgres", "", 5), "hosting": host},
            "rules": [], "score": score, "no_skills": False, "no_fe_skills": False, "lock_in_ok": False,
            "defaulted": set(), "cloud_skills": frozenset({"aws"})}


def test_team_cloud_decides_before_hiring_pool():
    order = [attr for _, attr, _ in TIE_BREAKERS]
    assert order.index("cloud_skill") < order.index("hiring")
    fly = _combo(_layer("flyio", "flyio", 3, lock_in=1), 80.6)  # higher score, lower lock-in
    ecs = _combo(_layer("aws_ecs", "aws", 4, lock_in=3), 80.0)
    win = pick_tied([fly, ecs])
    assert win is ecs
    assert "team's cloud" in tie_reason(ecs, fly)


def test_lower_scoring_pick_names_its_rule():
    for inp in ({"app_type": "iot_telemetry", "dau": 20_000, "budget_monthly": 500, "team_skills": ["aws"],
                 "compliance": ["soc2"], "team_size": 2},
                {"app_type": "saas", "dau": 200_000, "budget_monthly": 100, "team_skills": ["python", "aws"],
                 "team_size": 2}):
        r = recommend(inp, with_counterfactuals=False)
        tb = r["tie_break"]
        assert tb and tb["margin"] > 0 and tb["decided_by"]
        for layer in r["stack"].values():
            vs = layer["explanation"].get("vs_runner_up")
            if vs and vs["margin"] < 0:
                assert "chosen by the" in vs["text"] or "The tie went to" in vs["text"], vs["text"]
