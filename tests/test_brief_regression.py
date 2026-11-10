"""Fifteen project descriptions written by a reviewer to probe the pattern reader (no network). Each row lists answers
the reader must find; values left out of a row are not checked. Every value must quote the description."""
import pytest

from engine.brief import parse_brief, quote_in_text
from engine.brief_rules import read_all

CASES = [
    ("college fest ticketing site, about 2 lakh students across karnataka, we can spend maybe 5k rupees a month. "
     "3 of us know react and node.",
     {"dau": 40000, "team_size": 3, "budget_monthly": 5000, "currency": "INR", "team_skills": ["react", "node"],
      "regions": ["india"], "platforms": ["web"]}),
    ("Food delivery app for Tier-2 cities. 50k orders/day at peak dinner time. Budget 1.5 crore INR per year. Team of 12, "
     "Java/Spring + Kotlin. Need live rider tracking and UPI payments.",
     {"dau": 50000, "team_size": 12, "budget_monthly": 1250000, "regions": ["india"], "realtime": "some",
      "special_workloads": ["live_location"], "user_actions": ["read", "sign_in", "post", "pay"], "app_type": "ecommerce"}),
    ("B2B HR SaaS for Indian mid-size companies, needs SSO with Azure AD / Okta, multi-tenant, audit logs, DPDP compliant. "
     "8 devs, TypeScript. ~300 tenant companies, 40,000 employees total.",
     {"team_size": 8, "team_skills": ["typescript"], "regions": ["india"], "compliance": ["dpdp"], "app_type": "saas",
      "dau": 8000, "tenancy": "shared", "enterprise_sso": True}),
    ("simple blog", {"app_type": "content_site"}),
    ("we r 2 frnds bulding a stdy app for jee aspirants, 10000 users, no money, flutter devs, shud work offline",
     {"team_size": 2, "dau": 2000, "budget_monthly": 0, "team_skills": ["flutter"], "regions": ["india"], "offline": True}),
    ("Hospital EHR integrating with our existing Oracle database and HL7 FHIR APIs. On-prem only, data cant leave india. "
     "99.99% uptime. 20 engineers, .NET shop.",
     {"team_size": 20, "team_skills": ["csharp"], "deployment": "on_prem", "availability": "99.99",
      "existing_systems": ["oracle"], "compliance": ["data_residency_india"], "app_type": "healthcare"}),
    ("Need a Shopify-like marketplace for handloom weavers. Mobile-first, vernacular languages (Hindi, Tamil, Bengali), "
     "sellers upload lots of product photos and videos. $200/mo. Python team.",
     {"budget_monthly": 200, "team_skills": ["python"], "regions": ["india"], "special_workloads": ["media_uploads"],
      "app_type": "ecommerce", "platforms": ["ios", "android"]}),
    ("IoT: 5000 smart meters reporting every 15 seconds, dashboards for utility staff. AWS credits. Go and Postgres.",
     {"dau": 5000, "peak_rps": 333.3, "team_skills": ["go", "postgres"], "cloud_preference": "aws", "app_type": "iot_telemetry"}),
    ("Realtime multiplayer quiz game for 10,000 concurrent players during live events, spikes to 50k. No SEO needed. "
     "Elixir team of 4. Launch in 6 weeks.",
     {"peak_concurrent": 50000, "team_size": 4, "team_skills": ["elixir"], "seo": "none", "realtime": "core",
      "timeline_weeks": 6, "app_type": "realtime_collab"}),
    ("Internal admin panel for 50 employees, read-mostly, we already run MySQL and want to keep it. Budget is basically nothing.",
     {"budget_monthly": 0, "existing_systems": ["mysql"], "read_write": "read_heavy", "app_type": "internal_tool"}),
    ("A RAG chatbot over our company's 2 TB of PDFs, needs vector search, 500 DAU, budget $2000/month, team of 5 Python devs, "
     "must not lose data, GDPR since users in Germany.",
     {"dau": 500, "team_size": 5, "budget_monthly": 2000, "team_skills": ["python"], "regions": ["europe"],
      "compliance": ["gdpr"], "data_volume_gb": 2000, "data_shapes": ["relational", "vector"], "app_type": "ml_product"}),
    ("Fintech lending app, UPI autopay, RBI compliant, 1 million MAU expected in year 1, team of 25, kubernetes on GCP. "
     "Low latency < 100ms.",
     {"dau": 200000, "team_size": 25, "cloud_preference": "gcp", "latency_target_ms": 100, "app_type": "fintech",
      "user_actions": ["read", "sign_in", "post", "pay"]}),
    ("We want a cheap website but also it must handle 10 million users a day and run on our own servers but also on Vercel.",
     {"dau": 10000000, "deployment": "on_prem", "platforms": ["web"]}),
    ("Video course platform like Udemy for Indian learners, 20k DAU, lots of video on demand streaming, payments via Razorpay, "
     "3 devs know Django, budget Rs 50,000 per month, launch in 3 months.",
     {"dau": 20000, "team_size": 3, "budget_monthly": 50000, "currency": "INR", "team_skills": ["django"],
      "special_workloads": ["video_on_demand"], "user_actions": ["read", "sign_in", "post", "pay"], "timeline_weeks": 13}),
    ("Social app for college clubs with push notifications, image uploads, feed, chat. Android and iOS. 2 devs, "
     "React Native and Firebase. Expect growth from 2k to 200k users within a year.",
     {"team_size": 2, "team_skills": ["react_native", "firebase"], "realtime": "core", "special_workloads": ["media_uploads"],
      "app_type": "social_network", "platforms": ["ios", "android"]}),
]


