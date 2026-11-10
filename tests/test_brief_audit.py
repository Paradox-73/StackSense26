"""Phrasings an audit of the pattern reader found misread (no network)."""
import pytest

from engine.brief import parse_brief
from engine.brief_rules import read_all


def _values(text):
    return {k: h.value for k, h in read_all(text).items()}


def test_a_spike_in_another_unit_is_not_users_online():
    fields = parse_brief("About 500 concurrent users, and traffic spikes to 5000 requests per second.", use_llm=False)["fields"]
    assert fields["peak_concurrent"]["value"] == 500
    assert _values("About 500 concurrent users, budget spikes to 2000 rupees in December.")["peak_concurrent"] == 500
    assert _values("10,000 concurrent players, spikes to 50k on launch day.")["peak_concurrent"] == 50000


@pytest.mark.parametrize("text, dau", [
    ("We run on 3 machines. A food delivery app for 10,000 users.", 2000),  # the audience, scaled to daily users
    ("A food delivery app for 10,000 users that shows restaurants within 500 meters.", 2000),
    ("The game runs on 2 gateways in Mumbai.", None),
    ("IoT: 5000 smart meters reporting every 15 seconds.", 5000),
])
def test_device_words_count_a_fleet_only_in_a_device_brief(text, dau):
    hit = read_all(text).get("dau")
    assert (hit.value if hit else None) == dau


def test_paying_for_hosting_is_not_a_payment_feature():
    v = _values("An Indian lending startup. We can pay for hosting up to 5000 rupees a month.")
    assert "user_actions" not in v and v["budget_monthly"] == 5000


def test_rbi_binds_india_storage_only_when_the_app_takes_payments():
    assert "compliance" not in _values("A wallet app under RBI rules; no payments happen in the app.")
    assert _values("RBI regulated app with UPI payments.")["compliance"] == ["data_residency_india"]


@pytest.mark.parametrize("text, key", [
    ("No chat or comments needed.", "realtime"),
    ("Order updates through WhatsApp messaging.", "realtime"),
    ("B2B SaaS. SSO is not needed.", "enterprise_sso"),
    ("A shop where payments are not needed.", "user_actions"),
])
def test_a_denied_feature_is_not_read(text, key):
    assert key not in read_all(text)


def test_a_stated_feature_is_still_read():
    assert _values("A chat app for students.")["realtime"] == "core"
    assert _values("Staff sign in with SSO through Okta.")["enterprise_sso"] is True


@pytest.mark.parametrize("text, app", [
    ("A personal blog with an RSS feed.", "content_site"),
    ("An online store with a product feed for Google Shopping.", "ecommerce"),
    ("A social app with an activity feed.", "social_network"),
])
def test_only_a_social_feed_names_a_social_network(text, app):
    assert _values(text)["app_type"] == app


def test_an_identity_provider_is_not_a_cloud_preference():
    v = _values("Customers log in using Azure AD.")
    assert "cloud_preference" not in v and v["enterprise_sso"] is True
    assert _values("We use AWS credits from the startup program.")["cloud_preference"] == "aws"


def test_a_price_oracle_is_not_an_oracle_database():
    assert "existing_systems" not in read_all("A DeFi app; our price oracle feeds the contracts.")
    assert _values("We already run oracle db for billing.")["existing_systems"] == ["oracle"]


def test_a_storage_quota_per_user_is_not_the_data_stored():
    assert "data_volume_gb" not in read_all("Each user gets 5 GB of storage.")
    assert _values("We have 2 TB of PDFs.")["data_volume_gb"] == 2000


@pytest.mark.parametrize("text, growth", [
    ("We ingest 10 GB a day of logs.", 300),
    ("About 2 GB per week of uploads.", 8.67),
    ("50 GB a month of new files.", 50),
])
def test_data_growth_per_day_or_week_is_converted_to_a_month(text, growth):
    assert _values(text)["data_growth_gb_month"] == growth


def test_order_status_tracking_is_not_live_location():
    assert "special_workloads" not in read_all("Customers see order status, tracking deliveries by status emails.")
    assert _values("Need live rider tracking.")["special_workloads"] == ["live_location"]


# ---- phrasings a later audit found the pattern reader missing

def test_a_truck_fleet_is_iot_with_a_rate_from_devices_and_interval():
    v = _values("50,000 trucks reporting GPS every 5 seconds; keep data for 2 years.")
    assert v["app_type"] == "iot_telemetry"
    assert v["peak_rps"] == 10000
    assert v["dau"] == 50000  # devices counted as active, not scaled to 20%


@pytest.mark.parametrize("text, key, value", [
    ("We're an AWS shop.", "cloud_preference", "aws"),
    ("We are all-in on AWS.", "cloud_preference", "aws"),
    ("two Flutter devs", "team_size", 2),
    ("a dozen engineers", "team_size", 12),
    ("free tier please", "budget_monthly", 0),
    ("We want to stay on a free tier.", "budget_monthly", 0),
    ("each customer gets their own database", "tenancy", "isolated"),
    ("a database per customer", "tenancy", "isolated"),
    ("800 staff users", "dau", 800),
    ("An internal tool for 50 employees.", "dau", 50),
])
def test_more_plain_phrasings(text, key, value):
    assert _values(text).get(key) == value


def test_employee_counts_stay_an_audience_outside_internal_tools():
    assert _values("HR SaaS, 40,000 employees total.")["dau"] == 8000
