# Obsidian Labs Pipeline — Code Review Bundle

_Everything a reviewer needs in one file. Generated for a second-opinion review._

## How to use this
Upload this file to ChatGPT (or paste it) with a prompt like:

> "You are a senior engineer doing a code review. This is a $0-cost, fully local
> AI lead-generation pipeline (scrape local businesses → grade their website →
> generate a demo site with a local LLM via Ollama → draft an outreach email →
> a human approves in a dashboard → the human sends manually; nothing auto-sends).
> Review the code below for correctness, security, and reliability. Point out bugs,
> risky edge cases, and anything that would break when the base 'engine' files are
> wired in. Then suggest concrete improvements, prioritized."

## Architecture in one picture
```
                 ENGINE (source NOT in this bundle — lives in the
                 obsidian-local-pipeline GitHub repo)
   pipeline.py ── scraper.py ── grader.py ── rag_setup.py ── demo_gen_local.py
        │                                                          │
        └──────────────── writes to  output/  ────────────────────┘
                                    │
   ────────────────────────────────┼──────────────────────────────
                 NEW FILES (full source below, reconstructed)
                                    │
   autonomous_orchestrator.py  (nightly scheduler: runs the engine stages)
   media_enhancer.py           (Pillow photo enhance + optional Unsplash)
   outreach_generator.py       (local Ollama drafts, RAG-grounded)
   fastapi_backend.py          (reads output/, serves the dashboard on :8502)
   tesla_style_dashboard_with_chat.html  (phone PWA dashboard + chat)
   manifest.json / sw.js       (installable PWA shell)
```

## What the reviewer should know
- **Two halves.** The "engine" (pipeline.py, scraper.py, grader.py, rag_setup.py,
  demo_gen_local.py, dashboard.py, templates/) already exists in the original repo;
  its **source is not included here** because it wasn't in the handoff document.
  The files below are the **new dashboard + automation layer**, which call the engine.
- **Contract between the halves:** the engine writes to `output/` —
  `output/leads_graded.csv` (or `output/graded_leads.json`), `output/demos/<slug>/index.html`,
  and `output/outreach/<slug>.md`. The new files only ever read those.
- **Guardrail:** nothing in any of these files sends an email. "Approve" only logs
  to `output/logs/approvals.csv`.
- **Known not-yet-built** (flagged honestly, need engine source or a paid API):
  the multi-agent Architect→Builder→Reviewer upgrade to demo_gen_local.py, and
  stock video/music in media_enhancer.py.

## Engine files (source not available — descriptions only, for context)
| File | Purpose |
| --- | --- |
| pipeline.py | Orchestrator: scrape → grade stages |
| scraper.py | Finds local businesses (Google Places) |
| grader.py | Scores each business's current website (PageSpeed) |
| rag_setup.py | Builds the local chroma_db index from Drive/Obsidian docs |
| demo_gen_local.py | Generates a personalized demo site via local LLM + RAG |
| dashboard.py | Original Streamlit dashboard |
| templates/ | Design-standards and outreach-voice prompts |

---

# New files — full source

## `autonomous_orchestrator.py`  
_(240 lines)_

```python
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

```

## `media_enhancer.py`  
_(183 lines)_

```python
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

```

## `outreach_generator.py`  
_(219 lines)_

