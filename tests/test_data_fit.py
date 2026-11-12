"""A database is never the primary store for data it does not fit, and in-memory stores are caches."""
import json
from pathlib import Path

import pytest

from engine import recommend

AUDIT = Path(__file__).parent / "scenarios_extra"


def _scenario(prefix):
    for f in AUDIT.glob("*.json"):
        for s in json.loads(f.read_text(encoding="utf-8")):
            if s["name"].startswith(prefix):
                return s["input"]
    raise KeyError(prefix)


@pytest.mark.parametrize("name", ["S03", "E07", "S08", "S21"])
def test_firestore_not_chosen_where_it_does_not_fit(name):
    """Relational course data (S03), 2,500 writes/s telemetry (E07), 1M-DAU chat (S08), 80 ms game (S21)."""
    r = recommend(_scenario(name), with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] != "firestore"


def test_primary_fit_of_one_is_excluded():
    r = recommend({"data_shapes": ["relational"]}, with_counterfactuals=False)
    excluded = {e["id"] for e in r["stack"]["database"]["excluded"]}
    assert {"firestore", "dynamodb", "redis"} <= excluded


def test_redis_is_a_cache_not_the_system_of_record():
    """I1: realtime multiplayer with ~62 GB in a year must not keep it all in RAM as the primary database."""
    r = recommend(_scenario("I1"), with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] != "redis"
    assert any(s["role"] == "Cache" and "Redis" in s["name"] for s in r["supporting_services"])


def test_offline_lists_a_sync_service():
    r = recommend({"app_type": "mobile_first", "offline": True}, with_counterfactuals=False)
    assert any(s["role"] == "Offline sync" for s in r["supporting_services"])


def test_specialised_store_not_listed_as_alternative():
    """J02 food delivery (relational data): TimescaleDB is a time-series store and fits relational data worse
    than the pick, so it is not offered as the database alternative."""
    r = recommend(_scenario("J02"), with_counterfactuals=False)
    alts = {a["id"] for a in r["stack"]["database"]["alternatives"]}
    assert "timescaledb" not in alts and alts


def test_hiring_pool_breaks_ties_only_without_skills():
    from engine.stack import _tb_value
    from engine.recommender import _core
    with_skills = _core({"team_skills": ["python", "react"]})["combos"][0]
    without = _core({})["combos"][0]
    assert _tb_value(with_skills, "hiring") == 0
    assert _tb_value(without, "hiring") > 0
    # Skills listed but none for a web frontend: the frontend's hiring pool alone breaks the tie.
    no_fe = _core({"team_skills": ["python"]})["combos"][0]
    assert _tb_value(no_fe, "hiring") == no_fe["picks"]["frontend"]["item"]["scores"]["hiring"]


