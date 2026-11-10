from engine.recommender import recommend

BASE = {"app_type": "ecommerce", "dau": 300000, "team_size": 5}


def picks(raw):
    r = recommend(raw, False)
    return r, {l: r["stack"][l]["pick"]["name"] for l in r["stack"]}


def test_empty_priorities_change_nothing():
    assert picks(BASE)[1] == picks({**BASE, "priorities": []})[1]


def test_priorities_appear_in_the_weight_trace():
    r, _ = picks({**BASE, "priorities": ["cost", "speed"]})
    reasons = [d["reason"] for w in r["weights"] for d in w["drivers"]]
    assert "Your priority #1: lowest cost" in reasons
    assert "Your priority #2: ship fastest" in reasons


def test_only_three_priorities_are_used():
    r, _ = picks({**BASE, "priorities": ["cost", "speed", "scale", "proven"]})
    assert r["profile"]["priorities"] == ["cost", "speed", "scale"]


def test_existing_mysql_is_kept():
    assert picks({**BASE, "existing_systems": ["mysql"]})[1]["database"] == "MySQL"


def test_unknown_existing_database_is_explained():
    r, _ = picks({**BASE, "existing_systems": ["oracle"]})
    assert "EXISTING_SYSTEM_UNKNOWN" in {w["code"] for w in r["warnings"]}


def test_unkept_existing_database_is_flagged():
    r, got = picks({**BASE, "existing_systems": ["mongodb"]})
    if got["database"] != "MongoDB":
        assert "EXISTING_SYSTEM_NOT_PICKED" in {w["code"] for w in r["warnings"]}


def test_cacheable_traffic_lowers_origin_load_and_lists_a_cdn():
    base, _ = picks({"app_type": "saas", "dau": 100000, "team_skills": ["python"]})
    most, _ = picks({"app_type": "saas", "dau": 100000, "team_skills": ["python"], "cacheable_share": "most"})
    assert most["derived"]["peak_rps"] < base["derived"]["peak_rps"] * 0.3
    assert any(s["role"] == "CDN" for s in most.get("supporting_services", []))
    assert not any(s["role"] == "CDN" for s in base.get("supporting_services", []))


def test_traffic_pattern_scales_the_peak():
    steady = recommend({"app_type": "saas", "dau": 100000, "traffic_pattern": "steady"}, False)["derived"]["peak_rps"]
    spiky = recommend({"app_type": "saas", "dau": 100000, "traffic_pattern": "spiky"}, False)["derived"]["peak_rps"]
    assert spiky > 3 * steady


def test_region_questions_carry_weight():
    r = recommend({**BASE, "latency_target_ms": 100, "realtime": "core"}, False)
    reg = next(w for w in r["weights"] if w["criterion"] == "region_fit")
    assert reg["weight"] >= 2.5


def test_glossary_has_the_twelve_added_terms():
    from engine.kb import load_glossary
    terms = load_glossary()["terms"]
    for k in ("lsm", "olap", "oltp", "acid", "cap", "lcp", "multi_az", "cdn", "sharding", "connection_pooling", "rpo_rto", "orm"):
        assert terms[k]["definition"] and terms[k]["source"].startswith("https://")


def test_cacheable_share_also_scales_a_stated_peak():
    raw = {"app_type": "content_site", "dau": 20000, "peak_rps": 30000}
    full = recommend(raw, False)["derived"]["peak_rps"]
    cached = recommend({**raw, "cacheable_share": "most"}, False)["derived"]["peak_rps"]
    assert cached == full * 0.2