```python
#!/usr/bin/env python3
"""
Obsidian Labs - Outreach Email Draft Generator ($1,495 Starter pitch)
Generates personalized outreach drafts using local Ollama, grounded in
templates/email_system_prompt.md and the RAG index. Writes to
output/outreach/<slug>.md - never sends anything.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
OUTREACH_DIR = OUTPUT_DIR / "outreach"
LEADS_GRADED_CSV = OUTPUT_DIR / "leads_graded.csv"
TEMPLATES_DIR = ROOT / "templates"
EMAIL_SYSTEM_PROMPT_PATH = TEMPLATES_DIR / "email_system_prompt.md"
ENV_PATH = ROOT / ".env"
CHROMA_DIR = ROOT / "chroma_db"

load_dotenv(ENV_PATH, encoding="utf-8-sig")
OLLAMA_MODEL = "qwen2.5:14b-instruct-q4_K_M"
EMBED_MODEL = "nomic-embed-text"

FALLBACK_SYSTEM_PROMPT = """You are writing cold outreach email drafts for Obsidian Labs, \
a web design agency. Tone: low-pressure, specific to the recipient's real business, never \
pushy, never claims to be AI-built. Pricing: Starter $1,495 / Professional $2,500 (most \
popular) / Business Growth $4,500+. Lead with a specific, real observation about their \
current site or online presence, not generic flattery. Keep it short - 4-6 sentences. \
End with a soft, easy next step (not a hard CTA)."""


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return slug or "lead"


def load_system_prompt() -> str:
    if EMAIL_SYSTEM_PROMPT_PATH.exists():
        return EMAIL_SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    print(
        f"[outreach_generator] No {EMAIL_SYSTEM_PROMPT_PATH} found - using a baked-in "
        "fallback voice/pricing prompt instead.",
        file=sys.stderr,
    )
    return FALLBACK_SYSTEM_PROMPT


def load_hot_leads(limit: int) -> list[dict]:
    if not LEADS_GRADED_CSV.exists():
        print(
            f"[outreach_generator] No {LEADS_GRADED_CSV} found - nothing to draft.",
            file=sys.stderr,
        )
        return []
    with LEADS_GRADED_CSV.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    hot = [
        r
        for r in rows
        if str(r.get("is_hot_lead", "")).strip().lower() in ("true", "1", "yes")
    ]
    return (hot or rows)[:limit]


def get_retriever():
    if not CHROMA_DIR.exists():
        return None
    try:
        from langchain_chroma import Chroma
        from langchain_ollama import OllamaEmbeddings

        embeddings = OllamaEmbeddings(model=EMBED_MODEL)
        return Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=embeddings,
        )
    except Exception as e:
        print(
            f"[outreach_generator] RAG retriever unavailable ({e}) - continuing without it.",
            file=sys.stderr,
        )
        return None


def retrieve_context(vectorstore, query: str, k: int = 3) -> str:
    if vectorstore is None:
        return ""
    try:
        docs = vectorstore.similarity_search(query, k=k)
        return "\n\n".join(d.page_content for d in docs)
    except Exception as e:
        print(f"[outreach_generator] RAG retrieval failed: {e}", file=sys.stderr)
        return ""


def build_prompt(lead: dict, system_prompt: str, retrieved_context: str) -> str:
    name = lead.get("name", "this business")
    town = lead.get("town", "")
    niche = lead.get("type", "local business")
    status = lead.get("status", "")
    perf = lead.get("perf_score", "")

    site_note = (
        "no live website"
        if status == "no_website"
        else f"a website scoring {perf}/100 on performance"
    )

    context_block = (
        "\n\nBackground context from past work (for tone/voice only, do not invent "
        f"facts about this specific business):\n{retrieved_context}"
        if retrieved_context
        else ""
    )

    return f"""{system_prompt}

Write ONE outreach email draft for:
Business name: {name}
Niche: {niche}
Town: {town}
Current site status: {site_note}
Subject line style example: "Quick question about your {niche} website in {town}"

{context_block}
Output format:
Subject: <subject line>
<email body>
"""


def generate_draft(lead: dict, llm, vectorstore, system_prompt: str) -> str:
    query = f"{lead.get('type', '')} outreach tone pricing"
    context = retrieve_context(vectorstore, query)
    prompt = build_prompt(lead, system_prompt, context)
    return llm.invoke(prompt)


def main():
    parser = argparse.ArgumentParser(description="Obsidian Labs outreach draft generator")
    parser.add_argument(
        "--limit", type=int, default=5, help="Max number of leads to draft for"
    )
    parser.add_argument(
        "--lead-slug",
        type=str,
        default=None,
        help="Draft for a single lead by slug",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even if a draft already exists",
    )
    args = parser.parse_args()

    try:
        from langchain_ollama import OllamaLLM
    except ImportError:
        print(
            "[outreach_generator] Missing dependency: pip install langchain-ollama",
            file=sys.stderr,
        )
        sys.exit(1)

    OUTREACH_DIR.mkdir(parents=True, exist_ok=True)
    system_prompt = load_system_prompt()
    vectorstore = get_retriever()
    llm = OllamaLLM(model=OLLAMA_MODEL)

    leads = load_hot_leads(limit=1000)
    if args.lead_slug:
        leads = [l for l in leads if slugify(l.get("name", "")) == args.lead_slug]
        if not leads:
            print(
                f"[outreach_generator] No lead found matching slug '{args.lead_slug}'.",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        leads = leads[: args.limit]

    if not leads:
        print("[outreach_generator] No leads to draft for.")
        return

    written = 0
    for lead in leads:
        slug = slugify(lead.get("name", ""))
        out_path = OUTREACH_DIR / f"{slug}.md"
        if out_path.exists() and not args.force:
            print(
                f"[outreach_generator] Skipping {slug} - draft already exists "
                "(use --force to regenerate)."
            )
            continue
        print(f"[outreach_generator] Drafting outreach for {lead.get('name')}...")
        try:
            draft = generate_draft(lead, llm, vectorstore, system_prompt)
        except Exception as e:
            print(f"[outreach_generator] FAILED for {slug}: {e}", file=sys.stderr)
            continue
        out_path.write_text(draft.strip() + "\n", encoding="utf-8")
        written += 1
        print(f"[outreach_generator] Wrote {out_path}")

    print(f"[outreach_generator] Done. {written} draft(s) written to {OUTREACH_DIR}.")


if __name__ == "__main__":
    main()

```

## `fastapi_backend.py`  
_(243 lines)_

```python
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

```

