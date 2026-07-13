#!/usr/bin/env python3
"""
pipeline.py — Obsidian Labs Local AI Automation System (Predator Helios 300 Edition)
Main CLI orchestrator.

Runs the lead-gen -> grading -> RAG ingest -> demo generation -> outreach
drafting -> dashboard pipeline end-to-end, or any single stage in isolation.

Every stage is invoked as a subprocess so each script can also be run
standalone for debugging (e.g. `python scraper.py --towns Mahopac`).

Usage examples
--------------
    # Full pipeline for two towns, two niches, 5 leads per niche/town combo
    python pipeline.py --towns Mahopac "Carmel" --niches "dentist" "roofer" --limit 5

    # Just re-run grading on an existing leads.csv
    python pipeline.py --stage grade

    # Rebuild the RAG index after adding new docs to Drive/Obsidian
    python pipeline.py --stage rag_ingest

    # Launch the review dashboard
    python pipeline.py --stage dashboard
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable

STAGES = ["scrape", "grade", "rag_ingest", "demo", "outreach", "dashboard"]


def run_step(name: str, cmd: list[str]) -> None:
    """Run a subprocess step, streaming output, and abort the pipeline on failure."""
    print(f"\n{'=' * 70}\n>> STAGE: {name}\n   $ {' '.join(cmd)}\n{'=' * 70}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        print(f"\n[pipeline.py] Stage '{name}' exited with code {result.returncode}. Stopping.")
        sys.exit(result.returncode)


def stage_scrape(args: argparse.Namespace) -> None:
    cmd = [PYTHON, "scraper.py", "--limit", str(args.limit)]
    if args.towns:
        cmd += ["--towns", *args.towns]
    if args.niches:
        cmd += ["--niches", *args.niches]
    run_step("scrape", cmd)


def stage_grade(args: argparse.Namespace) -> None:
    run_step("grade", [PYTHON, "grader.py"])


def stage_rag_ingest(args: argparse.Namespace) -> None:
    run_step("rag_ingest", [PYTHON, "rag_setup.py"])


def stage_demo(args: argparse.Namespace) -> None:
    run_step("demo", [PYTHON, "demo_gen_local.py"])


def stage_outreach(args: argparse.Namespace) -> None:
    run_step("outreach", [PYTHON, "outreach_local.py"])


def stage_dashboard(args: argparse.Namespace) -> None:
    # streamlit run blocks/serves — don't wrap in run_step's return-code check logic,
    # just hand control over directly so Ctrl+C behaves normally.
    print(f"\n{'=' * 70}\n>> STAGE: dashboard (http://localhost:8501)\n{'=' * 70}")
    subprocess.run(["streamlit", "run", "dashboard.py"], cwd=str(ROOT))


STAGE_FUNCS = {
    "scrape": stage_scrape,
    "grade": stage_grade,
    "rag_ingest": stage_rag_ingest,
    "demo": stage_demo,
    "outreach": stage_outreach,
    "dashboard": stage_dashboard,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Obsidian Labs Local AI Automation System — pipeline orchestrator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--towns",
        nargs="+",
        default=[],
        help='Towns to search, e.g. --towns Mahopac "Putnam Valley" Carmel',
    )
    parser.add_argument(
        "--niches",
        nargs="+",
        default=[],
        help='Business niches to search, e.g. --niches dentist roofer "hair salon"',
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Max leads to fetch per town/niche combination in the scrape stage",
    )
    parser.add_argument(
        "--stage",
        choices=STAGES + ["all"],
        default="all",
        help="Which pipeline stage to run",
    )
    args = parser.parse_args()

    if args.stage == "all":
        # dashboard is excluded from "all" since it's a long-running server,
        # not a batch step. Run it explicitly with --stage dashboard.
        for stage in ["scrape", "grade", "rag_ingest", "demo", "outreach"]:
            STAGE_FUNCS[stage](args)
        print(
            "\nAll batch stages complete. Run `python pipeline.py --stage dashboard` "
            "to review leads, demos, and outreach drafts before anything goes out."
        )
    else:
        STAGE_FUNCS[args.stage](args)


if __name__ == "__main__":
    main()
