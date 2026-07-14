#!/usr/bin/env python3
"""
import_demos.py - pull previously-built demo websites into the dashboard.

The dashboard shows demos from output/demos/<slug>/index.html. Your past demos
live as `demo_<name>.html` files in your Google Drive / Obsidian vault / a local
seed_demos/ folder. This script scans those locations, copies each demo into the
right place, and the dashboard picks them up immediately (no backend changes).

By default it scans (shallow, top level only, so it stays fast):
  - ./seed_demos/                     (drop any .html demos here to include them)
  - GDRIVE_PATH from .env             (your Google Drive root - where demo_*.html live)
  - GDRIVE_PATH/demos
  - OBSIDIAN_VAULT_PATH from .env

Usage
-----
    python import_demos.py                  # scan the default locations
    python import_demos.py --recursive      # also scan subfolders
    python import_demos.py path\\to\\a\\demo.html [more.html ...]   # import specific files
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

# Never treat these as "demos" even though they're .html.
EXCLUDE_PREFIXES = ("dashboard", "tesla_style_dashboard", "index")
EXCLUDE_SUBSTRINGS = ("_preview", "manifest")


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "demo"


def demo_slug_from_filename(path: Path) -> str:
    stem = path.stem
    # drop a leading "demo_" / "demo-" label if present
    stem = re.sub(r"^demo[_-]+", "", stem, flags=re.IGNORECASE)
    return slugify(stem)


def looks_like_demo(path: Path) -> bool:
    if path.suffix.lower() != ".html":
        return False
    low = path.name.lower()
    if any(low.startswith(p) for p in EXCLUDE_PREFIXES):
        return False
    if any(s in low for s in EXCLUDE_SUBSTRINGS):
        return False
    # Prefer the clear signal (files the pipeline/humans named demo_*), but also
    # accept any other .html sitting in an explicit seed_demos/ folder.
    return low.startswith("demo_") or low.startswith("demo-") or path.parent.name == "seed_demos"


def scan_dir(d: Path, recursive: bool) -> list[Path]:
    if not d.exists():
        return []
    it = d.rglob("*.html") if recursive else d.glob("*.html")
    return [p for p in it if p.is_file() and looks_like_demo(p)]


def default_locations() -> list[Path]:
    locs = [SEED_DEMOS]
    gdrive = os.getenv("GDRIVE_PATH", "").strip().strip('"').strip("'")
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip().strip('"').strip("'")
    if gdrive:
        locs += [Path(gdrive), Path(gdrive) / "demos"]
    if vault:
        locs.append(Path(vault))
    return locs


def import_file(src: Path) -> str:
    slug = demo_slug_from_filename(src)
    dest_dir = OUTPUT_DEMOS / slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest_dir / "index.html")
    return slug


def main() -> None:
    parser = argparse.ArgumentParser(description="Import past demo websites into the dashboard")
    parser.add_argument("files", nargs="*", help="Specific demo .html files to import")
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

    # de-dupe by resolved path
    seen, unique = set(), []
    for p in found:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(p)

    if not unique:
        print(
            "[import_demos] No demo files found.\n"
            "  Put demo_*.html files in seed_demos/, or set GDRIVE_PATH/OBSIDIAN_VAULT_PATH\n"
            "  in .env to the folders that hold your existing demos, then re-run.",
        )
        return

    imported = []
    for src in unique:
        try:
            slug = import_file(src)
            imported.append((src.name, slug))
            print(f"[import_demos] {src.name}  ->  output/demos/{slug}/index.html")
        except Exception as e:
            print(f"[import_demos] ! failed on {src}: {e}", file=sys.stderr)

    print(f"[import_demos] Done. Imported {len(imported)} demo(s). Refresh the dashboard to see them.")


if __name__ == "__main__":
    main()