## `tesla_style_dashboard_with_chat.html`  
_(464 lines)_

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Obsidian Labs - Pipeline Dashboard</title>
  <link rel="manifest" href="manifest.json" />
  <link rel="icon" href="icon-192.png" />
  <link rel="apple-touch-icon" href="icon-192.png" />
  <meta name="theme-color" content="#f8f9fa" />
  <style>
    :root {
      --red: #cc0000;
      --red-dark: #a30000;
      --bg: #f8f9fa;
      --card: #ffffff;
      --border: #eee;
      --text: #111;
      --muted: #6b7280;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .wrap { max-width: 1400px; margin: 0 auto; padding: 1.5rem 2rem 4rem; }
    .topnav {
      display: flex; align-items: center; justify-content: space-between;
      padding-bottom: 1rem; border-bottom: 1px solid var(--border);
      margin-bottom: 1.5rem; gap: 1rem; flex-wrap: wrap;
    }
    .brand { font-weight: 700; font-size: 1.2rem; letter-spacing: -0.02em; }
    .navtabs { display: flex; gap: 0.25rem; flex-wrap: wrap; }
    .navtabs button {
      background: none; border: none; padding: 0.5rem 1rem; border-radius: 9999px;
      font-weight: 600; cursor: pointer; color: var(--muted);
    }
    .navtabs button.active { background: #111; color: white; }
    .navmeta { font-size: 0.8rem; color: var(--muted); text-align: right; }
    .metrics {
      display: grid; grid-template-columns: repeat(4, 1fr);
      gap: 1rem; margin-bottom: 1.5rem;
    }
    .metric-card {
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 1.25rem; box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    }
    .metric-card .label { font-size: 0.8rem; color: var(--muted); margin-bottom: 0.25rem; }
    .metric-card .value { font-size: 1.8rem; font-weight: 700; letter-spacing: -0.02em; }
    .btn {
      border-radius: 9999px; padding: 0.6rem 1.6rem; font-weight: 600; border: none;
      background: var(--red); color: white; cursor: pointer; transition: all 0.15s;
    }
    .btn:hover { background: var(--red-dark); transform: translateY(-1px); }
    .btn.secondary { background: #eee; color: #111; }
    .btn:disabled { opacity: 0.4; cursor: not-allowed; transform: none; }
    .section {
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      padding: 1.5rem; margin-bottom: 1.5rem;
    }
    .section h2 { margin-top: 0; font-size: 1.1rem; }
    .two-col { display: grid; grid-template-columns: 2fr 3fr; gap: 1.5rem; }
    @media (max-width: 900px) {
      .two-col { grid-template-columns: 1fr; }
      .metrics { grid-template-columns: repeat(2, 1fr); }
    }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th, td { text-align: left; padding: 0.5rem 0.5rem; border-bottom: 1px solid var(--border); }
    tr.lead-row { cursor: pointer; }
    tr.lead-row:hover { background: #fafafa; }
    .pill {
      display: inline-block; padding: 3px 10px; border-radius: 9999px;
      font-size: 0.75rem; font-weight: 600;
    }
    .pill-red { background: #ef4444; color: #fff; }
    .pill-amber { background: #f59e0b; color: #111; }
    .pill-green { background: #22c55e; color: #111; }
    .pill-gray { background: #6b7280; color: #fff; }
    .device-toggle { display: flex; gap: 0.5rem; margin-bottom: 0.75rem; }
    .device-toggle button {
      padding: 0.35rem 0.9rem; border-radius: 9999px; border: 1px solid var(--border);
      background: white; cursor: pointer; font-size: 0.8rem;
    }
    .device-toggle button.active { background: #111; color: white; border-color: #111; }
    .preview-frame-wrap { display: flex; justify-content: center; }
    iframe#demo-preview {
      border: 1px solid var(--border); border-radius: 16px;
      width: 100%; height: 640px; background: white;
    }
    .draft-card {
      border: 1px solid var(--border); border-radius: 12px;
      padding: 1rem; margin-bottom: 0.75rem;
    }
    .draft-card pre { white-space: pre-wrap; font-family: inherit; font-size: 0.85rem; }
    #chat-toggle {
      position: fixed; bottom: 24px; right: 24px; width: 56px; height: 56px;
      border-radius: 50%; background: var(--red); color: white; border: none;
      font-size: 1.4rem; cursor: pointer; box-shadow: 0 4px 16px rgba(0,0,0,0.2); z-index: 50;
    }
    #chat-panel {
      position: fixed; bottom: 90px; right: 24px; width: 340px; max-height: 480px;
      background: var(--card); border: 1px solid var(--border); border-radius: 16px;
      box-shadow: 0 8px 32px rgba(0,0,0,0.18); display: none;
      flex-direction: column; z-index: 50; overflow: hidden;
    }
    #chat-panel.open { display: flex; }
    #chat-header { background: #111; color: white; padding: 0.75rem 1rem; font-weight: 600; }
    #chat-messages {
      flex: 1; overflow-y: auto; padding: 0.75rem 1rem; font-size: 0.85rem;
      display: flex; flex-direction: column; gap: 0.5rem;
    }
    .chat-msg { padding: 0.5rem 0.75rem; border-radius: 12px; max-width: 85%; }
    .chat-msg.user { align-self: flex-end; background: var(--red); color: white; }
    .chat-msg.bot { align-self: flex-start; background: #f1f1f1; color: #111; }
    #chat-input-row { display: flex; border-top: 1px solid var(--border); }
    #chat-input { flex: 1; border: none; padding: 0.75rem; font-size: 0.85rem; }
    #chat-send { border: none; background: var(--red); color: white; padding: 0 1rem; cursor: pointer; }
    .muted { color: var(--muted); font-size: 0.85rem; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="topnav">
      <div class="brand">&#9632; Obsidian Labs</div>
      <div class="navtabs">
        <button data-page="dashboard" class="active">Dashboard</button>
        <button data-page="leads">Leads</button>
        <button data-page="demos">Demos</button>
        <button data-page="outreach">Outreach</button>
      </div>
      <div class="navmeta" id="nav-meta">Runs 100% locally. Nothing auto-sends.</div>
      <button class="btn secondary" id="settings-btn" title="Set backend URL">&#9881;</button>
    </div>

    <div class="metrics">
      <div class="metric-card"><div class="label">Leads</div><div class="value" id="m-leads">-</div></div>
      <div class="metric-card"><div class="label">Hot leads</div><div class="value" id="m-hot">-</div></div>
      <div class="metric-card"><div class="label">Demos generated</div><div class="value" id="m-demos">-</div></div>
      <div class="metric-card"><div class="label">Outreach drafts</div><div class="value" id="m-outreach">-</div></div>
    </div>

    <div id="page-dashboard">
      <div class="section">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:0.5rem;">
          <button class="btn" id="run-pipeline-btn">Run Pipeline</button>
          <button class="btn secondary" id="approve-btn" disabled>Approve &amp; Send</button>
        </div>
        <p class="muted" id="run-status"></p>
      </div>
      <div class="two-col">
        <div class="section">
          <h2>Leads</h2>
          <table>
            <thead><tr><th>Business</th><th>Niche</th><th>Score</th><th>Status</th></tr></thead>
            <tbody id="leads-tbody"><tr><td colspan="4" class="muted">Loading...</td></tr></tbody>
          </table>
        </div>
        <div class="section">
          <h2>HTML Preview</h2>
          <div class="device-toggle">
            <button data-device="Desktop" class="active">Desktop</button>
            <button data-device="Tablet">Tablet</button>
            <button data-device="Mobile">Mobile</button>
          </div>
          <div class="preview-frame-wrap">
            <iframe id="demo-preview" srcdoc="<p style='font-family:sans-serif;color:#999;padding:2rem;'>Select a lead to preview its demo.</p>"></iframe>
          </div>
        </div>
      </div>
    </div>

    <div id="page-leads" style="display:none;">
      <div class="section">
        <h2>All Leads</h2>
        <table>
          <thead><tr><th>Business</th><th>Niche</th><th>Town</th><th>Score</th><th>Hot?</th></tr></thead>
          <tbody id="leads-full-tbody"><tr><td colspan="5" class="muted">Loading...</td></tr></tbody>
        </table>
      </div>
    </div>

    <div id="page-demos" style="display:none;">
      <div class="section">
        <h2>Demos</h2>
        <div id="demos-list" class="muted">Loading...</div>
      </div>
    </div>

    <div id="page-outreach" style="display:none;">
      <div class="section">
        <h2>Outreach Drafts</h2>
        <p class="muted">Drafts only - approving here just logs the approval. Sending is a separate, deliberate step outside this dashboard.</p>
        <div id="outreach-list" class="muted">Loading...</div>
      </div>
    </div>
  </div>

  <button id="chat-toggle" title="Ask the Obsidian Labs assistant">&#128172;</button>
  <div id="chat-panel">
    <div id="chat-header">Obsidian Labs Assistant</div>
    <div id="chat-messages"></div>
    <div id="chat-input-row">
      <input id="chat-input" type="text" placeholder="Ask about your pipeline..." />
      <button id="chat-send">Send</button>
    </div>
  </div>

  <script>
    function getApiBase() {
      return localStorage.getItem("obsidian_api_base") || "http://localhost:8502";
    }
    function setApiBase(url) {
      localStorage.setItem("obsidian_api_base", url.replace(/\/$/, ""));
    }

    let API_BASE = getApiBase();
    let currentDevice = "Desktop";
    let currentSlug = null;
    let leadsCache = [];

    function pillFor(status, perf) {
      perf = Number(perf) || 0;
      if (status === "no_website") return ["No Website", "pill-red"];
      if (status === "unreachable") return ["Unreachable", "pill-red"];
      if (status === "api_error") return ["Grade Error", "pill-gray"];
      if (perf <= 50) return ["Needs Improvement", "pill-amber"];
      return ["Healthy", "pill-green"];
    }

    function slugify(name) {
      return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "lead";
    }

    async function apiGet(path) {
      const res = await fetch(API_BASE + path);
      if (!res.ok) throw new Error(`${path} -> ${res.status}`);
      return res.json();
    }

    async function apiPost(path, body) {
      const res = await fetch(API_BASE + path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      if (!res.ok) throw new Error(`${path} -> ${res.status}`);
      return res.json();
    }

    async function loadStatus() {
      try {
        const s = await apiGet("/api/status");
        document.getElementById("m-leads").textContent = s.leads;
        document.getElementById("m-hot").textContent = s.hot_leads;
        document.getElementById("m-demos").textContent = s.demos;
        document.getElementById("m-outreach").textContent = s.outreach_drafts;
        document.getElementById("nav-meta").textContent =
          `${s.leads} leads - ${s.hot_leads} hot - ${s.demos} demos - ${s.outreach_drafts} drafts`;
      } catch (e) {
        document.getElementById("nav-meta").textContent =
          "Backend unreachable - is fastapi_backend running on :8502?";
      }
    }

    async function loadLeads() {
      try {
        leadsCache = await apiGet("/api/leads");
      } catch (e) {
        leadsCache = [];
      }
      renderLeadsTable();
      renderLeadsFullTable();
    }

    function renderLeadsTable() {
      const tbody = document.getElementById("leads-tbody");
      if (!leadsCache.length) {
        tbody.innerHTML = `<tr><td colspan="4" class="muted">No leads yet. Run the pipeline above.</td></tr>`;
        return;
      }
      tbody.innerHTML = leadsCache.map(l => {
        const [label, cls] = pillFor(l.status, l.perf_score);
        return `<tr class="lead-row" data-slug="${slugify(l.name)}">
          <td>${l.name || ""}</td><td>${l.type || ""}</td><td>${l.perf_score || 0}</td>
          <td><span class="pill ${cls}">${label}</span></td></tr>`;
      }).join("");
      document.querySelectorAll("#leads-tbody tr.lead-row").forEach(row => {
        row.addEventListener("click", () => selectLead(row.dataset.slug));
      });
    }

    function renderLeadsFullTable() {
      const tbody = document.getElementById("leads-full-tbody");
      if (!leadsCache.length) {
        tbody.innerHTML = `<tr><td colspan="5" class="muted">No leads yet.</td></tr>`;
        return;
      }
      tbody.innerHTML = leadsCache.map(l => `<tr>
        <td>${l.name || ""}</td><td>${l.type || ""}</td><td>${l.town || ""}</td>
        <td>${l.perf_score || 0}</td><td>${String(l.is_hot_lead).toLowerCase() === "true" ? "Yes" : "No"}</td></tr>`).join("");
    }

    async function selectLead(slug) {
      currentSlug = slug;
      document.getElementById("approve-btn").disabled = false;
      try {
        const demo = await apiGet(`/api/demos/${slug}`);
        renderPreview(demo.html);
      } catch (e) {
        document.getElementById("demo-preview").srcdoc =
          `<p style='font-family:sans-serif;color:#999;padding:2rem;'>No demo generated yet for '${slug}'.</p>`;
      }
    }

    function renderPreview(html) {
      const widths = { Desktop: "100%", Tablet: "768px", Mobile: "390px" };
      const iframe = document.getElementById("demo-preview");
      iframe.style.width = widths[currentDevice];
      iframe.style.margin = currentDevice === "Desktop" ? "0" : "0 auto";
      iframe.srcdoc = html;
    }

    document.querySelectorAll(".device-toggle button").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".device-toggle button").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        currentDevice = btn.dataset.device;
        if (currentSlug) selectLead(currentSlug);
      });
    });

    document.getElementById("approve-btn").addEventListener("click", async () => {
      if (!currentSlug) return;
      await apiPost("/api/approve", { kind: "dashboard_approve_and_send", identifier: currentSlug });
      document.getElementById("run-status").textContent =
        `Logged approval for '${currentSlug}'. This does NOT send anything.`;
    });

    document.getElementById("run-pipeline-btn").addEventListener("click", async () => {
      document.getElementById("run-status").textContent = "Starting pipeline in background...";
      try {
        await apiPost("/api/run-pipeline", {
          stage: "all", towns: ["Mahopac", "Carmel"], niches: ["dentist", "roofer"], limit: 5
        });
        document.getElementById("run-status").textContent =
          "Started. Check output/logs/pipeline_run.log, or refresh in a bit.";
      } catch (e) {
        document.getElementById("run-status").textContent = "Failed to start - is the backend running?";
      }
    });

    async function loadDemos() {
      try {
        const demos = await apiGet("/api/demos");
        const el = document.getElementById("demos-list");
        if (!demos.length) {
          el.innerHTML = `<p class="muted">No demos generated yet.</p>`;
          return;
        }
        el.innerHTML = demos.map(d => `<div class="draft-card"><strong>${d.slug}</strong></div>`).join("");
      } catch (e) {}
    }

    async function loadOutreach() {
      try {
        const drafts = await apiGet("/api/outreach");
        const el = document.getElementById("outreach-list");
        if (!drafts.length) {
          el.innerHTML = `<p class="muted">No outreach drafts yet.</p>`;
          return;
        }
        let html = "";
        for (const d of drafts) {
          const full = await apiGet(`/api/outreach/${d.slug}`);
          html += `<div class="draft-card"><strong>${d.slug}</strong>
            <pre>${full.content.replace(/</g, "&lt;")}</pre>
            <button class="btn secondary" data-approve-slug="${d.slug}">Approve</button></div>`;
        }
        el.innerHTML = html;
        el.querySelectorAll("[data-approve-slug]").forEach(btn => {
          btn.addEventListener("click", async () => {
            await apiPost("/api/approve", { kind: "outreach_approved", identifier: btn.dataset.approveSlug });
            btn.textContent = "Approved";
            btn.disabled = true;
          });
        });
      } catch (e) {}
    }

    document.querySelectorAll(".navtabs button").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".navtabs button").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        ["dashboard", "leads", "demos", "outreach"].forEach(p => {
          document.getElementById(`page-${p}`).style.display = p === btn.dataset.page ? "" : "none";
        });
        if (btn.dataset.page === "demos") loadDemos();
        if (btn.dataset.page === "outreach") loadOutreach();
      });
    });

    const chatToggle = document.getElementById("chat-toggle");
    const chatPanel = document.getElementById("chat-panel");
    const chatMessages = document.getElementById("chat-messages");
    const chatInput = document.getElementById("chat-input");

    chatToggle.addEventListener("click", () => chatPanel.classList.toggle("open"));

    function addChatMsg(text, who) {
      const div = document.createElement("div");
      div.className = `chat-msg ${who}`;
      div.textContent = text;
      chatMessages.appendChild(div);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    async function sendChat() {
      const msg = chatInput.value.trim();
      if (!msg) return;
      addChatMsg(msg, "user");
      chatInput.value = "";
      addChatMsg("Thinking...", "bot");
      try {
        const res = await apiPost("/api/chat", { message: msg });
        chatMessages.lastChild.textContent = res.reply || "(no response)";
      } catch (e) {
        chatMessages.lastChild.textContent =
          "Couldn't reach the assistant - is fastapi_backend + Ollama running?";
      }
    }

    document.getElementById("chat-send").addEventListener("click", sendChat);
    chatInput.addEventListener("keydown", e => { if (e.key === "Enter") sendChat(); });

    if ("serviceWorker" in navigator) {
      window.addEventListener("load", () => {
        navigator.serviceWorker.register("sw.js").catch(() => {});
      });
    }

    document.getElementById("settings-btn").addEventListener("click", () => {
      const current = getApiBase();
      const next = prompt(
        "Backend URL (your fastapi_backend.py address - e.g. https://xxxx.ngrok-free.app " +
        "or http://localhost:8502 if you're on the same laptop):",
        current
      );
      if (next && next.trim()) {
        setApiBase(next.trim());
        API_BASE = getApiBase();
        loadStatus();
        loadLeads();
      }
    });

    loadStatus();
    loadLeads();
    setInterval(loadStatus, 15000);
  </script>
</body>
</html>

```

## `manifest.json`  
_(14 lines)_

```json
{
  "name": "Obsidian Labs Pipeline Dashboard",
  "short_name": "Obsidian Labs",
  "description": "Local AI lead-gen pipeline dashboard - review leads, demos, and outreach drafts.",
  "start_url": "tesla_style_dashboard_with_chat.html",
  "display": "standalone",
  "background_color": "#f8f9fa",
  "theme_color": "#f8f9fa",
  "icons": [
    { "src": "icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}

```

## `sw.js`  
_(41 lines)_

```javascript
// Obsidian Labs Dashboard - minimal offline app-shell cache.
// Caches the static shell (HTML/CSS/JS/icons) so the dashboard opens instantly and
// works if briefly offline. Does NOT cache API responses from fastapi_backend - live
// data always comes from the network.
const CACHE_NAME = "obsidian-labs-shell-v1";
const SHELL_FILES = [
  "tesla_style_dashboard_with_chat.html",
  "manifest.json",
  "icon-192.png",
  "icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // Never cache backend/API calls - always go straight to the network. The backend
  // can be localhost:8502, an ngrok URL, or anything else set in Settings, so the
  // safest check is "not the same origin this dashboard was served from."
  if (url.origin !== self.location.origin || url.pathname.startsWith("/api/")) {
    return;
  }
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request))
  );
});

