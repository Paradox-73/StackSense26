"""Offline checks on cited URLs (tools/check_links.py does the live check)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from check_links import collect  # noqa: E402

KNOWN_DEAD = [
    "https://www.cncf.io/blog/2021/03/10/cloud-native-portability/",
    "https://developer.apple.com/xcode/swiftui/",
    "https://www.starlette.io/",
    "https://www.uvicorn.org/",
]


def test_collects_cited_urls():
    urls = collect()
    assert len(urls) > 200
    assert all(u.startswith(("http://", "https://")) for u in urls)
    assert not any("127.0.0.1" in u or "localhost" in u for u in urls)


def test_known_dead_links_replaced():
    urls = collect()
    assert [u for u in KNOWN_DEAD if u in urls] == []
