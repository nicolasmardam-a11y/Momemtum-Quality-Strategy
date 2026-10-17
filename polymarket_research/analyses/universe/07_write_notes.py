"""Assemble notes/strategies/universe.md from the pre-registered section 0 (kept verbatim), the hand-written
template (analyses/universe/universe_notes_template.md) and tables copied from 05_stats output.

Marker syntax in the template: <<T:heading>> or <<T:heading|sub-heading>>; the first markdown table that follows
that heading (and sub-heading) in analyses/universe/out/05_stats_output.md is inserted, with integer-valued floats
>= 2 printed as integers.
Run from polymarket_research/: python analyses/universe/07_write_notes.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
NOTE = ROOT / "notes" / "strategies" / "universe.md"


def table_after(lines: list[str], start: int) -> str:
    i = start
    while i < len(lines) and not lines[i].startswith("|"):
        i += 1
    out = []
    while i < len(lines) and lines[i].startswith("|"):
        out.append(lines[i])
        i += 1
    if not out:
        raise ValueError(f"no table after line {start}")
    return "\n".join(out)


def tidy(t: str) -> str:
    def f(m):
        v = float(m.group(0).replace(",", ""))
        return f"{int(round(v)):,}" if v >= 2 and abs(v - round(v)) < 1e-9 else m.group(0)
    return re.sub(r"(?<![\w.])\d[\d,]*\.\d+(?![\w.])", f, t)


def main() -> None:
    stats = (HERE / "out" / "05_stats_output.md").read_text().splitlines()
    tpl = (HERE / "universe_notes_template.md").read_text()
    old = NOTE.read_text()
    cut = old.find("\n_Section 0 was written")
    sec0 = old if cut < 0 else old[:cut]
    sec0 = sec0.rstrip() + "\n"

    def fill(m):
        parts = m.group(1).split("|")
        idx = next(i for i, l in enumerate(stats) if l.startswith(parts[0]))
        for sub in parts[1:]:
            idx = next(i for i in range(idx + 1, len(stats)) if stats[i].startswith(sub))
        return tidy(table_after(stats, idx + 1))

    body = re.sub(r"<<T:(.+?)>>", fill, tpl)
    NOTE.write_text(sec0 + body)
    print(f"wrote {NOTE} ({len(sec0 + body):,} chars)")


if __name__ == "__main__":
    main()