```

## `requirements-new-files.txt`  
_(24 lines)_

```text
# Dependencies required by the NEW files reconstructed here (Appendices A-H).
# The base pipeline (pipeline.py, scraper.py, grader.py, rag_setup.py,
# demo_gen_local.py, dashboard.py) lives in the original obsidian-local-pipeline
# repo and has its own requirements.txt - install that too when you have it.

# FastAPI backend (fastapi_backend.py) + Tesla dashboard PWA
fastapi>=0.110,<1.0
uvicorn>=0.29,<1.0
pydantic>=2.0,<3.0

# Media enhancer (media_enhancer.py) + Telegram/Unsplash/Ollama HTTP calls
requests>=2.31,<3.0
pillow>=10.0,<11.0
python-dotenv>=1.0,<2.0

# Nightly orchestrator (autonomous_orchestrator.py)
schedule>=1.2,<2.0

# Outreach generator (outreach_generator.py) RAG retrieval via local Ollama.
# Optional - only needed if you want RAG-grounded drafts; the script degrades
# gracefully to a baked-in fallback prompt if these are missing.
langchain-ollama>=0.1,<1.0
langchain-chroma>=0.1,<1.0

```

## `NEW_REQUIREMENTS_ADD_2026-07-10.txt`  
_(9 lines)_

```text
# Add these lines to your existing requirements.txt (don't replace the whole file -
# just append anything from this list you don't already have), then:
#   pip install -r requirements.txt
fastapi>=0.110,<1.0
uvicorn>=0.29,<1.0
pydantic>=2.0,<3.0
requests>=2.31,<3.0
pillow>=10.0,<11.0

