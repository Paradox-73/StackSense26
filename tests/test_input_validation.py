from engine.recommender import recommend


def codes(raw):
    return {w["code"] for w in recommend(raw, False)["warnings"]}


def test_implausible_peak_rps():
    assert "PEAK_RPS_IMPLAUSIBLE" in codes({"dau": 100, "peak_rps": 100000})
    assert "PEAK_RPS_IMPLAUSIBLE" not in codes({"dau": 100000, "peak_rps": 400})


def test_rps_mismatch_fires_for_tiny_apps():
    assert "RPS_DAU_MISMATCH" in codes({"dau": 100, "peak_rps": 100000})


def test_unknown_key_and_text_number():
    c = codes({"dau": "500", "colour": "red"})
    assert "UNKNOWN_FIELD" in c and "TYPE_COERCED" in c


def test_free_tier_has_no_sla():
    assert "FREE_TIER_NO_SLA" in codes({"budget_monthly": 0, "availability": "99.9"})
    assert "FREE_TIER_NO_SLA" not in codes({"budget_monthly": 100, "availability": "99.9"})


def test_internal_tool_scale():
    assert "INTERNAL_TOOL_SCALE" in codes({"app_type": "internal_tool", "dau": 50000})
    assert "INTERNAL_TOOL_SCALE" not in codes({"app_type": "internal_tool", "dau": 200})


def test_inr_summary_uses_rupees():
    r = recommend({"currency": "INR", "budget_monthly": 10000}, False)
    assert "₹" in r["summary"].split("Estimated infrastructure cost")[1]


def test_inr_summary_has_no_dollar_amounts():
    from engine.kb import load_presets
    raw = next(x["input"] for x in load_presets() if x["id"] == "india_college_fest")
    assert raw.get("currency") == "INR"
    summary = recommend(raw, False)["summary"]
    assert "₹" in summary and "$" not in summary