@pytest.mark.parametrize("text, want", CASES, ids=[f"brief{i + 1:02d}" for i in range(len(CASES))])
def test_review_brief(text, want):
    fields = parse_brief(text, use_llm=False)["fields"]
    got = {k: f["value"] for k, f in fields.items()}
    for k, v in want.items():
        assert k in got, (k, got)
        if isinstance(v, list) and k != "data_shapes":
            assert sorted(got[k]) == sorted(v), (k, got[k])
        else:
            assert got[k] == v, (k, got[k])
    for k, f in fields.items():
        assert all(quote_in_text(q, text) for q in f["quotes"]), (k, f["quotes"])


def test_azure_ad_is_not_a_skill_and_concurrency_is_not_an_audience():
    v = {k: h.value for k, h in read_all(CASES[2][0]).items()}
    assert "azure" not in v["team_skills"]
    v = {k: h.value for k, h in read_all(CASES[8][0]).items()}
    assert "dau" not in v


@pytest.mark.parametrize("text, key, value", [
    ("We already run MySQL.", "existing_systems", ["mysql"]),
    ("Must work with the existing Oracle database", "existing_systems", ["oracle"]),
    ("keep our Postgres cluster", "existing_systems", ["postgres"]),
    ("Riders share photos of deliveries", "special_workloads", ["media_uploads"]),
    ("live classes with video calls", "special_workloads", ["live_video"]),
    ("students submit code and an online judge runs it", "special_workloads", ["user_code"]),
    ("login by phone OTP", "special_workloads", ["phone_otp"]),
    ("Checkout through Stripe", "user_actions", ["read", "sign_in", "post", "pay"]),
    ("about 500 GB of data at launch", "data_volume_gb", 500),
    ("logs grow by 20 GB a month", "data_growth_gb_month", 20),
    ("p95 latency under 50 ms", "latency_target_ms", 50),
    ("the workload is write-heavy", "read_write", "write_heavy"),
    ("data can't leave India", "compliance", ["data_residency_india"]),
    ("Personal data cannot leave the EU", "compliance", ["data_residency_eu"]),
    ("we got GCP credits", "cloud_preference", "gcp"),
    ("10000 users", "dau", 2000),
    ("2 lakh students", "dau", 40000),
    ("users across Kerala and Tamil Nadu", "regions", ["india"]),
    ("readings stored as time-series", "data_shapes", ["time_series", "relational"]),
    ("a separate database per customer", "tenancy", "isolated"),
    ("staff log in with Okta", "enterprise_sso", True),
])
def test_phrasings_the_reader_used_to_miss(text, key, value):
    v = {k: h.value for k, h in read_all(text).items()}
    assert v.get(key) == value, (key, v)


@pytest.mark.parametrize("text, key", [
    ("we are 3 students", "dau"),                    # a small count is the team, not the audience
    ("servers with 64 GB RAM", "data_volume_gb"),     # memory, not data
    ("no payments in version one", "user_actions"),
    ("we do not need video calls", "special_workloads"),
    ("an app where landlords and tenants pay rent", "tenancy"),
])
def test_phrasings_that_must_not_be_read(text, key):
    assert key not in read_all(text)