```

## `.env.example`  
_(23 lines)_

```ini
# Obsidian Labs pipeline - environment variables (copy to .env at the repo root).
# Save as plain UTF-8. A stray BOM is handled by the code (load_dotenv uses utf-8-sig).

# --- Required: RAG source document locations ---
GDRIVE_PATH=C:\Users\Laptop\My Drive
OBSIDIAN_VAULT_PATH=C:\Users\Laptop\My Drive\Shipper Vault

# --- Optional: stock-photo fallback in media_enhancer.py ---
# Free key from https://unsplash.com/developers
UNSPLASH_ACCESS_KEY=

# --- Optional: Telegram ping when the nightly orchestrator starts/finishes/fails ---
OL_TELEGRAM_TOKEN=
OL_TELEGRAM_CHAT_ID=

# --- Optional: orchestrator tuning ---
# Seconds before a stuck pipeline stage is aborted (default 1800)
OL_STAGE_TIMEOUT=1800
# Businesses processed per nightly run (default 5)
OL_NIGHTLY_LIMIT=5
# Nightly run time, 24h format (default 02:00)
OL_RUN_AT=02:00

```

## `setup.ps1`  
_(103 lines)_

```powershell
<#
  Obsidian Labs - one-shot setup & launch (Windows PowerShell)
  --------------------------------------------------------------
  Paste this whole file into a PowerShell window (or run:  .\setup.ps1 )
  It will:
    1. check Git / Python / Ollama are installed
    2. make sure the two Ollama models are pulled
    3. copy the new dashboard files into your project folder
    4. install the Python packages
    5. launch Ollama + the backend in their own windows
    6. open the dashboard in your browser

  Nothing here ever sends an email. Safe to re-run - it skips steps already done.
  Edit the paths in the CONFIG block below only if your folders differ.