def test_write_heavy_leaderboard_with_redis_team_gets_redis():
    """E20: a 10M-DAU leaderboard (write-heavy key-value, ~44 GB in a year, $60k/month) with a Redis
    team. The RAM for primary plus replica (~$1k/month) is well inside the database budget share, so
    the in-memory limit does not apply."""
    from engine.scoring import ram_affordable
    r = recommend(_scenario("E20"), with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "redis"
    assert ram_affordable(r["profile"], dict(r["derived"]))


def test_in_memory_limit_still_applies_on_a_small_budget():
    """The same data on a $400/month budget cannot pay for the RAM: Redis stays excluded as the primary."""
    raw = dict(_scenario("E20"), budget_monthly=400)
    r = recommend(raw, with_counterfactuals=False)
    assert "redis" in {e["id"] for e in r["stack"]["database"]["excluded"]}


# --- Database fit to the data, and databases the team would have to run itself -------------------------------

def _pick(inp, layer="database"):
    return recommend(inp, with_counterfactuals=False)["stack"][layer]["pick"]["id"]


def test_self_managed_database_on_its_missing_cloud_loses_to_managed_postgres():
    """J10: a small analytics dashboard on Google Cloud. Cloud SQL has no TimescaleDB extension, so Timescale
    there is run by the team; a managed store wins unless time-series needs are strong. The app type's own data
    shape (analytical) lifts the unanswered consistency default, so the managed store may be BigQuery."""
    r = recommend(_scenario("J10"), with_counterfactuals=False)
    assert r["stack"]["hosting"]["pick"]["id"].startswith("gcp_")
    assert r["stack"]["database"]["pick"]["id"] in ("postgres", "bigquery")


def test_strong_time_series_need_still_wins_despite_running_it_yourself():
    """E07: time-series is the first data shape, 400 GB a month of telemetry, and the team already knows Postgres."""
    r = recommend(_scenario("E07"), with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "timescaledb"
    assert r["stack"]["hosting"]["pick"]["id"].startswith("gcp_")
    assert any("timescaledb_self_managed_on_gcp" in c.get("id", "") or "has no managed service on Google Cloud" in c.get("note", "")
               for c in r["compatibility"])


def test_self_managed_rule_comes_from_the_knowledge_base_field():
    from engine.kb import load_kb, validate_kb
    kb = load_kb()
    rule = next(x for x in kb["rules"] if x["id"] == "timescaledb_self_managed_on_gcp")
    assert rule["when"] == {"database": ["timescaledb"], "hosting_provider": ["gcp"]} and rule["delta"] < 0
    assert rule["source"].startswith("https://cloud.google.com/")
    assert not validate_kb()


def test_self_managed_database_costs_more_than_its_managed_price_band():
    """Same Timescale band, priced with the allowance for backups, monitoring and failover the team builds."""
    from engine.advice import SELF_MANAGED_COST_FACTOR
    r = recommend(_scenario("E07"), with_counterfactuals=False)
    line = next(x for x in r["cost"]["lines"] if x["component"].startswith("Database: TimescaleDB"))
    assert f"x{SELF_MANAGED_COST_FACTOR:g} planning allowance" in line["basis"]


def test_poor_fit_for_the_data_shapes_loses_to_a_good_fit():
    """E08: time-series + analytical at 8 TB. MongoDB (analytical 2/5) must not beat a store that fits both."""
    assert _pick(_scenario("E08")) in ("clickhouse", "timescaledb")


def test_good_fit_stores_are_not_separated_by_the_gate():
    """A 4/5 fit is not penalised for a 5/5 neighbour: with document + relational data Postgres (4.3/5) keeps
    its score next to a document store (3.7/5 for the same shapes)."""
    from engine.recommender import _core
    scored = {c["id"]: c for c in _core({"data_shapes": ["document", "relational"]})["scored"]["database"]}
    assert not any("Fits your data shapes" in a["reason"] for a in scored["postgres"]["adjustments"])


def test_strong_consistency_keeps_the_record_store_strong_and_offers_the_analytics_store():
    """Relational records + analytical queries with strong consistency: Postgres holds the records and
    ClickHouse (eventually consistent, so never the record store) is offered for the analytical part."""
    inp = {"app_type": "saas", "data_shapes": ["relational", "analytical"], "consistency": "strong",
           "dau": 20000, "data_volume_gb": 3000, "read_write": "read_heavy", "team_size": 5,
           "team_skills": ["python"], "budget_monthly": 2000, "currency": "USD", "regions": ["europe"]}
    r = recommend(inp, with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] != "clickhouse"
    assert any(e["id"] == "clickhouse" for e in r["stack"]["database"]["excluded"])
    names = " ".join(s["name"] for s in r["supporting_services"] if "tore" in s["role"] or s["role"] == "Analytics")
    # The analytics store is ClickHouse, or BigQuery when the app is hosted on Google Cloud (native there).
    on_gcp = r["stack"]["hosting"]["pick"]["id"] in ("gcp_cloud_run", "gcp_gke")
    assert ("BigQuery" if on_gcp else "ClickHouse") in names


def test_analytical_only_data_has_no_record_to_protect():
    from engine.scoring import record_shapes
    assert record_shapes({"primary_shape": "analytical", "secondary_shapes": []}) == []
    assert record_shapes({"primary_shape": "analytical", "secondary_shapes": ["relational"]}) == ["relational"]


def _services_with(inp, drop=()):
    """Supporting services for the picked stack, with some databases removed from the candidates."""
    from engine.advice import supporting_services
    from engine.recommender import _core
    core = _core(inp)
    stack = {l: c["item"] for l, c in core["combos"][0]["picks"].items()}
    cands = [c for c in core["scored"]["database"] if c["id"] not in drop]
    return supporting_services(core["p"], core["d"], stack, cands)


def test_strong_consistency_never_puts_record_data_in_an_eventually_consistent_secondary_store():
    """Relational + time-series records under strong consistency, with the strong and tunable time-series
    stores removed: ClickHouse (time-series 4/5, eventually consistent) may serve analytics, never records."""
    from engine.kb import load_kb
    eventual = {it["name"] for it in load_kb()["database"] if it["consistency"] == "eventual"}
    svcs = _services_with({"data_shapes": ["relational", "time_series"], "consistency": "strong"},
                          drop=("timescaledb", "mongodb"))
    for s in svcs:
        if s["role"].startswith("Secondary store"):
            assert not any(s["name"].startswith(n) for n in eventual), s


def test_one_secondary_store_serving_several_shapes_is_listed_once():
    """Analytical primary with vector + relational secondaries: one Postgres covers both, so it is one system."""
    inp = {"app_type": "ml_product", "data_shapes": ["analytical", "vector", "relational"], "consistency": "eventual_ok",
           "dau": 2000, "data_volume_gb": 50000, "read_write": "write_heavy", "team_size": 20,
           "team_skills": ["python", "sql"], "budget_monthly": 60000, "currency": "USD", "cloud_preference": "gcp"}
    r = recommend(inp, with_counterfactuals=False)
    stores = [s for s in r["supporting_services"] + r["deferred_services"] if s["role"].startswith("Secondary store")]
    assert stores and len({s["name"] for s in stores}) == len(stores)


def test_dashboard_analytics_store_is_priced_by_the_data_it_copies():
    """A columnar copy of 5 TB costs more than one of 150 GB at the same traffic."""
    base = {"app_type": "analytics_dashboard", "data_shapes": ["relational"], "consistency": "strong", "dau": 3000,
            "read_write": "read_heavy", "team_size": 6, "team_skills": ["python", "sql"], "budget_monthly": 6000,
            "currency": "USD"}
    def line(gb):
        r = recommend(dict(base, data_volume_gb=gb), with_counterfactuals=False)
        return next(x for x in r["cost"]["lines"] if x["component"].startswith("Analytics"))
    assert line(5000)["high"] > line(150)["high"]


def test_analytics_store_is_not_held_to_the_primary_shape():
    """Document records + analytical queries: ClickHouse cannot hold the documents (1/5) but is the best
    analytical store (5/5), so it is the supporting analytics store."""
    inp = {"app_type": "analytics_dashboard", "data_shapes": ["document", "analytical"], "consistency": "eventual_ok",
           "dau": 20000, "data_volume_gb": 20000, "read_write": "write_heavy", "team_size": 6,
           "team_skills": ["go", "python"], "budget_monthly": 15000, "currency": "USD", "cloud_preference": "aws"}
    r = recommend(inp, with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] != "clickhouse"
    store = next(s for s in r["supporting_services"] + r["deferred_services"]
                 if s["role"].startswith("Secondary store") and "analytical" in s["role"])
    assert store["name"].startswith("ClickHouse")


def test_sql_orm_backends_are_not_paired_with_document_baas_stores(kb):
    """Django, Rails, Laravel, Phoenix and ASP.NET Core build their data layer on a SQL ORM: a PHP team's content
    site with a server backend gets a SQL database, not Cloud Firestore."""
    rules = {r["id"]: r for r in kb["rules"]}
    for be in ("django", "rails", "laravel", "phoenix", "dotnet"):
        hit = [r for r in rules.values() if be in r.get("when", {}).get("backend", ())
               and "firestore" in r.get("when", {}).get("database", ()) and r["delta"] < 0]
        assert hit and hit[0]["source"].startswith("https://"), be
    r = recommend({"app_type": "content_site", "team_skills": ["php", "vue"], "budget_monthly": 50, "dau": 2000,
                   "data_volume_gb": 20, "user_actions": ["read"]}, with_counterfactuals=False)
    if r["stack"]["backend"]["pick"]["id"] in ("laravel", "django", "rails", "phoenix", "dotnet"):
        assert r["stack"]["database"]["pick"]["id"] not in ("firestore", "dynamodb")


def test_defaulted_data_shape_lowers_the_score_but_does_not_exclude():
    # The generic default ('relational') is an assumption, not an answer: a Firebase team's offline mobile app
    # on a $0 budget keeps Firestore. A stated relational shape still excludes it.
    raw = {"app_type": "mobile_first", "platforms": ["ios", "android"], "dau": 2000, "team_size": 1,
           "team_skills": ["dart", "firebase"], "budget_monthly": 0, "offline": True, "regions": ["global"]}
    r = recommend(raw, with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "firestore"
    r = recommend(dict(raw, data_shapes=["relational"]), with_counterfactuals=False)
    assert "firestore" in {e["id"] for e in r["stack"]["database"]["excluded"]}


def test_analytical_dashboard_can_keep_its_data_in_a_warehouse():
    # Main data analytical, consistency not answered: the warehouse may be the primary store (records go to a
    # secondary relational store). Stated strong consistency keeps a row store primary, and the warehouse line
    # then says it holds a copy of the same data.
    raw = {"app_type": "analytics_dashboard", "dau": 300, "data_volume_gb": 2000, "data_growth_gb_month": 200,
           "read_write": "read_heavy", "data_shapes": ["analytical", "relational"], "team_size": 3,
           "team_skills": ["python", "sql", "gcp"], "cloud_preference": "gcp", "budget_monthly": 2000,
           "regions": ["north_america"], "seo": "none"}
    r = recommend(raw, with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "bigquery"
    assert not any(l["component"].startswith("Analytics") for l in r["cost"]["lines"])
    assert any(s["role"] == "Secondary store (relational)" for s in r["supporting_services"])
    r = recommend(dict(raw, consistency="strong"), with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] != "bigquery"
    line = next(l for l in r["cost"]["lines"] if l["component"].startswith("Analytics"))
    assert "paid for in both stores" in line["basis"]
