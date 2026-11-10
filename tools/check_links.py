"""Check every cited URL in data/, README.md and report/*.md.

    python tools/check_links.py              # check all, exit 1 if any link is dead
    python tools/check_links.py --list       # only print the URLs that would be checked
    python tools/check_links.py --out links.tsv

A link is dead when it returns 404/410, cannot be reached after one retry, or serves a
"page not found" page with status 200. Sites that refuse automated requests (401/403/429)
are reported as "blocked" for a manual check but do not fail the run.
Needs internet access; the app itself never makes network requests.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL_RX = re.compile(r"https?://[^\s\"'<>)\]`]+")
SKIP = re.compile(r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)|^http://www\.w3\.org/2000/svg")
SOFT_404 = re.compile(r"<title>[^<]*(page not found|404|not found)[^<]*</title>", re.I)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
BLOCKED = {401, 403, 429}


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def collect(root: Path = ROOT) -> dict[str, list[str]]:
    """URL -> files that cite it."""
    found: dict[str, list[str]] = {}

    def add(url: str, where: str) -> None:
        url = url.rstrip(".,;:")
        if not SKIP.match(url):
            found.setdefault(url, [])
            if where not in found[url]:
                found[url].append(where)

    for p in sorted((root / "data").rglob("*.json")):
        rel = p.relative_to(root).as_posix()
        for s in _strings(json.loads(p.read_text(encoding="utf-8"))):
            for u in URL_RX.findall(s):
                add(u, rel)
    for p in [root / "README.md", *sorted((root / "report").glob("*.md"))]:
        if p.exists():
            rel = p.relative_to(root).as_posix()
            for u in URL_RX.findall(p.read_text(encoding="utf-8")):
                add(u, rel)
    return found


def check(url: str, timeout: float = 15) -> tuple[str, str]:
    """Return (verdict, detail) with verdict in ok / blocked / dead."""
    last = ""
    for attempt in range(2):
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*;q=0.8"})
        try:
            # A cookie jar per check: some documentation sites redirect until a cookie is set.
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            with opener.open(req, timeout=timeout) as resp:
                head = resp.read(65536).decode("utf-8", "replace")
                if SOFT_404.search(head):
                    return "dead", f"{resp.status} but the page says not found"
                return "ok", str(resp.status)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return "dead", str(e.code)
            if e.code in BLOCKED:
                return "blocked", f"{e.code} (refuses automated requests; check in a browser)"
            last = f"HTTP {e.code}"
        except Exception as e:  # DNS failure, timeout, TLS error
            last = f"{type(e).__name__}: {e}"
        if attempt == 0:
            time.sleep(2)
    return ("dead" if not last.startswith("HTTP 5") else "blocked"), last


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print the URLs and exit")
    ap.add_argument("--out", help="write a tab-separated report here")
    ap.add_argument("--workers", type=int, default=16)
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    urls = collect()
    if a.list:
        print("\n".join(sorted(urls)))
        return 0
    print(f"checking {len(urls)} URLs ...", flush=True)
    with ThreadPoolExecutor(a.workers) as pool:
        results = dict(zip(urls, pool.map(check, urls)))
    counts = {"ok": 0, "blocked": 0, "dead": 0}
    for url, (verdict, detail) in sorted(results.items()):
        counts[verdict] += 1
        if verdict != "ok":
            print(f"{verdict.upper():8} {url}  [{detail}]  cited in {', '.join(urls[url])}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write("url\tverdict\tdetail\tcited_in\n")
            for url, (verdict, detail) in sorted(results.items()):
                fh.write(f"{url}\t{verdict}\t{detail}\t{', '.join(urls[url])}\n")
    print(f"{counts['ok']} ok, {counts['blocked']} blocked (manual check), {counts['dead']} dead")
    return 1 if counts["dead"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
