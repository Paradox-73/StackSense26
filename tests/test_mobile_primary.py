"""A mobile-first app that also targets the web may get a mobile toolkit as its primary frontend; the web
framework is then the companion. Other app types that target web and mobile keep a web framework as primary."""
from engine import recommend
from engine.kb import load_kb
from engine.profile import derive, normalize
from engine.scoring import hard_constraints

BASE = {"platforms": ["android", "ios", "web"], "dau": 50000, "team_size": 8,
        "team_skills": ["kotlin", "swift", "java", "spring", "postgres"], "timeline_weeks": 20,
        "budget_monthly": 3000, "currency": "USD", "deployment": "cloud"}


def _mobile_excluded(app_type):
    p, a, w = normalize(dict(BASE, app_type=app_type))
    d = derive(p, a, w)
    native = next(i for i in load_kb()["frontend"] if i["id"] == "native_mobile")
    return bool(hard_constraints("frontend", native, p, d))


def test_mobile_toolkit_allowed_as_primary_only_for_mobile_first():
    assert not _mobile_excluded("mobile_first")
    assert _mobile_excluded("saas")


def test_mobile_primary_gets_web_companion():
    r = recommend(dict(BASE, app_type="mobile_first"))
    fe = r["stack"]["frontend"]["pick"]["id"]
    kinds = {i["id"]: i.get("kind", "web") for i in load_kb()["frontend"]}
    comp = r["companion"]
    assert comp is not None
    assert kinds[comp["id"]] != kinds[fe], "the companion covers the other platform"
    if kinds[fe] == "mobile":
        assert comp["role"] == "Web app"
        assert "browser loads" not in r["architecture"]["how_parts_fit"][0]["text"]
    else:
        assert comp["role"].startswith("Mobile app")
