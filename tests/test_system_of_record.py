"""Specialist stores (KB field system_of_record: in-memory, graph, search index) are the primary database only for the
data shapes they can hold as records; other records go to a durable general-purpose primary, with the specialist
listed beside it as a supporting store."""
from engine import recommend
from engine.kb import load_kb, validate_kb
from engine.scoring import specialist_reason


def _run(**answers):
    return recommend(answers, with_counterfactuals=False)


def _excluded(r):
    return {e["id"] for e in r["stack"]["database"]["excluded"]}


def test_specialist_facts_are_valid_and_cited():
    assert not validate_kb()
    idx = load_kb()["index"]
    for sid in ("redis", "neo4j", "opensearch"):
        sor = idx[sid]["system_of_record"]
        assert sor["source"] in idx[sid]["sources"]


def test_graph_store_is_not_the_primary_when_there_are_relational_records():
    # A PCI fintech with a fraud graph: the ledger is relational, the graph sits beside it.
    r = _run(app_type="fintech", dau=1000, data_shapes=["graph", "relational"], team_skills=["java", "spring"],
             budget_monthly=3000, regions=["europe"], compliance=["gdpr", "pci_dss"])
    assert r["stack"]["database"]["pick"]["id"] != "neo4j"
    assert "neo4j" in _excluded(r)
    assert any(s["role"].startswith("Secondary store") and "Neo4j" in s["name"] for s in r["supporting_services"])


def test_graph_store_stays_primary_for_graph_only_data():
    r = _run(dau=5000, data_shapes=["graph"], consistency="eventual_ok", budget_monthly=2000)
    assert "neo4j" not in _excluded(r)


def test_search_index_is_not_the_primary_for_documents():
    r = _run(app_type="saas", dau=5000, data_shapes=["search", "document"], special_workloads=["text_search"],
             team_skills=["python", "django", "elasticsearch"], budget_monthly=1500, data_volume_gb=800,
             regions=["europe"], compliance=["data_residency_eu", "gdpr"])
    assert r["stack"]["database"]["pick"]["id"] != "opensearch"
    assert any("OpenSearch" in s["name"] for s in r["supporting_services"])


def test_in_memory_store_is_not_the_primary_for_relational_records():
    r = _run(app_type="realtime_collab", dau=100000, platforms=["android", "ios"], team_skills=["csharp"],
             budget_monthly=5000, latency_target_ms=50, data_shapes=["key_value", "relational"], consistency="eventual_ok")
    assert r["stack"]["database"]["pick"]["id"] != "redis"
    assert any(s["role"] == "Cache" and "Redis" in s["name"] for s in r["supporting_services"])


def test_in_memory_store_never_holds_regulated_data():
    redis = load_kb()["index"]["redis"]
    p = {"compliance": ["hipaa"]}
    d = {"primary_shape": "key_value", "secondary_shapes": []}
    assert specialist_reason(redis, p, d)
    assert specialist_reason(redis, {"compliance": []}, d) is None


def test_one_database_for_all_records_beats_a_second_store():
    # Key-value game state plus relational accounts: with the in-memory store beside it for the key-value data, a store
    # that fits both record shapes is the primary; one that fits the relational records 2/5 would need a second database.
    r = _run(app_type="realtime_collab", dau=100000, platforms=["android", "ios"], team_skills=["csharp"],
             budget_monthly=5000, latency_target_ms=50, data_shapes=["key_value", "relational"], consistency="eventual_ok")
    assert r["stack"]["database"]["pick"]["id"] == "postgres"
    mongo = next(c for c in r["stack"]["database"]["ranking"] if c["id"] == "mongodb")
    assert mongo["score"] < next(c for c in r["stack"]["database"]["ranking"] if c["id"] == "postgres")["score"]
    assert not any(s["role"].startswith("Secondary store (relational)") for s in r["supporting_services"])
