"""Special workloads (video, maps, SMS, uploads, user code) add their own service and a usage-based cost."""
import json
from pathlib import Path

import pytest

from engine import recommend

AUDIT = Path(__file__).resolve().parent / "scenarios_extra"


def _audit(name):
    for f in AUDIT.glob("*.json"):
        for s in json.loads(f.read_text(encoding="utf-8")):
            if s["name"].startswith(name):
                return s["input"]
    raise KeyError(name)


def _run(inp, work):
    return recommend(dict(inp, special_workloads=work), with_counterfactuals=False)


def test_live_classes_get_a_video_service_with_a_cost_line():
    r = _run(_audit("S03"), ["live_video"])
    assert any(s["role"] == "Live video" for s in r["supporting_services"])
    line = next(x for x in r["cost"]["lines"] if x["component"] == "Live video")
    assert 0 < line["low"] < line["high"] and "participant-minutes" in line["basis"]


def test_lecture_videos_get_storage_and_streaming():
    r = _run(_audit("D1"), ["video_on_demand"])
    roles = {s["role"] for s in r["supporting_services"]}
    assert {"Object storage", "Video on demand"} <= roles
    assert any(x["component"] == "Video on demand" and x["high"] > 0 for x in r["cost"]["lines"])


@pytest.mark.parametrize("work,role", [("media_uploads", "Media delivery"), ("live_location", "Maps & live location"),
                                       ("phone_otp", "Phone login (SMS OTP)"), ("user_code", "Code sandbox")])
def test_each_workload_adds_its_service(work, role):
    r = _run({"dau": 20000, "regions": ["india"]}, [work])
    assert any(s["role"] == role for s in r["supporting_services"])


def test_workloads_follow_hipaa_and_on_prem(presets):
    hipaa = _run(presets["hipaa_telehealth"]["input"], ["live_video"])
    assert "BAA" in next(s["name"] for s in hipaa["supporting_services"] if s["role"] == "Live video")
    onprem = _run({"deployment": "on_prem"}, ["live_video", "video_on_demand"])
    names = " ".join(s["name"] for s in onprem["supporting_services"])
    assert "Self-hosted" in names or "self-hosted" in names
    assert "Cloudflare Stream" not in names and "LiveKit Cloud" not in names


def test_cost_grows_with_users():
    small = _run({"dau": 1000}, ["video_on_demand"])["cost"]["total_high"]
    big = _run({"dau": 100000}, ["video_on_demand"])["cost"]["total_high"]
    assert big > small


def test_default_adds_nothing(presets):
    r = recommend(presets["hipaa_telehealth"]["input"], with_counterfactuals=False)
    assert not any(s["role"] in ("Live video", "Video on demand") for s in r["supporting_services"])
