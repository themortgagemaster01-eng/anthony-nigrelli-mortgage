#!/usr/bin/env python3
"""
make_demos_bundle.py - pack every demo website into ONE markdown file.

Produces DEMOS_BUNDLE.md containing the full HTML of every demo, with a table of
contents. Hand that one file to any Claude (or ChatGPT) chat and it can read,
compare, or reuse all your demos at once - "which salon demo did we do?", "match
this new lead to our closest demo", etc.

Run it after the importers have populated output/demos/ (START.bat does this for
you), or point it at any folders of demo HTML.

Sources scanned by default:
  - output/demos/<slug>/index.html   (what the dashboard serves)
  - seed_demos/*.html

Usage
-----
    python make_demos_bundle.py
    python make_demos_bundle.py --out DEMOS_BUNDLE.md
"""
from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_DEMOS = ROOT / "output" / "demos"
SEED_DEMOS = ROOT / "seed_demos"


def collect() -> list[tuple[str, Path]]:
    demos: dict[str, Path] = {}
    if OUTPUT_DEMOS.exists():
        for idx in sorted(OUTPUT_DEMOS.glob("*/index.html")):
            demos[idx.parent.name] = idx
    if SEED_DEMOS.exists():
        for html in sorted(SEED_DEMOS.glob("*.html")):
            demos.setdefault(html.stem, html)  # don't override an imported one
    return sorted(demos.items())


def fence_for(body: str) -> str:
    longest = run = 0
    for ch in body:
        if ch == "`":
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return "`" * max(3, longest + 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Bundle all demo websites into one markdown file")
    ap.add_argument("--out", default="DEMOS_BUNDLE.md", help="Output filename")
    args = ap.parse_args()

    demos = collect()
    out = ROOT / args.out

    if not demos:
        out.write_text(
            "# Demos bundle\n\nNo demos found yet. Run `python import_demos.py` and "
            "`python import_github_demos.py` first (or just launch START.bat), then re-run this.\n",
            encoding="utf-8",
        )
        print(f"[make_demos_bundle] No demos found. Wrote a placeholder to {out.name}.")
        return

    toc = "\n".join(f"- [{slug}](#{slug})" for slug, _ in demos)
    parts = [
        "# Obsidian Labs - All Demos (single file)\n",
        f"Every demo website we've built, in one place. {len(demos)} demo(s).\n",
        "Give this file to a Claude/ChatGPT chat to browse, compare, or match demos to new leads.\n",
        "\n## Contents\n",
        toc,
        "\n\n---\n",
    ]
    for slug, path in demos:
        body = path.read_text(encoding="utf-8", errors="ignore")
        fence = fence_for(body)
        parts.append(f"\n## {slug}\n\n_source: {path.relative_to(ROOT)} - {len(body):,} bytes_\n\n{fence}html\n{body}\n{fence}\n")

    out.write_text("".join(parts), encoding="utf-8")
    kb = out.stat().st_size / 1024
    print(f"[make_demos_bundle] Wrote {out.name}: {len(demos)} demos, {kb:.1f} KB -> {', '.join(s for s,_ in demos)}")


if __name__ == "__main__":
    main()