#>

# ============================ CONFIG ============================
$RepoPath     = "C:\Users\Laptop\obsidian-local-pipeline"
$NewFilesSrc  = "C:\Users\Laptop\My Drive\Shipper Vault\autonomous_system_2026-07-10"
$GitEmail     = "themortgagemaster01@gmail.com"
$GitName      = "Robert"
$BackendPort  = 8502
$Models       = @("qwen2.5:14b-instruct-q4_K_M", "nomic-embed-text")
# ===============================================================

$ErrorActionPreference = "Stop"
function Say($m,$c="White"){ Write-Host $m -ForegroundColor $c }
function Have($cmd){ [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

Say "`n=== Obsidian Labs setup ===`n" "Cyan"

# --- 1. prerequisites ---
Say "[1/6] Checking Git, Python, Ollama..." "Yellow"
$missing = @()
foreach ($c in "git","python","ollama") { if (-not (Have $c)) { $missing += $c } }
if ($missing.Count) {
    Say "  Missing: $($missing -join ', ')" "Red"
    Say "  Install them first:" "Red"
    Say "    Git:    https://git-scm.com/download/win"
    Say "    Python: https://www.python.org/downloads/  (tick 'Add to PATH')"
    Say "    Ollama: https://ollama.com/download"
    return
}
Say "  OK - all three found." "Green"

# make sure git knows who you are (fixes 'unable to auto-detect email address')
if (-not (git config --global user.email)) { git config --global user.email $GitEmail }
if (-not (git config --global user.name))  { git config --global user.name  $GitName }

# --- 2. project folder ---
Say "[2/6] Locating project folder..." "Yellow"
if (-not (Test-Path $RepoPath)) {
    Say "  Not found at $RepoPath" "Red"
    Say "  Clone it first, then re-run this script:" "Red"
    Say "    git clone https://github.com/themortgagemaster01-eng/obsidian-local-pipeline.git `"$RepoPath`""
    return
}
Set-Location $RepoPath
try { git pull --ff-only 2>$null } catch { Say "  (skipped git pull - not a problem)" "DarkGray" }
Say "  Using $RepoPath" "Green"

# --- 3. copy in the new dashboard files ---
Say "[3/6] Copying new dashboard files..." "Yellow"
if (Test-Path $NewFilesSrc) {
    Copy-Item "$NewFilesSrc\*" -Destination $RepoPath -Recurse -Force
    Say "  Copied from Shipper Vault." "Green"
} else {
    Say "  Source folder not found: $NewFilesSrc" "DarkYellow"
    Say "  Skipping copy - assuming the files are already in the project folder." "DarkYellow"
}

# --- 4. python packages ---
Say "[4/6] Installing Python packages..." "Yellow"
$venv = Join-Path $RepoPath "venv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv; Say "  venv activated." "DarkGray" }
python -m pip install --quiet --upgrade pip
python -m pip install --quiet fastapi uvicorn pydantic requests pillow python-dotenv schedule
Say "  Packages installed." "Green"

# --- 5. ollama models ---
Say "[5/6] Checking Ollama models (first run may download several GB)..." "Yellow"
$installed = (ollama list) 2>$null
foreach ($m in $Models) {
    if ($installed -match [regex]::Escape($m)) { Say "  Already have $m" "DarkGray" }
    else { Say "  Pulling $m ..." "DarkGray"; ollama pull $m }
}
Say "  Models ready." "Green"

# --- 6. launch everything ---
Say "[6/6] Launching Ollama + backend in their own windows..." "Yellow"
Start-Process powershell -ArgumentList '-NoExit','-Command','Write-Host "Ollama - keep me open"; ollama serve'
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList '-NoExit','-Command',"Set-Location '$RepoPath'; Write-Host 'Backend - keep me open'; uvicorn fastapi_backend:app --port $BackendPort"
Start-Sleep -Seconds 3

$dashboard = Join-Path $RepoPath "tesla_style_dashboard_with_chat.html"
if (Test-Path $dashboard) { Start-Process $dashboard }

Say "`n=== Done! ===" "Cyan"
Say "Two new windows opened (Ollama + Backend) - leave them running." "White"
Say "Dashboard opened in your browser. Click 'Run Pipeline' to gather leads." "White"
Say "To use it on your phone: run 'ngrok http $BackendPort', then paste that URL into the dashboard's gear icon.`n" "White"

```

## `README.md`  
_(86 lines)_

```markdown
# Obsidian Labs — Local Pipeline (new files, reconstructed)

A $0-cost, fully local AI pipeline for local-business lead generation, demo-site
generation, and outreach drafting. Nothing here calls a paid AI API — it runs on
[Ollama](https://ollama.com) (local LLM) plus a local RAG index. **Nothing in this
system auto-sends anything** — a human reviews and approves drafts in a dashboard,
then sends manually.

This folder contains the **new files** from the July 10, 2026 handoff guide — the
"Tesla-style" phone-friendly PWA dashboard, its FastAPI backend, the v2 nightly
orchestrator, the media enhancer, and the outreach generator — reconstructed from
the handoff PDF.

## What's here (from the handoff appendices)

| File | Purpose |
| --- | --- |
| `autonomous_orchestrator.py` | Nightly scheduler v2 — fail-fast, dedup, Telegram notify, rotating logs, `--now` flag |
| `media_enhancer.py` | Sharpens/enhances real scraped photos (Pillow); optional Unsplash stock-photo fallback |
| `outreach_generator.py` | Drafts the $1,495 pitch email via local Ollama, grounded in RAG |
| `fastapi_backend.py` | API server (port 8502) powering the Tesla-style dashboard |
| `tesla_style_dashboard_with_chat.html` | Standalone dashboard with AI chat widget + PWA support |
| `manifest.json` / `sw.js` | PWA manifest + service worker (installable app, offline shell) |
| `icon-192.png` / `icon-512.png` | App icons (placeholder brand mark — swap for the real assets) |
| `NEW_REQUIREMENTS_ADD_2026-07-10.txt` | New pip packages to append to the base `requirements.txt` |
| `requirements-new-files.txt` | Full dependency list for just the files in this folder |
| `.env.example` | Template for the `.env` file (copy to `.env` and fill in) |

## What's NOT here (needs the original repo)

The base pipeline is described in the handoff as *"already in the GitHub repo"*
(`obsidian-local-pipeline`) and its source is **not** in the PDF, so it could not be
reconstructed. The new files above call these — copy them in from the original repo:

- `pipeline.py` — orchestrator (scrape → grade stages)
- `scraper.py` — finds local businesses (Google Places)
- `grader.py` — scores each business's current website (PageSpeed)
- `rag_setup.py` — builds the local `chroma_db` index from Drive/Obsidian docs
- `demo_gen_local.py` — generates a personalized demo site via local LLM + RAG
- `dashboard.py` — the original Streamlit dashboard
- `templates/` — design-standards and outreach-voice prompts

The reconstructed files degrade gracefully when these are absent (the orchestrator
logs and skips missing stages; the backend serves empty lists until the pipeline runs).

## Quick start

```bash
# 1. install deps for the new files
pip install -r requirements-new-files.txt

# 2. configure environment
cp .env.example .env      # then edit paths/keys

# 3. run the backend (leave running)
uvicorn fastapi_backend:app --port 8502 --reload

# 4. open the dashboard
#    - locally: open tesla_style_dashboard_with_chat.html
#    - on a phone: serve via GitHub Pages + point the gear-icon URL at an ngrok tunnel
```

### Nightly automation (optional)

```bash
python autonomous_orchestrator.py        # schedules a nightly run at OL_RUN_AT (default 02:00)
python autonomous_orchestrator.py --now  # one-off run right now
```

## Phone / PWA deployment

1. Enable GitHub Pages (deploy from `main`, folder `/`) so the HTML gets an `https` URL.
2. Run `uvicorn fastapi_backend:app --port 8502` on the laptop.
3. Expose it: `ngrok http 8502`, copy the `https://xxxx.ngrok-free.app` URL.
4. On the phone, open the Pages URL, tap the ⚙ gear, paste the ngrok URL (saved per-device).
5. Add to Home Screen to install it as an app.

> Free ngrok URLs change on every restart — re-paste the new URL in the gear dialog
> after restarting ngrok, or use a static domain on ngrok's paid tier.

## Guardrails

Runs 100% locally. The chat widget talks to local Ollama
(`qwen2.5:14b-instruct-q4_K_M`) via the backend. Approving in the dashboard only
**logs** an approval to `output/logs/approvals.csv` — it never sends email.

```

---

## Suggested review questions
1. Any bug that only shows up once the engine writes real data to `output/`?
2. `fastapi_backend.py` allows CORS `*` — acceptable given it's meant to be
   exposed via ngrok? What would you tighten?
3. `/api/run-pipeline` shells out with `subprocess.Popen` using values from a
   POST body (towns/niches). Is the argument handling safe?
4. The dashboard reads the backend URL from `localStorage` and calls it directly.
   Any XSS / injection concerns in how demo HTML and drafts are rendered?
5. Dedup logic in `autonomous_orchestrator.py` (`lead_key`, `seen_leads.json`) —
   correct and race-free for a nightly single-process run?
6. Error handling / graceful degradation when Ollama or the engine files are absent.
