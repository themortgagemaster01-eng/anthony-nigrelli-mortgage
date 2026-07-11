#!/usr/bin/env python3
"""
Obsidian Labs - Media Enhancement Module
Enhances real scraped photos (Pillow, $0 cost, fully local). Optional Unsplash stock
photo fallback if UNSPLASH_ACCESS_KEY is set. Stock video/music NOT implemented (would
need a paid API) - flagged as a TODO, not a silent no-op.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageEnhance

try:
    import requests
except ImportError:
    requests = None

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
DEMOS_DIR = OUTPUT_DIR / "demos"
ENV_PATH = ROOT / ".env"

load_dotenv(ENV_PATH, encoding="utf-8-sig")
UNSPLASH_ACCESS_KEY = os.environ.get("UNSPLASH_ACCESS_KEY", "")

NICHE_MOOD = {
    "dentist": ("modern dental clinic interior", "clean, professional, trustworthy"),
    "roofer": ("roofing contractor working on house", "rugged, dependable, craftsmanship"),
    "restaurant": ("warm restaurant interior dining", "warm, inviting, appetizing"),
    "bakery": ("artisan bakery fresh bread pastries", "warm, cozy, handmade"),
    "landscaping": ("landscaped garden lawn care", "fresh, natural, well-maintained"),
    "auto shop": ("modern auto repair garage", "precise, technical, dependable"),
    "salon": ("modern hair salon interior", "stylish, clean, upscale"),
    "gym": ("modern fitness gym interior", "energetic, motivating, clean"),
}
DEFAULT_MOOD = (
    "professional local business storefront",
    "clean, professional, trustworthy",
)


def pick_stock_query(niche: str) -> tuple[str, str]:
    niche_key = (niche or "").strip().lower()
    for key, val in NICHE_MOOD.items():
        if key in niche_key:
            return val
    return DEFAULT_MOOD


def enhance_existing_image(image_path: Path, output_path: Path) -> Path:
    img = Image.open(image_path).convert("RGB")
    img = ImageEnhance.Contrast(img).enhance(1.12)
    img = ImageEnhance.Sharpness(img).enhance(1.15)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, quality=92)
    return output_path


def fetch_stock_image(query: str, dest: Path) -> Path | None:
    if not UNSPLASH_ACCESS_KEY:
        print(
            "[media_enhancer] No UNSPLASH_ACCESS_KEY set in .env - skipping stock "
            "image fallback (get a free key at unsplash.com/developers if you want this).",
            file=sys.stderr,
        )
        return None
    if requests is None:
        print(
            "[media_enhancer] `requests` not installed - skipping stock fallback.",
            file=sys.stderr,
        )
        return None
    try:
        resp = requests.get(
            "https://api.unsplash.com/photos/random",
            params={"query": query, "orientation": "landscape"},
            headers={"Authorization": f"Client-ID {UNSPLASH_ACCESS_KEY}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        image_url = data.get("urls", {}).get("regular")
        if not image_url:
            return None
        img_resp = requests.get(image_url, timeout=20)
        img_resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        img = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
        img.save(dest, quality=92)
        return dest
    except Exception as e:
        print(f"[media_enhancer] Unsplash fetch failed: {e}", file=sys.stderr)
        return None


def process_lead_media(slug: str, niche: str = "") -> dict:
    lead_dir = DEMOS_DIR / slug
    photos_dir = lead_dir / "photos"
    enhanced_dir = lead_dir / "media" / "enhanced"

    result = {"slug": slug, "enhanced": [], "stock_fallback": None}

    real_photos = []
    if photos_dir.exists():
        real_photos = [
            p
            for p in photos_dir.iterdir()
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")
        ]

    if real_photos:
        for photo in real_photos:
            out_path = enhanced_dir / photo.name
            try:
                enhance_existing_image(photo, out_path)
                result["enhanced"].append(str(out_path))
            except Exception as e:
                print(
                    f"[media_enhancer] Failed to enhance {photo}: {e}",
                    file=sys.stderr,
                )
    else:
        query, mood = pick_stock_query(niche)
        stock_dest = enhanced_dir / "stock_fallback.jpg"
        fetched = fetch_stock_image(query, stock_dest)
        if fetched:
            result["stock_fallback"] = str(fetched)
            print(
                f"[media_enhancer] {slug}: no real photos found, "
                f"used stock fallback ({mood})."
            )
        else:
            print(
                f"[media_enhancer] {slug}: no real photos and no stock fallback available."
            )

    return result


def main():
    parser = argparse.ArgumentParser(description="Obsidian Labs media enhancement")
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Max number of demo folders to process",
    )
    parser.add_argument(
        "--lead-slug",
        type=str,
        default=None,
        help="Process a single lead by slug",
    )
    args = parser.parse_args()

    if not DEMOS_DIR.exists():
        print(f"[media_enhancer] No demos directory at {DEMOS_DIR} - nothing to do.")
        return

    if args.lead_slug:
        targets = [args.lead_slug]
    else:
        targets = sorted(p.name for p in DEMOS_DIR.iterdir() if p.is_dir())[: args.limit]

    if not targets:
        print("[media_enhancer] No demo folders found.")
        return

    for slug in targets:
        process_lead_media(slug)

    print(f"[media_enhancer] Processed {len(targets)} lead(s).")


if __name__ == "__main__":
    main()
