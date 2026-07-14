#!/usr/bin/env python3
"""
import_demos.py - pull previously-built demo websites into the dashboard.

The dashboard shows demos from output/demos/<slug>/index.html. Your past demos
live as HTML files in your Google Drive / Obsidian (Shipper) vault / a local
seed_demos/ folder, under a mix of names, e.g.:
    demo_wallys-super-service.html
    demo_wallys-super-service_v2-imagery.html
    makeover_homestyle-desserts-bakery.html
    salon-uccelli.html (demo code)
    degasperi.html (flagship demo code)
This script finds them (whatever they're named), copies each into the dashboard,
and it picks them up immediately (no backend changes).

By default it scans (shallow - top level only, so it stays fast):
  - ./seed_demos/            (drop any demo HTML here to force-include it)
  - GDRIVE_PATH from .env    (your Google Drive root)
  - GDRIVE_PATH/demos
  - OBSIDIAN_VAULT_PATH from .env   (your Shipper Vault)

Usage
-----
    python import_demos.py                # scan the default locations
    python import_demos.py --recursive    # also scan subfolders
    python import_demos.py a.html "b.html (demo code)"   # import specific files
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
OUTPUT_DEMOS = ROOT / "output" / "demos"
SEED_DEMOS = ROOT / "seed_demos"
load_dotenv(ROOT / ".env", encoding="utf-8-sig")

# A file is a candidate demo if its name contains ".html" anywhere (covers
# "salon-uccelli.html (demo code)") and it isn't one of the app's own files.
EXCLUDE_SUBSTRINGS = (
    "dashboard", "tesla_style_dashboard", "manifest", "sw.js",
    "_preview", "mortgage-calculator", "index.html",
)
# Name hints that mark a file as one of our demos.
DEMO_NAME_HINTS = ("demo", "makeover", "flagship")
# Content signatures of an Obsidian Labs demo (belt-and-suspenders detection).
WATERMARK_HINTS = ("obsidianlabshq", "built by obsidian labs", "preview built by obsidian labs")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "demo"


def has_html(path: Path) -> bool:
    return ".html" in path.name.lower()


def is_excluded(path: Path) -> bool:
    low = path.name.lower()
    return any(x in low for x in EXCLUDE_SUBSTRINGS)


def looks_like_demo(path: Path) -> bool:
    if not path.is_file() or not has_html(path) or is_excluded(path):
        return False
    if path.parent.name == "seed_demos":
        return True
    low = path.name.lower()
    if any(h in low for h in DEMO_NAME_HINTS):
        return True
    # Fall back to a content check for cleanly-named demos (e.g. salon-uccelli).
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:4000].lower()
    except Exception:
        return False
    if any(w in head for w in WATERMARK_HINTS):
        return True
    # A standalone HTML document that isn't an app file - treat as a demo.
    return "<!doctype html" in head or "<html" in head


def demo_slug(path: Path) -> str:
    name = path.name
    i = name.lower().find(".html")
    if i != -1:
        name = name[:i]               # drop ".html" and any "(demo code)" tail
    name = re.sub(r"^(demo|makeover)[ _-]+", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[ _-]+v\d+([ _-]+imagery)?$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"[ _-]+(flagship|imagery|final|demo[ _-]?code)$", "", name, flags=re.IGNORECASE)
    return slugify(name)


def scan_dir(d: Path, recursive: bool) -> list[Path]:
    if not d.exists():
        return []
    it = d.rglob("*") if recursive else d.glob("*")
    return [p for p in it if looks_like_demo(p)]


def default_locations() -> list[Path]:
    locs = [SEED_DEMOS]
    gdrive = os.getenv("GDRIVE_PATH", "").strip().strip('"').strip("'")
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip().strip('"').strip("'")
    if gdrive:
        locs += [Path(gdrive), Path(gdrive) / "demos"]
    if vault:
        locs.append(Path(vault))
    return locs


def main() -> None:
    parser = argparse.ArgumentParser(description="Import past demo websites into the dashboard")
    parser.add_argument("files", nargs="*", help="Specific demo HTML files to import")
    parser.add_argument("--recursive", action="store_true", help="Scan subfolders too (slower)")
    args = parser.parse_args()

    OUTPUT_DEMOS.mkdir(parents=True, exist_ok=True)
    SEED_DEMOS.mkdir(parents=True, exist_ok=True)

    found: list[Path] = []
    if args.files:
        found = [Path(f) for f in args.files if Path(f).is_file()]
    else:
        for d in default_locations():
            found += scan_dir(d, args.recursive)

    # Group by slug; when several files map to the same business (e.g. plain +
    # _v2-imagery), keep the largest file - usually the richer, later version.
    best: dict[str, Path] = {}
    for p in found:
        slug = demo_slug(p)
        cur = best.get(slug)
        if cur is None or p.stat().st_size > cur.stat().st_size:
            best[slug] = p

    if not best:
        print(
            "[import_demos] No demo files found.\n"
            "  Put demo HTML in seed_demos/, or set GDRIVE_PATH / OBSIDIAN_VAULT_PATH in .env\n"
            "  to the folders that hold your existing demos, then re-run."
        )
        return

    for slug, src in sorted(best.items()):
        dest_dir = OUTPUT_DEMOS / slug
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copyfile(src, dest_dir / "index.html")
            print(f"[import_demos] {src.name}  ->  output/demos/{slug}/index.html")
        except Exception as e:
            print(f"[import_demos] ! failed on {src}: {e}", file=sys.stderr)

    print(
        f"[import_demos] Done. Imported {len(best)} demo(s): {', '.join(sorted(best))}. "
        "Refresh the dashboard to see them."
    )


if __name__ == "__main__":
    main()
