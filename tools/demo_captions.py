"""Make a caption file for the demo video from the shot table in report/demo_script.md.

    python tools/demo_captions.py              # writes dist/demo_captions.srt
    python tools/demo_captions.py --out x.srt

Each row of the "Shots" table has a time range, the address or click path, what is on screen, and the spoken
line in the last column. The line is split into short captions that share the row's time evenly. Burn them in with ffmpeg (the command is in the script).
"""
from __future__ import annotations

import argparse
import re
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROW = re.compile(r"^\| (\d+):(\d\d)-(\d+):(\d\d) \| .* \| \"(.*)\" \|$")


def shots(script: Path | None = None) -> list[tuple[int, int, str]]:
    """(start second, end second, spoken line) for every row of the shot table."""
    text = (script or ROOT / "report" / "demo_script.md").read_text(encoding="utf-8")
    out = []
    for ln in text.splitlines():
        m = ROW.match(ln)
        if m:
            out.append((int(m[1]) * 60 + int(m[2]), int(m[3]) * 60 + int(m[4]), m[5]))
    return out


def stamp(sec: float) -> str:
    ms = round(sec * 1000)
    return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"


def captions(rows: list[tuple[int, int, str]]) -> list[tuple[float, float, str]]:
    out = []
    for start, end, line in rows:
        parts = [p for p in re.split(r"(?<=[.:;?!])\s+", line) if p]
        chunks = []
        for p in parts:
            chunks += textwrap.wrap(p, 84) or [p]
        step = (end - start) / max(len(chunks), 1)
        for i, c in enumerate(chunks):
            out.append((start + i * step, start + (i + 1) * step, c))
    return out


def srt(rows: list[tuple[int, int, str]]) -> str:
    lines = []
    for i, (a, b, c) in enumerate(captions(rows), 1):
        lines += [str(i), f"{stamp(a)} --> {stamp(b)}", textwrap.fill(c, 42), ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist" / "demo_captions.srt"))
    a = ap.parse_args()
    rows = shots()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(srt(rows), encoding="utf-8")
    print(f"{out}: {len(captions(rows))} captions over {rows[-1][1]} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
