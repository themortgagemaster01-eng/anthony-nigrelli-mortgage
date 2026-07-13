#!/usr/bin/env python3
"""
scraper.py - Google Places API lead scraper (BEST-EFFORT RE-IMPLEMENTATION)

>>> NOTE: Robert's original scraper.py was not available to build from. This
>>> is a functional, sensibly-designed re-implementation of what the spec
>>> describes. Swap in your real scraper.py from Google Drive for full
>>> fidelity to your existing pipeline (custom filters, dedupe logic against
>>> past runs, CRM sync, etc.) - this version covers the core interface:
>>> --towns / --niches / --limit in, output/leads.csv out.
>>>
>>> TODO(Robert): your real scraper.py may exist in Google Drive as a
>>> .gdoc/.gsheet-linked script rather than a plain .py file, which local
>>> file tools can't read directly - if so, open it in Drive, copy the
>>> actual source, and paste it over this file. Not blocking for now.

Uses the Google Places API (Text Search + Place Details) to find local
businesses by town + niche, and writes them to output/leads.csv.

Requires GOOGLE_API_KEY in .env with the "Places API" enabled.

Usage
-----
    python scraper.py --towns Mahopac "Putnam Valley" --niches dentist roofer --limit 5
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
LEADS_CSV = OUTPUT_DIR / "leads.csv"

PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

FIELDNAMES = [
    "name",
    "type",
    "town",
    "address",
    "phone",
    "rating",
    "review_count",
    "website",
    "place_id",
]


def load_api_key() -> str:
    # encoding="utf-8-sig" tolerates a leading UTF-8 BOM, which Windows
    # Notepad silently adds when saving with "UTF-8" encoding - a BOM
    # corrupts the first KEY=VALUE line for plain utf-8 parsing.
    load_dotenv(ROOT / ".env", encoding="utf-8-sig")
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        print(
            "[scraper.py] ERROR: GOOGLE_API_KEY is not set in .env. "
            "Copy .env.example to .env and add your Google Places API key.",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def text_search(query: str, api_key: str) -> list[dict]:
    """Run a Places Text Search query and return raw place results (one page)."""
    params = {"query": query, "key": api_key}
    resp = requests.get(PLACES_TEXT_SEARCH_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    status = data.get("status")
    if status not in ("OK", "ZERO_RESULTS"):
        print(f"[scraper.py] WARNING: Places API returned status={status} for query={query!r}: "
              f"{data.get('error_message', '')}", file=sys.stderr)
        return []
    return data.get("results", [])


def get_place_details(place_id: str, api_key: str) -> dict:
    """Fetch phone number + website for a place, which Text Search doesn't include."""
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,website,formatted_address",
        "key": api_key,
    }
    resp = requests.get(PLACES_DETAILS_URL, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "OK":
        return {}
    return data.get("result", {})


def scrape_town_niche(town: str, niche: str, limit: int, api_key: str) -> list[dict]:
    query = f"{niche} in {town}, NY"
    print(f"[scraper.py] Searching: {query!r}")
    results = text_search(query, api_key)[:limit]

    leads = []
    for place in results:
        place_id = place.get("place_id", "")
        details = get_place_details(place_id, api_key) if place_id else {}
        # Be polite to the API - Details is a separate billed call per place.
        time.sleep(0.1)

        website = details.get("website", "").strip()
        lead = {
            "name": place.get("name", "").strip(),
            "type": niche,
            "town": town,
            "address": details.get("formatted_address") or place.get("formatted_address", ""),
            "phone": details.get("formatted_phone_number", "").strip(),
            "rating": place.get("rating", ""),
            "review_count": place.get("user_ratings_total", ""),
            "website": website if website else "",  # blank = no site = full-demo candidate
            "place_id": place_id,
        }
        leads.append(lead)
    return leads


def write_leads_csv(leads: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # De-dupe by place_id (or name+town if place_id missing) in case the same
    # business surfaces under multiple niche queries.
    seen = set()
    deduped = []
    for lead in leads:
        key = lead.get("place_id") or f"{lead['name']}|{lead['town']}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(lead)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(deduped)

    print(f"[scraper.py] Wrote {len(deduped)} unique leads to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape local business leads via Google Places API")
    parser.add_argument("--towns", nargs="+", required=True, help="Towns to search, e.g. Mahopac Carmel")
    parser.add_argument("--niches", nargs="+", required=True, help="Niches to search, e.g. dentist roofer")
    parser.add_argument("--limit", type=int, default=5, help="Max leads per town/niche combo")
    args = parser.parse_args()

    if not args.towns or not args.niches:
        print("[scraper.py] --towns and --niches are required (and non-empty).", file=sys.stderr)
        sys.exit(1)

    api_key = load_api_key()

    all_leads: list[dict] = []
    for town in args.towns:
        for niche in args.niches:
            try:
                all_leads.extend(scrape_town_niche(town, niche, args.limit, api_key))
            except requests.RequestException as e:
                print(f"[scraper.py] Request failed for {town}/{niche}: {e}", file=sys.stderr)

    if not all_leads:
        print("[scraper.py] No leads found. Check your towns/niches or API key/quota.")

    write_leads_csv(all_leads, LEADS_CSV)


if __name__ == "__main__":
    main()
