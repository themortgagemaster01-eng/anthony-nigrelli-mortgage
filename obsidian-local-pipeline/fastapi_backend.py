#!/usr/bin/env python3
"""
Obsidian Labs - FastAPI backend for tesla_style_dashboard_with_chat.html
Serves live data from the same output/ folder dashboard.py reads, and shares the
same approvals log. The chat widget calls local Ollama directly - no external API.
Run:

    pip install fastapi uvicorn
    uvicorn fastapi_backend:app --port 8502 --reload
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    import requests
except ImportError:
    requests = None

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
DEMOS_DIR = OUTPUT_DIR / "demos"
OUTREACH_DIR = OUTPUT_DIR / "outreach"
LOGS_DIR = OUTPUT_DIR / "logs"
LEADS_GRADED_CSV = OUTPUT_DIR / "leads_graded.csv"
APPROVALS_LOG = LOGS_DIR / "approvals.csv"
PIPELINE_RUN_LOG = LOGS_DIR / "pipeline_run.log"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:14b-instruct-q4_K_M"

app = FastAPI(title="Obsidian Labs API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return slug or "lead"


def read_leads() -> list[dict]:
    if not LEADS_GRADED_CSV.exists():
        return []
    with LEADS_GRADED_CSV.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def list_demo_slugs() -> list[str]:
    if not DEMOS_DIR.exists():
        return []
    return sorted(
        p.name
        for p in DEMOS_DIR.iterdir()
        if p.is_dir() and (p / "index.html").exists()
    )


def list_outreach_slugs() -> list[str]:
    if not OUTREACH_DIR.exists():
        return []
    return sorted(p.stem for p in OUTREACH_DIR.glob("*.md"))


@app.get("/api/status")
def status():
    leads = read_leads()
    hot = sum(
        1
        for l in leads
        if str(l.get("is_hot_lead", "")).lower() in ("true", "1", "yes")
    )
    return {
        "leads": len(leads),
        "hot_leads": hot,
        "demos": len(list_demo_slugs()),
        "outreach_drafts": len(list_outreach_slugs()),
        "pricing": {
            "starter": 1495,
            "professional": 2500,
            "business_growth": "4500+",
        },
        "guardrails": "Runs 100% locally. Nothing auto-sends.",
    }


@app.get("/api/leads")
def get_leads():
    return read_leads()


@app.get("/api/demos")
def get_demos():
    return [{"slug": s} for s in list_demo_slugs()]


@app.get("/api/demos/{slug}")
def get_demo_html(slug: str):
    demo_file = DEMOS_DIR / slug / "index.html"
    if not demo_file.exists():
        raise HTTPException(status_code=404, detail=f"No demo found for '{slug}'")
    return {"slug": slug, "html": demo_file.read_text(encoding="utf-8")}


@app.get("/api/outreach")
def get_outreach():
    return [{"slug": s} for s in list_outreach_slugs()]


@app.get("/api/outreach/{slug}")
def get_outreach_draft(slug: str):
    draft_file = OUTREACH_DIR / f"{slug}.md"
    if not draft_file.exists():
        raise HTTPException(
            status_code=404, detail=f"No outreach draft found for '{slug}'"
        )
    return {"slug": slug, "content": draft_file.read_text(encoding="utf-8")}


class ApprovalRequest(BaseModel):
    kind: str
    identifier: str


@app.post("/api/approve")
def approve(req: ApprovalRequest):
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    is_new = not APPROVALS_LOG.exists()
    with APPROVALS_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "kind", "identifier"])
        writer.writerow(
            [
                dt.datetime.now().isoformat(timespec="seconds"),
                req.kind,
                req.identifier,
            ]
        )
    return {"status": "logged", "kind": req.kind, "identifier": req.identifier}


class RunPipelineRequest(BaseModel):
    stage: str = "all"
    towns: list[str] = ["Mahopac", "Carmel"]
    niches: list[str] = ["dentist", "roofer"]
    limit: int = 5


@app.post("/api/run-pipeline")
def run_pipeline(req: RunPipelineRequest):
    cmd = [sys.executable, "pipeline.py", "--stage", req.stage]
    if req.stage in ("all", "scrape"):
        cmd += [
            "--towns",
            *req.towns,
            "--niches",
            *req.niches,
            "--limit",
            str(req.limit),
        ]

    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with PIPELINE_RUN_LOG.open("a", encoding="utf-8") as log_f:
        log_f.write(
            f"\n\n=== {dt.datetime.now().isoformat(timespec='seconds')} "
            f"- {' '.join(cmd)} ===\n"
        )
        subprocess.Popen(
            cmd, cwd=str(ROOT), stdout=log_f, stderr=subprocess.STDOUT
        )

    return {"status": "started", "command": " ".join(cmd)}


class ChatRequest(BaseModel):
    message: str


@app.post("/api/chat")
def chat(req: ChatRequest):
    if requests is None:
        raise HTTPException(
            status_code=500, detail="`requests` not installed on the backend."
        )

    live_status = status()
    system_context = (
        "You are the Obsidian Labs assistant embedded in the pipeline dashboard. "
        "You help the site owner understand their local lead-gen pipeline. Be concise, "
        "concrete, and never claim to have sent anything - this system never auto-sends. "
        f"Live stats right now: {json.dumps(live_status)}. "
        "Pricing: Starter $1,495 / Professional $2,500 (most popular) / Business Growth $4,500+."
    )

    prompt = f"{system_context}\n\nUser question: {req.message}\n\nAnswer:"

    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return {"reply": data.get("response", "").strip()}
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Could not reach local Ollama at {OLLAMA_URL} - "
                f"is `ollama serve` running? ({e})"
            ),
        )


@app.get("/")
def root():
    return {
        "service": "Obsidian Labs API",
        "docs": "/docs",
        "note": (
            "Serves tesla_style_dashboard_with_chat.html. "
            "Streamlit dashboard.py still works independently."
        ),
    }
