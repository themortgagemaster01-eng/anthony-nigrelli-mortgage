#!/usr/bin/env python3
"""
grader.py - Google PageSpeed Insights grader (BEST-EFFORT RE-IMPLEMENTATION)

>>> NOTE: Robert's original grader.py was not available to build from. This
>>> is a functional re-implementation of what the spec describes. Swap in
>>> your real grader.py from Google Drive for full fidelity (e.g. custom
>>> weighting of Core Web Vitals, desktop+mobile combined scoring, historical
>>> tracking) - this version covers the core interface: reads leads.csv,
>>> writes leads_graded.csv with a perf_score column.
>>>
>>> TODO(Robert): your real grader.py may exist in Google Drive as a
>>> .gdoc-linked script rather than a plain .py file, which local file tools
>>> can't read directly - if so, open it in Drive, copy the actual source,
>>> and paste it over this file. Not blocking for now.

Reads output/leads.csv, and for every lead with a website, runs it through
the Google PageSpeed Insights API (mobile strategy) to get a Lighthouse
performance score (0-100). Leads with no website, a dead/unreachable site,
or an API error get perf_score = 0 and are flagged as "no_website" so they
get prioritized as full-demo candidates downstream.

Requires GOOGLE_API_KEY in .env (PageSpeed Insights API uses the same
Google Cloud API key mechanism as Places, just enable "PageSpeed Insights
API" on the project too).

Usage
-----
    python grader.py
"""

from __future__ import annotations

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
LEADS_GRADED_CSV = OUTPUT_DIR / "leads_graded.csv"

PSI_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

GRADED_FIELDNAMES = [
    "name",
    "type",
    "town",
    "address",
    "phone",
    "rating",
    "review_count",
    "website",
    "place_id",
    "perf_score",
    "status",  # ok | no_website | unreachable | api_error
    "is_hot_lead",  # True if perf_score is low or there's no website - full-demo candidate
]

# perf_score at/below this threshold counts as a "hot lead" alongside no-website leads.
HOT_LEAD_PERF_THRESHOLD = 50


def load_api_key() -> str:
    # encoding="utf-8-sig" tolerates a leading UTF-8 BOM, which Windows
    # Notepad silently adds when saving with "UTF-8" encoding - a BOM
    # corrupts the first KEY=VALUE line for plain utf-8 parsing.
    load_dotenv(ROOT / ".env", encoding="utf-8-sig")
    key = os.getenv("GOOGLE_API_KEY", "").strip()
    if not key:
        print(
            "[grader.py] ERROR: GOOGLE_API_KEY is not set in .env. "
            "Copy .env.example to .env and add your Google API key "
            "(with PageSpeed Insights API enabled).",
            file=sys.stderr,
        )
        sys.exit(1)
    return key


def grade_website(url: str, api_key: str) -> tuple[int, str]:
    """Return (perf_score 0-100, status) for a given URL via PSI mobile audit."""
    if not url:
        return 0, "no_website"

    params = {
        "url": url,
        "strategy": "mobile",
        "category": "performance",
        "key": api_key,
    }
    try:
        resp = requests.get(PSI_URL, params=params, timeout=45)
        resp.raise_for_status()
        data = resp.json()
        score = (
            data.get("lighthouseResult", {})
            .get("categories", {})
            .get("performance", {})
            .get("score")
        )
        if score is None:
            return 0, "api_error"
        return round(score * 100), "ok"
    except requests.RequestException as e:
        print(f"[grader.py] Failed to grade {url}: {e}", file=sys.stderr)
        return 0, "unreachable"


def main() -> None:
    if not LEADS_CSV.exists():
        print(f"[grader.py] ERROR: {LEADS_CSV} not found. Run scraper.py first.", file=sys.stderr)
        sys.exit(1)

    api_key = load_api_key()

    with LEADS_CSV.open(newline="", encoding="utf-8") as f:
        leads = list(csv.DictReader(f))

    if not leads:
        print("[grader.py] leads.csv is empty - nothing to grade.")
        return

    graded = []
    for i, lead in enumerate(leads, start=1):
        website = (lead.get("website") or "").strip()
        print(f"[grader.py] ({i}/{len(leads)}) Grading {lead.get('name', '?')} - {website or 'NO WEBSITE'}")

        perf_score, status = grade_website(website, api_key)
        is_hot = (status != "ok") or (perf_score <= HOT_LEAD_PERF_THRESHOLD)

        lead["perf_score"] = perf_score
        lead["status"] = status
        lead["is_hot_lead"] = is_hot
        graded.append(lead)

        # PSI is slow (can take 10-30s per call) and rate-limited; be gentle.
        time.sleep(0.5)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with LEADS_GRADED_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=GRADED_FIELDNAMES)
        writer.writeheader()
        writer.writerows(graded)

    hot_count = sum(1 for lead in graded if lead["is_hot_lead"])
    print(f"[grader.py] Wrote {len(graded)} graded leads to {LEADS_GRADED_CSV} "
          f"({hot_count} hot leads - no site or perf_score <= {HOT_LEAD_PERF_THRESHOLD}).")


if __name__ == "__main__":
    main()
