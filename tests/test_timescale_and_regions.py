"""TimescaleDB's strengths (hypertables partitioned by time, compression, continuous aggregates) need
time-series data; without it the store is PostgreSQL plus an extension. A managed database from another
vendor than the app's host is created in the host's region."""
import json
from copy import deepcopy
from pathlib import Path

from engine import recommend
from engine.kb import load_kb
from engine.profile import derive, normalize
from engine.scoring import data_fit, shape_models

AUDIT = Path(__file__).resolve().parent / "scenarios_extra"
TS, PG = load_kb()["index"]["timescaledb"], load_kb()["index"]["postgres"]


def _scenario(name):
    return next(s["input"] for s in json.loads((AUDIT / "consumer.json").read_text(encoding="utf-8")) if s["name"] == name)


def _pd(raw):
    p, a, w = normalize(deepcopy(raw))
    return p, derive(p, a, w)


def test_timescale_fits_like_postgres_without_time_series_data():
    p, d = _pd({"app_type": "analytics_dashboard", "data_shapes": ["analytical", "relational"]})
    assert shape_models(TS, d)["analytical"] == PG["models"]["analytical"]
    assert data_fit(TS, p, d) < data_fit(PG, p, d)
    p, d = _pd({"app_type": "iot_telemetry", "data_shapes": ["time_series", "analytical"]})
    assert shape_models(TS, d) == TS["models"]
    assert data_fit(TS, p, d) > data_fit(PG, p, d)


def test_startup_analytics_dashboard_without_time_series_gets_postgres():
    r = recommend(_scenario("S23_startup_analytics_dashboard"), with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "postgres"


def test_time_series_dashboard_keeps_timescale_and_is_told_where_to_put_it():
    inp = dict(_scenario("S23_startup_analytics_dashboard"), data_shapes=["time_series", "analytical", "relational"])
    r = recommend(inp, with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "timescaledb"
    host = r["stack"]["hosting"]["pick"]["name"]
    if host == "Render":  # a host without an India region: the database goes to the host's region
        assert any("Singapore, not Mumbai" in x for x in r["stack"]["database"]["explanation"]["risks"])


def test_no_region_note_when_the_host_runs_the_database():
    r = recommend({"app_type": "saas", "dau": 2000, "budget_monthly": 300, "regions": ["india"],
                   "cloud_preference": "aws", "team_skills": ["python", "aws"]}, with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "postgres"
    assert not any("separate service" in x for x in r["stack"]["database"]["explanation"]["risks"])


def test_region_note_names_the_hosts_nearest_region():
    from engine.recommender import _db_region_note
    kb = load_kb()["index"]
    p, _ = _pd({"regions": ["india"]})
    stack = {"database": TS, "hosting": kb["render"], "backend": kb["fastapi"]}
    assert "Singapore, not Mumbai" in _db_region_note(p, stack, None)
    assert _db_region_note(p, dict(stack, database=PG), None) is None  # Render runs PostgreSQL itself
    assert _db_region_note(p, dict(stack, hosting=kb["aws_ecs"]), None) and \
        "has no" not in _db_region_note(p, dict(stack, hosting=kb["aws_ecs"]), None)


def test_without_shape_is_validated():
    from engine.kb import validate_kb
    kb = deepcopy(load_kb())
    kb["database"] = [dict(it, without_shape=dict(it["without_shape"], shape="timeseries")) if it["id"] == "timescaledb" else it
                      for it in kb["database"]]
    assert any("without_shape" in x for x in validate_kb(kb))
    assert validate_kb() == []
