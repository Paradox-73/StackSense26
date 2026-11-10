"""The "search" data shape: data read mainly by typing words (log search, document search). A search engine
(OpenSearch / Elasticsearch) is the primary store when search is the primary shape; a small search corpus
next to relational data stays in the database's own text index; a large one gets the search engine as a
secondary store."""
import json
from pathlib import Path

from engine import recommend
from engine.kb import DATA_SHAPES, field_specs, load_kb

AUDIT = Path(__file__).resolve().parent / "scenarios_extra"


def _scenario(name):
    return next(s["input"] for s in json.loads((AUDIT / "kb_gap.json").read_text(encoding="utf-8")) if s["name"] == name)


def _run(**answers):
    return recommend(answers, with_counterfactuals=False)


def _search_lines(r):
    return [s for s in r["supporting_services"] if s["role"] == "Search" or "search" in s["role"].lower()]


def test_every_database_rates_the_search_shape_and_the_question_offers_it():
    assert "search" in DATA_SHAPES
    assert all("search" in it["models"] for it in load_kb()["database"])
    assert "search" in [o["value"] for o in field_specs()["data_shapes"]["options"]]


def test_log_search_platform_gets_a_search_engine_as_primary():
    r = recommend(_scenario("G8_log_search_platform"), with_counterfactuals=False)
    assert r["stack"]["database"]["pick"]["id"] == "opensearch"
    # The search engine is the primary store, so no second search cluster is added.
    assert not [s for s in r["supporting_services"] if s["role"] == "Search"]


def test_search_only_data_is_not_held_to_strong_consistency():
    # A search index is read through the index, not updated in transactions (like analytical data).
    r = _run(app_type="saas", dau=5000, budget_monthly=2000, data_shapes=["search"], consistency="strong",
             data_volume_gb=300, data_growth_gb_month=20)
    assert r["stack"]["database"]["pick"]["id"] == "opensearch"


def test_small_search_corpus_stays_in_the_database_text_index():
    r = _run(app_type="saas", dau=2000, budget_monthly=300, team_skills=["python"], data_shapes=["relational", "search"],
             data_volume_gb=2, data_growth_gb_month=0.5)
    assert r["stack"]["database"]["pick"]["id"] == "postgres"
    lines = _search_lines(r)
    assert len(lines) == 1 and "Postgres full-text search" in lines[0]["name"]


def test_large_search_corpus_gets_the_search_engine_as_a_secondary_store():
    r = _run(app_type="saas", dau=20000, budget_monthly=3000, team_skills=["python"],
             data_shapes=["relational", "search"], data_volume_gb=400, data_growth_gb_month=20)
    assert r["stack"]["database"]["pick"]["id"] == "postgres"
    lines = _search_lines(r)
    assert len(lines) == 1 and "OpenSearch" in lines[0]["name"] and "search" in lines[0]["role"]


def test_projects_without_search_never_get_it_as_primary():
    for shapes in (["relational"], ["document"], ["time_series", "relational"], ["document", "analytical"]):
        r = _run(app_type="saas", dau=20000, budget_monthly=3000, data_shapes=shapes, data_volume_gb=400,
                 data_growth_gb_month=20, consistency="eventual_ok")
        assert r["stack"]["database"]["pick"]["id"] != "opensearch", shapes
