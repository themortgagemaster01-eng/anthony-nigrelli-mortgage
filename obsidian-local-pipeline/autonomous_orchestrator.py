#!/usr/bin/env python3
"""
Obsidian Labs - Autonomous Lead Generation Orchestrator (v2)
Runs nightly: Scrape -> Grade -> Multi-Agent Demo Build
-> Media Enhancement -> Outreach Draft

Human approval required before any outreach is sent. Nothing in this file ever sends anything.
"""
from __future__ import annotations

import csv
import json
import logging
import os
import subprocess
import sys
import time
import datetime as dt
from logging.handlers import RotatingFileHandler
from pathlib import Path

try:
    import schedule
except ImportError:
    print("Missing dependency: pip install schedule")
    sys.exit(1)

try:
    import requests  # only needed for Telegram; degrade gracefully if absent
except ImportError:
    requests = None

# ---------------------------------------------------------------------------
# Paths & config
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
LOGS_DIR = OUTPUT_DIR / "logs"
SEEN_FILE = OUTPUT_DIR / "seen_leads.json"
LEADS_GRADED_CSV = OUTPUT_DIR / "leads_graded.csv"

STAGE_TIMEOUT = int(os.environ.get("OL_STAGE_TIMEOUT", "1800"))
NIGHTLY_LIMIT = int(os.environ.get("OL_NIGHTLY_LIMIT", "5"))
RUN_AT = os.environ.get("OL_RUN_AT", "02:00")
TELEGRAM_TOKEN = os.environ.get("OL_TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("OL_TELEGRAM_CHAT_ID", "")

# ---------------------------------------------------------------------------
# Logging (rotating file + console)
# ---------------------------------------------------------------------------
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("obsidian_orchestrator")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = RotatingFileHandler(
        LOGS_DIR / "nightly_runs.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(message)s"))
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(ch)


def log(msg: str, level: str = "info"):
    getattr(logger, level)(msg)


def notify(msg: str):
    """Best-effort Telegram ping. Never raises."""
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID and requests):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"[Obsidian Labs] {msg}"},
            timeout=10,
        )
    except Exception as e:
        log(f"Telegram notify failed: {e}", "warning")


def load_seen() -> set:
    if SEEN_FILE.exists():
        try:
            return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
        except Exception as e:
            log(f"Could not read seen file, starting fresh: {e}", "warning")
    return set()


def save_seen(seen: set):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(sorted(seen), indent=2), encoding="utf-8")


def mark_seen(new_keys):
    seen = load_seen()
    before = len(seen)
    seen.update(new_keys)
    save_seen(seen)
    log(f"Dedup: {len(seen) - before} new lead(s) recorded, {len(seen)} total known.")


def load_graded_leads() -> list[dict]:
    if LEADS_GRADED_CSV.exists():
        with LEADS_GRADED_CSV.open(newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    json_path = OUTPUT_DIR / "graded_leads.json"
    if json_path.exists():
        return json.loads(json_path.read_text(encoding="utf-8"))
    return []


def lead_key(lead: dict) -> str:
    return lead.get("place_id") or f"{lead.get('name', '')}|{lead.get('town', '')}"


class StageError(RuntimeError):
    pass


def run_stage(script: str, args: list | None = None) -> str:
    cmd = [sys.executable, script] + (args or [])
    log(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=STAGE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise StageError(f"{script} timed out after {STAGE_TIMEOUT}s")

    if result.returncode != 0:
        raise StageError(
            f"{script} failed (exit {result.returncode}): {result.stderr.strip()}"
        )

    if result.stdout.strip():
        log(result.stdout.strip())
    return result.stdout


def nightly_autonomous_run(limit: int = NIGHTLY_LIMIT):
    start = dt.datetime.now()
    log(f"=== STARTING NIGHTLY RUN for {limit} businesses ===")
    notify(f"Nightly run started ({limit} businesses).")
    try:
        log("Stage 1: Scraping local businesses...")
        run_stage("pipeline.py", ["--stage", "scrape", "--limit", str(limit)])

        log("Stage 2: Grading leads...")
        run_stage("pipeline.py", ["--stage", "grade"])

        graded = load_graded_leads()
        seen = load_seen()
        fresh_leads = []
        for lead in graded:
            key = lead_key(lead)
            if key and key not in seen:
                fresh_leads.append((key, lead))

        if not graded:
            log(
                "No graded leads found (output/leads_graded.csv missing/empty).",
                "warning",
            )

        log(f"Dedup gate: {len(fresh_leads)} of {len(graded)} graded leads are new.")

        if graded and not fresh_leads:
            log("No new leads tonight - skipping demo/media/outreach stages.")
            notify("Nightly run finished: no new leads to process.")
            return

        log("Stage 3: Generating demos (demo_gen_local.py)...")
        run_stage("demo_gen_local.py", ["--limit", str(limit)])

        media_script = ROOT / "media_enhancer.py"
        if media_script.exists():
            log("Stage 4: Media enhancement...")
            run_stage("media_enhancer.py", ["--limit", str(limit)])
        else:
            log("Stage 4: media_enhancer.py not found - skipping.", "warning")

        outreach_script = ROOT / "outreach_generator.py"
        if outreach_script.exists():
            log("Stage 5: Outreach drafts ($1,495 pitch)...")
            run_stage("outreach_generator.py", ["--limit", str(limit)])
        else:
            log("Stage 5: outreach_generator.py not found - skipping.", "warning")

        if fresh_leads:
            mark_seen(k for k, _ in fresh_leads)

        elapsed = (dt.datetime.now() - start).total_seconds()
        log(f"=== NIGHTLY RUN COMPLETE ({elapsed:.0f}s) ===")
        log(
            "Check dashboard for results. Human approval required before sending any outreach."
        )
        notify(
            f"Nightly run complete in {elapsed:.0f}s. "
            f"{len(fresh_leads)} new lead(s). Awaiting approval."
        )

    except StageError as e:
        log(f"RUN ABORTED: {e}", "error")
        notify(f"RUN ABORTED: {e}")
    except Exception as e:
        log(f"UNEXPECTED ERROR: {e}", "error")
        notify(f"UNEXPECTED ERROR: {e}")


schedule.every().day.at(RUN_AT).do(nightly_autonomous_run, limit=NIGHTLY_LIMIT)


if __name__ == "__main__":
    if "--now" in sys.argv:
        nightly_autonomous_run(NIGHTLY_LIMIT)
        sys.exit(0)

    print("Obsidian Labs Autonomous Orchestrator (v2) started.")
    print(f"Scheduled nightly at {RUN_AT} for {NIGHTLY_LIMIT} businesses.")
    print("Run once now: python autonomous_orchestrator.py --now")
    print("Press Ctrl+C to stop.")
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            log(f"SCHEDULER LOOP ERROR: {e}", "error")
        time.sleep(60)
