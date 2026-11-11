"""A scenario's data volume is all of its stored data. With uploaded files, the database holds the rows the engine
estimates per user (at most the total), and the rest is priced as object storage on the stack's own cloud."""
import json
import re
from pathlib import Path

from engine.standard import run

ROOT = Path(__file__).resolve().parent.parent


def _run(files: bool, cloud: str = "gcp", gb: float = 80_000) -> dict:
    doc = json.loads((ROOT / "scenarios" / "public" / "P3.json").read_text(encoding="utf-8"))
    doc["scale"].update(users_at_launch=300, users_12_months=3000, data_volume_gb_12_months=gb)
    doc["requirements"]["file_media_storage"] = files
    doc["infrastructure"].update(cloud_preference=cloud, deployment_model="managed_cloud", data_residency="none")
    doc["budget"]["monthly_infra_usd"] = 10_000
    return run(doc)


def _line(out: dict, start: str) -> str:
    return next((a for a in out["estimated_monthly_cost_usd"]["assumptions"] if a.startswith(start)), "")


def _gb(text: str) -> float:
    return float(re.search(r"~([\d,.]+) GB", text).group(1).replace(",", ""))


def test_uploaded_files_are_priced_as_object_storage_not_database_rows():
    out = _run(files=True)
    db = _line(out, "Database:")
    assert _gb(db) < 100, db  # 600 daily users write a few GB of rows a year, not 80 TB
    assert "SHARDING_PLAN" not in {w["code"] for w in out["warnings"]}
    store = _line(out, "Object storage")
    assert store and "cloud.google.com/storage/pricing" in store, store
    assert 79_000 < _gb(store) < 80_000, store
    low, high = (float(x.replace(",", "")) for x in re.search(r"\$([\d,]+)-([\d,]+)", store).groups())
    assert 0.019 * 79_000 < low <= high < 0.027 * 80_000, store  # Cloud Storage Standard list prices
    assert any("80,000 GB" in a and "object storage" in a for a in out["assumptions"]), out["assumptions"]
    assert out["estimated_monthly_cost_usd"]["max"] < 80_000 * 0.115  # 80 TB as database disk: $9,200 a month


def test_each_cloud_prices_files_at_its_own_object_storage():
    assert "aws.amazon.com/s3/pricing" in _line(_run(files=True, cloud="aws"), "Object storage")
    assert "azure.microsoft.com/en-us/pricing/details/storage/blobs" in _line(_run(files=True, cloud="azure"),
                                                                              "Object storage")


def test_without_uploads_the_whole_volume_is_database_data():
    out = _run(files=False)
    assert _gb(_line(out, "Database:")) == 80_000
    assert "SHARDING_PLAN" in {w["code"] for w in out["warnings"]}
    assert not _line(out, "Object storage")


def test_a_small_total_stays_in_the_database():
    out = _run(files=True, gb=2)
    assert _gb(_line(out, "Database:")) == 2
    assert not _line(out, "Object storage")
