# Obsidian Labs — Complete Project Bundle

_Every source file in the pipeline, in one markdown document, for review.
Local lead-gen: scrape businesses → grade their sites → build a local-LLM demo →
draft outreach → human approves in a dashboard → human sends. $0 API cost, nothing auto-sends._

**Omitted:** binary assets (app icons), the local RAG index, and generated `output/`.
Everything else in the project is below.

---

## Contents

- **Engine**
  - `pipeline.py`
  - `scraper.py`
  - `grader.py`
  - `rag_setup.py`
  - `demo_gen_local.py`
  - `outreach_local.py`
  - `dashboard.py`
- **Backend (API)**
  - `fastapi_backend.py`
- **Dashboards (live, browser/PWA)**
  - `dashboard_leadflow.html`
  - `tesla_style_dashboard_v2.html`
  - `tesla_style_dashboard_with_chat.html`
- **Automation & media**
  - `autonomous_orchestrator.py`
  - `media_enhancer.py`
  - `outreach_generator.py`
- **PWA shell**
  - `manifest.json`
  - `sw.js`
- **Prompt templates**
  - `templates/demo_system_prompt.md`
  - `templates/email_system_prompt.md`
  - `templates/reference_demos/wallys-super-service.html`
  - `templates/reference_demos/README.md`
- **Config & deps**
  - `requirements.txt`
  - `.env.example`
  - `.streamlit/config.toml`
  - `.gitignore`
  - `setup.ps1`
- **Docs**
  - `README.md`
  - `docs/README.md`
  - `docs/business-playbook.md`
  - `docs/dashboard-v2-prompt.md`
  - `docs/tesla-dashboard-blueprint.md`
- **Self-contained previews (sample-data copies of the dashboards)**
  - `dashboard_leadflow_preview.html`
  - `dashboard_v2_preview.html`
  - `dashboard_preview.html`
- **Other files**
  - `NEW_REQUIREMENTS_ADD_2026-07-10.txt`
  - `requirements-new-files.txt`

---

# Engine

## `pipeline.py`  
_(135 lines)_

```python
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

```

## `scraper.py`  
_(182 lines)_

```python
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

```

## `grader.py`  
_(158 lines)_

```python
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

```

## `rag_setup.py`  
_(216 lines)_

```python
#!/usr/bin/env python3
"""
rag_setup.py - Local RAG index builder

Loads documents recursively from:
  1. Google Drive (mounted/synced locally - e.g. rclone on Mac/Linux at
     ~/GoogleDrive, or Google Drive for Desktop on Windows at a drive letter
     like G:\\My Drive) - expects your design standards doc, pricing docs,
     past demo examples, etc.
  2. Your local Obsidian vault (.md/.html/.txt notes) - client notes, voice/
     tone notes, past outreach that worked, etc.

Chunks everything, embeds with a local Ollama embedding model
(nomic-embed-text by default), and persists to a local Chroma DB.

This script is safe to re-run: it wipes and rebuilds the collection each
time, so editing/adding docs in Drive or Obsidian and re-running always
gives you an up-to-date index. (For very large corpora you may want to
switch this to incremental upserts - see the note near build_index().)

Requires a running local Ollama server with the embedding model pulled:
    ollama pull nomic-embed-text

Usage
-----
    python rag_setup.py
    python rag_setup.py --gdrive-path "G:\\My Drive" --vault-path "G:\\My Drive\\Shipper Vault"

Troubleshooting
----------------
If you see "WARNING: path does not exist, skipping: ..." for a path that
DOES exist on disk, the most likely cause is a corrupted .env file - see
the "GDRIVE_PATH / OBSIDIAN_VAULT_PATH not found in .env" warning that
prints right before it. The #1 real-world cause: saving .env from Windows
Notepad ("Save As" > Encoding: UTF-8) silently prepends a BOM (byte-order
mark) to the file, which corrupts the *first* KEY=VALUE line's key name so
python-dotenv can't find it and this script silently falls back to a
default path instead of your real one. This script loads .env with
encoding="utf-8-sig" specifically to tolerate that BOM, but if you edit
.env with a different tool that does something similar, re-check with:
    python -c "print(open('.env', 'rb').read()[:8])"
A leading b'\\xef\\xbb\\xbf' means there's a BOM present (harmless with this
script's fix, but worth knowing about for other tools).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
ENV_PATH = ROOT / ".env"

SUPPORTED_EXTENSIONS = {".md", ".html", ".htm", ".txt"}
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def expand(path_str: str) -> Path:
    """Turn a possibly-relative, possibly-~-prefixed, possibly-quoted path
    string (e.g. from a CLI arg or .env value) into a clean absolute Path.

    Defensive against stray leading/trailing whitespace and matching
    leading/trailing quote characters, both of which are easy to
    accidentally introduce when hand-editing a .env file on Windows.
    """
    cleaned = path_str.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
        cleaned = cleaned[1:-1].strip()
    return Path(cleaned).expanduser().resolve()


def env_or_default(key: str, default: str) -> tuple[str, bool]:
    """Return (value, was_set_in_env). Lets callers warn when falling back
    to a default instead of silently using it, which is exactly the kind of
    silent failure that made the GDRIVE_PATH bug hard to spot."""
    value = os.getenv(key)
    if value is None or value.strip() == "":
        return default, False
    return value, True


def collect_documents(root_dirs: list[Path]):
    """Walk each root dir, load supported text-like files as LangChain Documents."""
    from langchain_community.document_loaders import TextLoader

    docs = []
    for root_dir in root_dirs:
        if not root_dir.exists():
            print(f"[rag_setup.py] WARNING: path does not exist, skipping: {root_dir}", file=sys.stderr)
            continue

        print(f"[rag_setup.py] Scanning {root_dir} ...")
        count = 0
        for path in root_dir.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            # Skip obvious junk / system files.
            if path.name.startswith(".") or "node_modules" in path.parts:
                continue
            try:
                loader = TextLoader(str(path), encoding="utf-8", autodetect_encoding=True)
                loaded = loader.load()
                for d in loaded:
                    d.metadata["source"] = str(path)
                docs.extend(loaded)
                count += 1
            except Exception as e:
                print(f"[rag_setup.py]   ! skipped {path} ({e})", file=sys.stderr)
        print(f"[rag_setup.py]   loaded {count} files from {root_dir}")
    return docs


def build_index(docs, chroma_path: Path, embed_model: str, ollama_base_url: str) -> None:
    # NOTE: RecursiveCharacterTextSplitter lives in the standalone
    # langchain-text-splitters package (imported as langchain_text_splitters),
    # not in langchain.text_splitter - that import path was removed in
    # LangChain 1.x. requirements.txt pins langchain-text-splitters directly
    # so this always resolves regardless of which langchain version pip picks.
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_ollama import OllamaEmbeddings
    from langchain_community.vectorstores import Chroma

    if not docs:
        print("[rag_setup.py] No documents found to index. Nothing to do.")
        return

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = splitter.split_documents(docs)
    print(f"[rag_setup.py] Split {len(docs)} documents into {len(chunks)} chunks.")

    embeddings = OllamaEmbeddings(model=embed_model, base_url=ollama_base_url)

    # NOTE on re-runnability: this rebuilds the collection from scratch each
    # time, which is simple and correct but re-embeds everything (fine for a
    # personal-scale corpus on a 4090 laptop GPU). If your Drive/vault grows
    # large enough that re-embedding gets slow, switch this to Chroma's
    # upsert-by-id pattern keyed on file path + mtime instead of delete+rebuild.
    print(f"[rag_setup.py] Rebuilding Chroma collection at {chroma_path} ...")
    if chroma_path.exists():
        import shutil
        shutil.rmtree(chroma_path)

    vectordb = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(chroma_path),
    )
    vectordb.persist()
    print(f"[rag_setup.py] Done. Indexed {len(chunks)} chunks into {chroma_path}")


def main() -> None:
    # encoding="utf-8-sig" tolerates a leading UTF-8 BOM, which Windows
    # Notepad silently adds when you "Save As" with encoding set to UTF-8.
    # A BOM on the first line corrupts that line's key name for plain utf-8
    # parsing, which is exactly what caused GDRIVE_PATH to silently fall
    # back to its default instead of being read from .env. See the module
    # docstring's Troubleshooting section for how to check for this.
    load_dotenv(ENV_PATH, encoding="utf-8-sig")

    parser = argparse.ArgumentParser(description="Build/refresh the local Chroma RAG index")
    parser.add_argument("--gdrive-path", default=None, help="Path to your Google Drive (overrides GDRIVE_PATH in .env)")
    parser.add_argument("--vault-path", default=None, help="Path to your local Obsidian vault (overrides OBSIDIAN_VAULT_PATH in .env)")
    parser.add_argument("--chroma-path", default=None, help="Where to persist the Chroma DB (overrides CHROMA_DB_PATH in .env)")
    parser.add_argument("--embed-model", default=None, help="Ollama embedding model name (overrides OLLAMA_EMBED_MODEL in .env)")
    parser.add_argument("--ollama-base-url", default=None, help="Base URL of the local Ollama server (overrides OLLAMA_BASE_URL in .env)")
    args = parser.parse_args()

    gdrive_default, gdrive_from_env = env_or_default("GDRIVE_PATH", "~/GoogleDrive")
    vault_default, vault_from_env = env_or_default("OBSIDIAN_VAULT_PATH", "~/ObsidianVault")
    chroma_default, _ = env_or_default("CHROMA_DB_PATH", "./chroma_db")
    embed_default, _ = env_or_default("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    url_default, _ = env_or_default("OLLAMA_BASE_URL", "http://localhost:11434")

    gdrive_raw = args.gdrive_path or gdrive_default
    vault_raw = args.vault_path or vault_default
    chroma_raw = args.chroma_path or chroma_default
    embed_model = args.embed_model or embed_default
    ollama_base_url = args.ollama_base_url or url_default

    if not args.gdrive_path and not gdrive_from_env:
        print(
            f"[rag_setup.py] WARNING: GDRIVE_PATH not found in {ENV_PATH} (or .env is missing/empty) - "
            f"falling back to default: {gdrive_raw!r}. If that's not your real Drive path, check .env "
            f"for typos or a stray BOM (see this script's Troubleshooting docstring).",
            file=sys.stderr,
        )
    if not args.vault_path and not vault_from_env:
        print(
            f"[rag_setup.py] WARNING: OBSIDIAN_VAULT_PATH not found in {ENV_PATH} (or .env is missing/empty) - "
            f"falling back to default: {vault_raw!r}.",
            file=sys.stderr,
        )

    gdrive_path = expand(gdrive_raw)
    vault_path = expand(vault_raw)
    chroma_path = (ROOT / chroma_raw).resolve() if not Path(chroma_raw).is_absolute() else Path(chroma_raw)

    print(f"[rag_setup.py] GDRIVE_PATH raw={gdrive_raw!r} resolved={gdrive_path}")
    print(f"[rag_setup.py] OBSIDIAN_VAULT_PATH raw={vault_raw!r} resolved={vault_path}")
    print(f"[rag_setup.py] CHROMA_DB_PATH resolved={chroma_path}")

    docs = collect_documents([gdrive_path, vault_path])
    build_index(docs, chroma_path, embed_model, ollama_base_url)


if __name__ == "__main__":
    main()

```

## `demo_gen_local.py`  
_(288 lines)_

````python
#!/usr/bin/env python3
"""
demo_gen_local.py - RAG + local Ollama demo site generator

For each "hot lead" in output/leads_graded.csv (no website, or perf_score at
or below the hot-lead threshold), this script:

  1. Runs a similarity search against the local Chroma vectorstore (built by
     rag_setup.py) for relevant design-standards / pricing / past-demo-example
     context from your Drive + Obsidian vault.
  2. Builds a prompt from templates/demo_system_prompt.md + a real reference
     demo (templates/reference_demos/) as a few-shot quality bar + the lead's
     real business data + the retrieved context.
  3. Sends it to a local Ollama model (OLLAMA_MODEL env var, default
     qwen2.5:14b-instruct-q4_K_M) to generate a single-file HTML demo.
  4. Saves the result to output/demos/{slug}/index.html.

Zero Claude/OpenAI API calls, zero token cost - everything runs on your own
GPU via Ollama.

Requires:
  - A running local Ollama server with OLLAMA_MODEL pulled.
  - A Chroma index already built by rag_setup.py (./chroma_db). If it's
    missing, this script still runs but skips retrieval (empty context) and
    prints a warning - you'll get lower-quality, less-grounded demos.

Usage
-----
    python demo_gen_local.py
    python demo_gen_local.py --input output/leads_graded.csv --limit 3
    python demo_gen_local.py --no-reference-demo   # omit the few-shot example
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
DEMOS_DIR = OUTPUT_DIR / "demos"
LEADS_GRADED_CSV = OUTPUT_DIR / "leads_graded.csv"
PROMPT_TEMPLATE_PATH = ROOT / "templates" / "demo_system_prompt.md"
CHROMA_DB_PATH = ROOT / "chroma_db"

# Real, previously-shipped demo used as a concrete few-shot "here is our
# actual quality bar and code style" example. This is real client-facing
# work product (see templates/reference_demos/README.md for provenance and
# caveats) - it is a STYLE/CODE-QUALITY reference only. build_prompt() below
# wraps it with an explicit instruction not to reuse this specific business's
# name/address/phone/reviews for a different business, so it can't leak
# cross-lead.
REFERENCE_DEMO_PATH = ROOT / "templates" / "reference_demos" / "wallys-super-service.html"

DEMO_EXPIRY_DAYS = 7
RETRIEVAL_QUERY = (
    "web design standards, pricing tiers, layout guardrails, "
    "and example past demo sites for a local business"
)
RETRIEVAL_K = 5


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "lead"


def load_hot_leads(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        print(f"[demo_gen_local.py] ERROR: {csv_path} not found. Run grader.py first.", file=sys.stderr)
        sys.exit(1)
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    hot = [r for r in rows if str(r.get("is_hot_lead", "")).strip().lower() in ("true", "1", "yes")]
    return hot


def load_reference_demo(path: Path) -> str:
    """Load a real past demo as a few-shot code-quality example. Returns ''
    (not fatal) if the file is missing, so this stays optional."""
    if not path.exists():
        print(
            f"[demo_gen_local.py] NOTE: no reference demo found at {path} - "
            "generating without a few-shot code example. This still works, "
            "just less grounded in your actual shipped quality bar.",
            file=sys.stderr,
        )
        return ""
    return path.read_text(encoding="utf-8")


def get_retrieved_context(embed_model: str, ollama_base_url: str) -> str:
    """Pull relevant chunks from the Chroma RAG index. Returns '' if the index is missing."""
    if not CHROMA_DB_PATH.exists():
        print(
            f"[demo_gen_local.py] WARNING: no Chroma index found at {CHROMA_DB_PATH}. "
            "Run `python rag_setup.py` first for grounded, on-brand demos. "
            "Continuing with empty retrieval context.",
            file=sys.stderr,
        )
        return ""
    try:
        from langchain_ollama import OllamaEmbeddings
        from langchain_community.vectorstores import Chroma

        embeddings = OllamaEmbeddings(model=embed_model, base_url=ollama_base_url)
        vectordb = Chroma(persist_directory=str(CHROMA_DB_PATH), embedding_function=embeddings)
        results = vectordb.similarity_search(RETRIEVAL_QUERY, k=RETRIEVAL_K)
        return "\n\n---\n\n".join(d.page_content for d in results)
    except Exception as e:
        print(f"[demo_gen_local.py] WARNING: retrieval failed ({e}). Continuing with empty context.",
              file=sys.stderr)
        return ""


def build_prompt(
    lead: dict,
    system_prompt: str,
    retrieved_context: str,
    expiry_date: str,
    reference_demo: str = "",
) -> str:
    business_context = "\n".join(
        f"- {k}: {v}" for k, v in lead.items() if v not in (None, "", "None")
    )

    reference_block = ""
    if reference_demo:
        reference_block = f"""
## Reference example - real, previously-shipped demo (STYLE/CODE-QUALITY REFERENCE ONLY)

The HTML below is a real demo Obsidian Labs already built and shipped for a
different business. It shows the actual code quality bar, layout patterns,
and visual polish to match - copy structure/technique, not content.

IMPORTANT: this reference belongs to a completely different business than
the one you are generating a demo for right now. Do NOT reuse its business
name, address, phone number, reviews, or any other identifying detail in
your output - those belong to the reference business only, and must never
appear in a demo generated for a different lead.

```html
{reference_demo}
```
"""

    prompt = f"""{system_prompt}
{reference_block}
---

## Business data (real - use only this, do not invent additional facts)

{business_context}

## Retrieved context from Obsidian Labs' design standards / pricing / past examples

{retrieved_context if retrieved_context else '(no retrieved context available - rely on the guardrails above)'}

## Task-specific values to embed exactly as given

- expiry_date for the banner: {expiry_date}

Now generate the single-file HTML demo for this business. Output ONLY the
HTML document, starting with <!DOCTYPE html>, no explanation, no markdown
code fences.
"""
    return prompt


def generate_html(prompt: str, model: str, ollama_base_url: str) -> str:
    from langchain_ollama import OllamaLLM

    llm = OllamaLLM(model=model, base_url=ollama_base_url, temperature=0.4)
    raw = llm.invoke(prompt)
    return clean_html_response(raw)


def clean_html_response(raw: str) -> str:
    """Strip markdown code fences if the model wraps its output in them anyway."""
    text = raw.strip()
    text = re.sub(r"^```(?:html)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def ensure_guardrails(html: str, business_name: str, expiry_date: str) -> str:
    """
    Belt-and-suspenders check: if the model forgot noindex/expiry/watermark,
    inject them rather than shipping a demo that violates the hard guardrails.
    """
    if "noindex" not in html.lower():
        html = html.replace(
            "<head>",
            '<head>\n    <meta name="robots" content="noindex, nofollow">',
            1,
        )
    if "obsidianlabshq.io" not in html.lower():
        watermark = (
            '\n<footer style="text-align:center;padding:1rem;font-size:0.8rem;'
            'color:#888;">Built at obsidianlabshq.io</footer>\n'
        )
        if "</body>" in html:
            html = html.replace("</body>", f"{watermark}</body>", 1)
        else:
            html += watermark
    if "expires" not in html.lower():
        banner = (
            f'\n<div style="background:#111;color:#fff;text-align:center;'
            f'padding:0.5rem;font-size:0.85rem;">Preview built by Obsidian Labs '
            f'- expires {expiry_date}</div>\n'
        )
        if "<body" in html:
            html = re.sub(r"(<body[^>]*>)", r"\1" + banner, html, count=1)
        else:
            html = banner + html
    return html


def main() -> None:
    # encoding="utf-8-sig" tolerates a leading UTF-8 BOM, which Windows
    # Notepad silently adds when saving with "UTF-8" encoding - a BOM
    # corrupts the first KEY=VALUE line for plain utf-8 parsing.
    load_dotenv(ROOT / ".env", encoding="utf-8-sig")

    parser = argparse.ArgumentParser(description="Generate demo HTML sites for hot leads via local RAG + Ollama")
    parser.add_argument("--input", default=str(LEADS_GRADED_CSV), help="Path to leads_graded.csv")
    parser.add_argument("--limit", type=int, default=None, help="Max number of demos to generate this run")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct-q4_K_M"))
    parser.add_argument("--embed-model", default=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"))
    parser.add_argument("--ollama-base-url", default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    parser.add_argument(
        "--no-reference-demo",
        action="store_true",
        help="Skip including the real past-demo few-shot example (leaner prompt, less grounded output).",
    )
    args = parser.parse_args()

    if not PROMPT_TEMPLATE_PATH.exists():
        print(f"[demo_gen_local.py] ERROR: missing {PROMPT_TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)
    system_prompt = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    reference_demo = "" if args.no_reference_demo else load_reference_demo(REFERENCE_DEMO_PATH)

    hot_leads = load_hot_leads(Path(args.input))
    if args.limit:
        hot_leads = hot_leads[: args.limit]

    if not hot_leads:
        print("[demo_gen_local.py] No hot leads found (no-website or low perf_score). Nothing to generate.")
        return

    retrieved_context = get_retrieved_context(args.embed_model, args.ollama_base_url)
    expiry_date = (dt.date.today() + dt.timedelta(days=DEMO_EXPIRY_DAYS)).strftime("%B %d, %Y")

    DEMOS_DIR.mkdir(parents=True, exist_ok=True)

    for i, lead in enumerate(hot_leads, start=1):
        name = lead.get("name", f"lead-{i}")
        slug = slugify(name)
        print(f"[demo_gen_local.py] ({i}/{len(hot_leads)}) Generating demo for {name} -> demos/{slug}/index.html")

        prompt = build_prompt(lead, system_prompt, retrieved_context, expiry_date, reference_demo)
        try:
            html = generate_html(prompt, args.model, args.ollama_base_url)
        except Exception as e:
            print(f"[demo_gen_local.py]   ! generation failed for {name}: {e}", file=sys.stderr)
            continue

        html = ensure_guardrails(html, name, expiry_date)

        demo_dir = DEMOS_DIR / slug
        demo_dir.mkdir(parents=True, exist_ok=True)
        (demo_dir / "index.html").write_text(html, encoding="utf-8")

    print(f"[demo_gen_local.py] Done. Demos written to {DEMOS_DIR}")


if __name__ == "__main__":
    main()

````

## `outreach_local.py`  
_(235 lines)_

```python
#!/usr/bin/env python3
"""
outreach_local.py — RAG + local Ollama outreach email drafter

For each hot lead in output/leads_graded.csv, generates a 3-touch outreach
email sequence (drafts only — nothing is ever auto-sent) grounded in:

  - templates/email_system_prompt.md (voice + CAN-SPAM guardrails)
  - the lead's real business data
  - relevant context retrieved from the local Chroma RAG index (voice notes,
    past outreach that worked, pricing, etc.)

Every draft always includes a physical mailing address and an unsubscribe
line, and is instructed to avoid exaggerated/fabricated claims — CAN-SPAM
compliant by construction. Drafts are saved to output/outreach/{slug}.md for
human review in the dashboard; sending requires a separate, explicit human
action (this script never touches SMTP/Brevo/etc.).

Usage
-----
    python outreach_local.py
    python outreach_local.py --input output/leads_graded.csv --limit 3
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
OUTREACH_DIR = OUTPUT_DIR / "outreach"
DEMOS_DIR = OUTPUT_DIR / "demos"
LEADS_GRADED_CSV = OUTPUT_DIR / "leads_graded.csv"
PROMPT_TEMPLATE_PATH = ROOT / "templates" / "email_system_prompt.md"
CHROMA_DB_PATH = ROOT / "chroma_db"

RETRIEVAL_QUERY = (
    "outreach voice, tone, past successful cold emails, and pricing "
    "for local business web design outreach"
)
RETRIEVAL_K = 5


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "lead"


def load_hot_leads(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        print(f"[outreach_local.py] ERROR: {csv_path} not found. Run grader.py first.", file=sys.stderr)
        sys.exit(1)
    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    hot = [r for r in rows if str(r.get("is_hot_lead", "")).strip().lower() in ("true", "1", "yes")]
    return hot


def get_retrieved_context(embed_model: str, ollama_base_url: str) -> str:
    if not CHROMA_DB_PATH.exists():
        print(
            f"[outreach_local.py] WARNING: no Chroma index found at {CHROMA_DB_PATH}. "
            "Run `python rag_setup.py` first for grounded, on-voice outreach. "
            "Continuing with empty retrieval context.",
            file=sys.stderr,
        )
        return ""
    try:
        from langchain_ollama import OllamaEmbeddings
        from langchain_community.vectorstores import Chroma

        embeddings = OllamaEmbeddings(model=embed_model, base_url=ollama_base_url)
        vectordb = Chroma(persist_directory=str(CHROMA_DB_PATH), embedding_function=embeddings)
        results = vectordb.similarity_search(RETRIEVAL_QUERY, k=RETRIEVAL_K)
        return "\n\n---\n\n".join(d.page_content for d in results)
    except Exception as e:
        print(f"[outreach_local.py] WARNING: retrieval failed ({e}). Continuing with empty context.",
              file=sys.stderr)
        return ""


def find_demo_link(slug: str) -> str:
    """If a demo was already generated for this lead, reference its local path.

    NOTE: this is a local file path, not a public URL — Robert's real pipeline
    presumably uploads demos somewhere reachable (e.g. a subdomain/staging
    host) before referencing them in outreach. Swap in that real link logic
    here once you have it; this placeholder just points at the local file so
    outreach drafts have *something* concrete to reference.
    """
    demo_path = DEMOS_DIR / slug / "index.html"
    if demo_path.exists():
        return f"(local preview file: output/demos/{slug}/index.html — upload/host before sending)"
    return "(no demo generated yet for this lead)"


def build_prompt(
    lead: dict,
    system_prompt: str,
    retrieved_context: str,
    demo_link: str,
    physical_address: str,
    unsubscribe_link: str,
) -> str:
    business_context = "\n".join(
        f"- {k}: {v}" for k, v in lead.items() if v not in (None, "", "None")
    )
    prompt = f"""{system_prompt}

---

## Business data (real — use only this, do not invent additional facts)

{business_context}

## Retrieved context from Obsidian Labs' voice notes / past outreach / pricing

{retrieved_context if retrieved_context else '(no retrieved context available — rely on the guardrails above)'}

## Values to embed exactly as given

- physical_address: {physical_address}
- unsubscribe_link: {unsubscribe_link}
- demo_link: {demo_link}

Now generate the 3-email outreach sequence for this business, following the
output format specified above exactly.
"""
    return prompt


def generate_sequence(prompt: str, model: str, ollama_base_url: str) -> str:
    from langchain_ollama import OllamaLLM

    llm = OllamaLLM(model=model, base_url=ollama_base_url, temperature=0.5)
    raw = llm.invoke(prompt)
    return raw.strip()


def ensure_compliance(markdown: str, physical_address: str, unsubscribe_link: str) -> str:
    """
    Belt-and-suspenders check: if the model dropped the address or unsubscribe
    line anywhere, append a compliance footer so no draft is ever missing them,
    even though the prompt already asks for them in every email body.
    """
    has_address = physical_address.split(",")[0].strip().lower() in markdown.lower()
    has_unsub = unsubscribe_link.lower() in markdown.lower()
    if has_address and has_unsub:
        return markdown

    footer = (
        f"\n\n---\n\n_Compliance footer (auto-appended — verify it's also present "
        f"naturally in each email body above before sending):_\n\n"
        f"{physical_address}  \n"
        f"Don't want these emails? Unsubscribe here: {unsubscribe_link}\n"
    )
    return markdown + footer


def main() -> None:
    # encoding="utf-8-sig" tolerates a leading UTF-8 BOM, which Windows
    # Notepad silently adds when saving with "UTF-8" encoding - a BOM
    # corrupts the first KEY=VALUE line for plain utf-8 parsing.
    load_dotenv(ROOT / ".env", encoding="utf-8-sig")

    parser = argparse.ArgumentParser(description="Draft 3-touch outreach sequences for hot leads via local RAG + Ollama")
    parser.add_argument("--input", default=str(LEADS_GRADED_CSV), help="Path to leads_graded.csv")
    parser.add_argument("--limit", type=int, default=None, help="Max number of drafts to generate this run")
    parser.add_argument("--model", default=os.getenv("OLLAMA_MODEL", "qwen2.5:14b-instruct-q4_K_M"))
    parser.add_argument("--embed-model", default=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"))
    parser.add_argument("--ollama-base-url", default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))
    parser.add_argument(
        "--physical-address",
        default=os.getenv("PHYSICAL_ADDRESS", "85 Wixon Pond Rd, Mahopac, NY 10541"),
    )
    parser.add_argument(
        "--unsubscribe-link",
        default=os.getenv("UNSUBSCRIBE_LINK", "https://obsidianlabshq.io/unsubscribe"),
    )
    args = parser.parse_args()

    if not PROMPT_TEMPLATE_PATH.exists():
        print(f"[outreach_local.py] ERROR: missing {PROMPT_TEMPLATE_PATH}", file=sys.stderr)
        sys.exit(1)
    system_prompt = PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")

    hot_leads = load_hot_leads(Path(args.input))
    if args.limit:
        hot_leads = hot_leads[: args.limit]

    if not hot_leads:
        print("[outreach_local.py] No hot leads found. Nothing to draft.")
        return

    retrieved_context = get_retrieved_context(args.embed_model, args.ollama_base_url)

    OUTREACH_DIR.mkdir(parents=True, exist_ok=True)

    for i, lead in enumerate(hot_leads, start=1):
        name = lead.get("name", f"lead-{i}")
        slug = slugify(name)
        print(f"[outreach_local.py] ({i}/{len(hot_leads)}) Drafting outreach for {name} -> outreach/{slug}.md")

        demo_link = find_demo_link(slug)
        prompt = build_prompt(
            lead, system_prompt, retrieved_context, demo_link,
            args.physical_address, args.unsubscribe_link,
        )
        try:
            sequence = generate_sequence(prompt, args.model, args.ollama_base_url)
        except Exception as e:
            print(f"[outreach_local.py]   ! generation failed for {name}: {e}", file=sys.stderr)
            continue

        sequence = ensure_compliance(sequence, args.physical_address, args.unsubscribe_link)

        header = (
            f"# Outreach draft — {name}\n\n"
            f"_DRAFT ONLY. Not sent. Review and approve in the dashboard before sending._\n\n"
        )
        (OUTREACH_DIR / f"{slug}.md").write_text(header + sequence, encoding="utf-8")

    print(f"[outreach_local.py] Done. Drafts written to {OUTREACH_DIR}")


if __name__ == "__main__":
    main()

```

## `dashboard.py`  
_(468 lines)_

```python
#!/usr/bin/env python3
"""
dashboard.py - Obsidian Labs local review/approval dashboard (Streamlit)

Run with:
    streamlit run dashboard.py
    # or: python pipeline.py --stage dashboard

Opens at http://localhost:8501

Dark-theme dashboard (see .streamlit/config.toml) with a left sidebar nav:

  - Dashboard  - two-column view: leads table (left) + live HTML preview of
                 the selected lead's generated demo (right). Prominent
                 "Run Pipeline" and "Approve & Send" buttons up top.
  - Leads      - full leads_graded.csv table + CSV download.
  - Demos      - expandable preview of every generated demo, with an
                 "Approve & Queue Outreach" button stub per lead.
  - Outreach   - view generated drafts, with stubbed approve/send buttons.
  - Settings   - read-only view of current .env config (secrets masked) and
                 key paths, for a quick sanity check.

IMPORTANT: Nothing in this dashboard actually sends email or runs anything
irreversible. "Approve" buttons just log an approval record to
output/logs/approvals.csv. "Run Pipeline" launches pipeline.py as a
background subprocess (so you can watch its log) - it does NOT auto-send
outreach; the outreach stage only ever writes draft files. Real sending is a
separate, deliberate step outside this codebase (e.g. wiring up Brevo), per
the compliance requirement that outreach never auto-sends.
"""

from __future__ import annotations

import csv
import datetime as dt
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "output"
DEMOS_DIR = OUTPUT_DIR / "demos"
OUTREACH_DIR = OUTPUT_DIR / "outreach"
LOGS_DIR = OUTPUT_DIR / "logs"
LEADS_GRADED_CSV = OUTPUT_DIR / "leads_graded.csv"
APPROVALS_LOG = LOGS_DIR / "approvals.csv"
PIPELINE_RUN_LOG = LOGS_DIR / "pipeline_run.log"
ENV_PATH = ROOT / ".env"

st.set_page_config(
    page_title="Obsidian Labs - Pipeline Dashboard",
    page_icon="⬛",
    layout="wide",
)

st.markdown(
    """
    <style>
    div[data-testid="stStatusWidget"] { display: none; }
    .pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        text-align: center;
    }
    .pill-red    { background-color: #ef4444; color: #fff; }
    .pill-amber  { background-color: #f59e0b; color: #111; }
    .pill-green  { background-color: #22c55e; color: #111; }
    .pill-gray   { background-color: #6b7280; color: #fff; }
    section[data-testid="stSidebar"] { border-right: 1px solid #22262e; }
    </style>
    """,
    unsafe_allow_html=True,
)


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return slug or "lead"


def log_approval(kind: str, identifier: str) -> None:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    is_new = not APPROVALS_LOG.exists()
    with APPROVALS_LOG.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["timestamp", "kind", "identifier"])
        writer.writerow([dt.datetime.now().isoformat(timespec="seconds"), kind, identifier])


@st.cache_data(ttl=5)
def load_leads_df():
    if not LEADS_GRADED_CSV.exists():
        return None
    return pd.read_csv(LEADS_GRADED_CSV)


def status_for_row(row):
    status = str(row.get("status", "")).strip().lower()
    try:
        perf = float(row.get("perf_score", 0))
    except (TypeError, ValueError):
        perf = 0

    if status == "no_website":
        return "No Website", "pill-red"
    if status == "unreachable":
        return "Unreachable", "pill-red"
    if status == "api_error":
        return "Grade Error", "pill-gray"
    if perf <= 50:
        return "Needs Improvement", "pill-amber"
    return "Healthy", "pill-green"


def build_display_df(df):
    display = pd.DataFrame(
        {
            "Business Name": df.get("name", ""),
            "Niche": df.get("type", ""),
            "Town": df.get("town", ""),
            "Website Score": pd.to_numeric(df.get("perf_score", 0), errors="coerce").fillna(0).astype(int),
        }
    )
    labels = []
    classes = []
    for _, row in df.iterrows():
        label, css_class = status_for_row(row)
        labels.append(label)
        classes.append(css_class)
    display["Status"] = labels
    display["_status_class"] = classes
    display["_slug"] = df.get("name", "").map(slugify)
    return display


def demo_path_for_slug(slug: str) -> Path:
    return DEMOS_DIR / slug / "index.html"


def render_sidebar() -> str:
    with st.sidebar:
        st.markdown("### ⬛ Obsidian Labs")
        st.caption("Local AI Automation")
        st.divider()
        page = st.radio(
            "Navigate",
            ["Dashboard", "Leads", "Demos", "Outreach", "Settings"],
            label_visibility="collapsed",
        )
        st.divider()
        df = load_leads_df()
        if df is not None:
            hot = 0
            if "is_hot_lead" in df.columns:
                hot = df["is_hot_lead"].astype(str).str.lower().isin(["true", "1", "yes"]).sum()
            st.caption(f"{len(df)} leads, {hot} hot")
        n_demos = 0
        if DEMOS_DIR.exists():
            n_demos = len(list(DEMOS_DIR.glob("*/index.html")))
        n_outreach = 0
        if OUTREACH_DIR.exists():
            n_outreach = len(list(OUTREACH_DIR.glob("*.md")))
        st.caption(f"{n_demos} demos, {n_outreach} outreach drafts")
        st.divider()
        st.caption("Runs 100% locally. Nothing auto-sends.")
    return page


def render_top_bar(selected_slug) -> None:
    left, right, _ = st.columns([1, 1, 3])

    with left:
        with st.popover("Run Pipeline", width="stretch"):
            st.caption(
                "Launches pipeline.py in the background. Requires a running "
                "local Ollama server for the RAG/demo/outreach stages."
            )
            towns = st.text_input("Towns (space-separated)", value="Mahopac Carmel")
            niches = st.text_input("Niches (space-separated)", value="dentist roofer")
            limit = st.number_input("Limit per town/niche", min_value=1, max_value=50, value=5)
            stage = st.selectbox(
                "Stage",
                ["all", "scrape", "grade", "rag_ingest", "demo", "outreach"],
                index=0,
            )
            if st.button("Start run", type="primary"):
                cmd = [sys.executable, "pipeline.py", "--stage", stage]
                if stage in ("all", "scrape"):
                    cmd += [
                        "--towns", *towns.split(),
                        "--niches", *niches.split(),
                        "--limit", str(int(limit)),
                    ]
                LOGS_DIR.mkdir(parents=True, exist_ok=True)
                with PIPELINE_RUN_LOG.open("a", encoding="utf-8") as log_f:
                    log_f.write(
                        f"\n\n=== {dt.datetime.now().isoformat(timespec='seconds')} "
                        f"- {' '.join(cmd)} ===\n"
                    )
                    subprocess.Popen(cmd, cwd=str(ROOT), stdout=log_f, stderr=subprocess.STDOUT)
                st.success("Started in background. Tail output/logs/pipeline_run.log, or refresh this page shortly.")

    with right:
        disabled = selected_slug is None
        if st.button("Approve & Send", type="primary", disabled=disabled, width="stretch"):
            log_approval("dashboard_approve_and_send", selected_slug)
            st.success(
                f"Logged approval for '{selected_slug}'. This does NOT send anything - "
                "outreach sending is a separate, deliberate step outside this dashboard."
            )
        if disabled:
            st.caption("Select a lead below to enable Approve & Send.")
        else:
            st.caption("Logs an approval only - never sends automatically.")


def page_dashboard() -> None:
    st.title("Dashboard")

    df = load_leads_df()
    if df is None:
        render_top_bar(None)
        st.info(
            "No output/leads_graded.csv yet. Use **Run Pipeline** above "
            "(stage: scrape, then grade - or stage: all) to populate this."
        )
        return

    display_df = build_display_df(df)

    if "selected_slug" not in st.session_state:
        st.session_state.selected_slug = display_df["_slug"].iloc[0] if len(display_df) else None

    render_top_bar(st.session_state.selected_slug)
    st.divider()

    col_leads, col_preview = st.columns([2, 3])

    with col_leads:
        st.subheader("Leads")
        table_df = display_df.drop(columns=["_status_class", "_slug"])

        try:
            styled = table_df.style.map(
                lambda v: {
                    "No Website": "background-color:#ef4444;color:#fff;",
                    "Unreachable": "background-color:#ef4444;color:#fff;",
                    "Grade Error": "background-color:#6b7280;color:#fff;",
                    "Needs Improvement": "background-color:#f59e0b;color:#111;",
                    "Healthy": "background-color:#22c55e;color:#111;",
                }.get(v, ""),
                subset=["Status"],
            )
            table_to_show = styled
        except Exception:
            table_to_show = table_df

        event = None
        try:
            event = st.dataframe(
                table_to_show,
                width="stretch",
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="leads_table",
            )
        except TypeError:
            st.dataframe(table_to_show, width="stretch", hide_index=True)

        clicked_slug = None
        if event is not None:
            try:
                rows = event.selection.rows
                if rows:
                    clicked_slug = display_df.iloc[rows[0]]["_slug"]
            except Exception:
                clicked_slug = None

        if clicked_slug:
            st.session_state.selected_slug = clicked_slug
        else:
            names = display_df["Business Name"].tolist()
            slugs = display_df["_slug"].tolist()
            if names:
                try:
                    current_idx = slugs.index(st.session_state.selected_slug)
                except ValueError:
                    current_idx = 0
                picked = st.selectbox(
                    "Or pick a lead manually:",
                    options=range(len(names)),
                    index=current_idx,
                    format_func=lambda i: names[i],
                )
                st.session_state.selected_slug = slugs[picked]

    with col_preview:
        st.subheader("HTML Preview")
        slug = st.session_state.selected_slug
        demo_file = demo_path_for_slug(slug) if slug else None
        if demo_file and demo_file.exists():
            html = demo_file.read_text(encoding="utf-8")
            st.components.v1.html(html, height=720, scrolling=True)
        else:
            st.info(
                "No demo generated yet for this lead. Run the **demo** stage "
                "(Run Pipeline above) to generate one."
            )


def page_leads() -> None:
    st.title("Leads")
    df = load_leads_df()
    if df is None:
        st.info(
            "No output/leads_graded.csv yet. Run `python pipeline.py --stage scrape` "
            "then `--stage grade` (or `--stage all`) to populate this."
        )
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Total leads", len(df))
    if "is_hot_lead" in df.columns:
        hot = df["is_hot_lead"].astype(str).str.lower().isin(["true", "1", "yes"]).sum()
        col2.metric("Hot leads (demo candidates)", int(hot))
    if "perf_score" in df.columns:
        col3.metric("Avg perf score", round(pd.to_numeric(df["perf_score"], errors="coerce").mean(), 1))

    st.dataframe(df, width="stretch")

    st.download_button(
        "Download leads_graded.csv",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="leads_graded.csv",
        mime="text/csv",
    )


def page_demos() -> None:
    st.title("Demos")
    if not DEMOS_DIR.exists() or not any(DEMOS_DIR.iterdir()):
        st.info(
            "No demos generated yet. Run `python pipeline.py --stage demo` "
            "(requires a running local Ollama server and a built RAG index)."
        )
        return

    demo_dirs = sorted(p for p in DEMOS_DIR.iterdir() if p.is_dir())
    for demo_dir in demo_dirs:
        index_file = demo_dir / "index.html"
        if not index_file.exists():
            continue
        with st.expander(f"{demo_dir.name}"):
            html = index_file.read_text(encoding="utf-8")
            st.components.v1.html(html, height=600, scrolling=True)

            approve_col, _ = st.columns([1, 3])
            with approve_col:
                if st.button("Approve & Queue Outreach", key=f"approve_demo_{demo_dir.name}"):
                    log_approval("demo_approved", demo_dir.name)
                    st.success(
                        f"Logged approval for '{demo_dir.name}'. "
                        "This does NOT send anything - it just records that you've "
                        "reviewed and greenlit this lead for outreach drafting/review."
                    )


def page_outreach() -> None:
    st.title("Outreach Drafts")
    st.caption(
        "Drafts only - approving here just logs the approval. Actually sending "
        "requires a separate, explicit action outside this dashboard (e.g. wiring "
        "up Brevo) so nothing goes out without a deliberate human step."
    )

    if not OUTREACH_DIR.exists() or not any(OUTREACH_DIR.glob("*.md")):
        st.info(
            "No outreach drafts yet. Run `python pipeline.py --stage outreach` "
            "(requires a running local Ollama server and a built RAG index)."
        )
        return

    draft_files = sorted(OUTREACH_DIR.glob("*.md"))
    for draft_file in draft_files:
        with st.expander(f"{draft_file.stem}"):
            content = draft_file.read_text(encoding="utf-8")
            st.markdown(content)

            c1, c2 = st.columns([1, 1])
            with c1:
                if st.button("Approve", key=f"approve_outreach_{draft_file.stem}"):
                    log_approval("outreach_approved", draft_file.stem)
                    st.success(f"Logged approval for '{draft_file.stem}'.")
            with c2:
                if st.button("Send (stub - not implemented)", key=f"send_outreach_{draft_file.stem}"):
                    st.warning(
                        "Sending is intentionally not implemented in this dashboard. "
                        "Approved drafts are logged to output/logs/approvals.csv - "
                        "wire up Brevo (or your sender of choice) as a separate, "
                        "deliberate step when you're ready to actually send."
                    )


def page_settings() -> None:
    st.title("Settings")
    st.caption("Read-only view of your current configuration. Secrets are masked.")

    if not ENV_PATH.exists():
        st.warning(
            "No .env file found. Copy .env.example to .env and fill in your "
            "GOOGLE_API_KEY (and other values) before running the pipeline."
        )
        return

    # encoding="utf-8-sig" tolerates a leading UTF-8 BOM, which Windows
    # Notepad silently adds when saving with "UTF-8" encoding - a BOM
    # corrupts the first KEY=VALUE line for plain utf-8 parsing.
    values = dotenv_values(ENV_PATH, encoding="utf-8-sig")
    secret_keys = {"GOOGLE_API_KEY", "BREVO_API_KEY"}
    rows = []
    for key, value in values.items():
        display_value = value or ""
        if key in secret_keys and display_value:
            display_value = display_value[:4] + "..." + ("*" * 4)
        rows.append({"Key": key, "Value": display_value})

    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    st.divider()
    st.subheader("Paths")
    chroma_path = ROOT / "chroma_db"
    n_demos = len(list(DEMOS_DIR.glob("*/index.html"))) if DEMOS_DIR.exists() else 0
    n_outreach = len(list(OUTREACH_DIR.glob("*.md"))) if OUTREACH_DIR.exists() else 0
    st.code(
        f"Repo root:       {ROOT}\n"
        f"Chroma DB:       {chroma_path} (exists: {chroma_path.exists()})\n"
        f"leads_graded.csv exists: {LEADS_GRADED_CSV.exists()}\n"
        f"Demos generated: {n_demos}\n"
        f"Outreach drafts: {n_outreach}\n",
        language="text",
    )


def main() -> None:
    page = render_sidebar()

    pages = {
        "Dashboard": page_dashboard,
        "Leads": page_leads,
        "Demos": page_demos,
        "Outreach": page_outreach,
        "Settings": page_settings,
    }
    pages[page]()


main()

```

# Backend (API)

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

# Dashboards (live, browser/PWA)

## `dashboard_leadflow.html`  
_(669 lines)_

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Obsidian Labs — Dashboard</title>
  <link rel="manifest" href="manifest.json" />
  <link rel="icon" href="icon-192.png" />
  <link rel="apple-touch-icon" href="icon-192.png" />
  <meta name="theme-color" content="#f6f7f9" />
  <style>
    /* ============================================================
       Obsidian Labs — LeadFlow-style light dashboard.
       Single self-contained file. Same fastapi_backend on :8502,
       no backend changes. Charts are hand-drawn inline SVG (CSP-safe).
       ============================================================ */
    :root {
      --purple: #7c3aed;
      --purple-600: #6d28d9;
      --purple-50: #f3effe;
      --purple-100: #ede9fe;
      --blue: #3b82f6;
      --teal: #14b8a6;
      --orange: #f59e0b;
      --bg: #f6f7f9;
      --card: #ffffff;
      --border: #eceef2;
      --border-2: #e5e7eb;
      --text: #111827;
      --muted: #6b7280;
      --faint: #9ca3af;
      --good-bg: #dcfce7; --good-fg: #15803d;
      --new-bg: #dbeafe;  --new-fg: #1d4ed8;
      --warn-bg: #fef3c7; --warn-fg: #b45309;
      --bad-bg: #fee2e2;  --bad-fg: #b91c1c;
      --gray-bg: #f1f5f9; --gray-fg: #475569;
      --radius: 16px;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0; background: var(--bg); color: var(--text);
      font-family: system-ui, -apple-system, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      -webkit-font-smoothing: antialiased; letter-spacing: -0.011em;
    }
    .app { display: grid; grid-template-columns: 248px 1fr; min-height: 100vh; }

    /* ---------- sidebar ---------- */
    .sidebar { background: var(--card); border-right: 1px solid var(--border); padding: 1.25rem 0.9rem; display: flex; flex-direction: column; gap: 0.35rem; position: sticky; top: 0; height: 100vh; }
    .logo { display: flex; align-items: center; gap: 0.6rem; font-weight: 700; font-size: 1.15rem; padding: 0.2rem 0.6rem 1rem; }
    .logo .mark { width: 34px; height: 34px; border-radius: 10px; background: linear-gradient(150deg, var(--purple), #4f46e5); display: grid; place-items: center; color: #fff; font-size: 1.05rem; box-shadow: 0 6px 16px rgba(124,58,237,.35); }
    .nav { display: flex; flex-direction: column; gap: 0.15rem; }
    .nav button { display: flex; align-items: center; gap: 0.75rem; width: 100%; text-align: left; background: none; border: none; padding: 0.62rem 0.8rem; border-radius: 11px; font-size: 0.92rem; font-weight: 550; color: var(--muted); cursor: pointer; font-family: inherit; transition: all .15s; }
    .nav button:hover { background: var(--bg); color: var(--text); }
    .nav button.active { background: var(--purple-100); color: var(--purple-600); font-weight: 650; }
    .nav .ico { width: 20px; height: 20px; flex: none; opacity: .9; }
    .side-spacer { flex: 1; }
    .promo { background: var(--purple-50); border: 1px solid var(--purple-100); border-radius: var(--radius); padding: 1.1rem; text-align: center; margin: 0.5rem 0.3rem; }
    .promo .rocket { font-size: 1.5rem; }
    .promo h4 { margin: 0.5rem 0 0.3rem; font-size: 1.02rem; }
    .promo p { margin: 0 0 0.85rem; font-size: 0.82rem; color: var(--muted); line-height: 1.4; }
    .profile { display: flex; align-items: center; gap: 0.6rem; padding: 0.7rem 0.6rem 0.2rem; border-top: 1px solid var(--border); margin-top: 0.3rem; }
    .avatar { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-weight: 650; font-size: 0.85rem; flex: none; }
    .profile .who { font-size: 0.86rem; font-weight: 600; line-height: 1.2; }
    .profile .who small { display: block; color: var(--faint); font-weight: 400; font-size: 0.76rem; }

    /* ---------- main ---------- */
    .main { padding: 1.6rem 2rem 3rem; min-width: 0; }
    .topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
    .topbar h1 { margin: 0 0 0.25rem; font-size: 1.7rem; letter-spacing: -0.03em; }
    .topbar .sub { margin: 0; color: var(--muted); font-size: 0.92rem; max-width: 40ch; }
    .top-actions { display: flex; align-items: center; gap: 0.6rem; }
    .chip { display: inline-flex; align-items: center; gap: 0.5rem; background: var(--card); border: 1px solid var(--border-2); border-radius: 11px; padding: 0.55rem 0.85rem; font-size: 0.85rem; font-weight: 550; cursor: pointer; }
    .icon-btn { width: 42px; height: 42px; border-radius: 11px; background: var(--card); border: 1px solid var(--border-2); cursor: pointer; font-size: 1rem; position: relative; }
    .icon-btn .badge { position: absolute; top: 9px; right: 10px; width: 7px; height: 7px; background: var(--purple); border-radius: 50%; }

    .card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: 0 1px 2px rgba(16,24,40,.04); }

    /* KPI row */
    .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.1rem; margin-bottom: 1.3rem; }
    .kpi { padding: 1.15rem 1.2rem; }
    .kpi .kico { width: 42px; height: 42px; border-radius: 11px; display: grid; place-items: center; font-size: 1.1rem; margin-bottom: 0.85rem; }
    .kico.p { background: var(--purple-100); color: var(--purple-600); }
    .kico.b { background: #dbeafe; color: var(--blue); }
    .kico.t { background: #ccfbf1; color: #0f766e; }
    .kico.o { background: #fef3c7; color: #b45309; }
    .kpi .klabel { font-size: 0.85rem; color: var(--muted); }
    .kpi .kvalue { font-size: 1.85rem; font-weight: 750; letter-spacing: -0.03em; margin: 0.1rem 0 0.35rem; font-variant-numeric: tabular-nums; }
    .kpi .kdelta { font-size: 0.8rem; font-weight: 600; display: inline-flex; gap: 0.3rem; align-items: center; }
    .kdelta.up { color: #15803d; } .kdelta.down { color: #b91c1c; } .kdelta.flat { color: var(--faint); }
    .kpi .kspark { margin-top: 0.7rem; height: 34px; }
    .kpi .kspark svg { width: 100%; height: 100%; display: block; }

    /* charts row */
    .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 1.3rem; margin-bottom: 1.3rem; }
    .panel { padding: 1.3rem 1.4rem; }
    .panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem; }
    .panel-head h3 { margin: 0; font-size: 1.12rem; letter-spacing: -0.02em; }
    select.range { border: 1px solid var(--border-2); border-radius: 9px; padding: 0.4rem 0.6rem; font-size: 0.82rem; font-family: inherit; background: var(--card); color: var(--text); cursor: pointer; }
    .area-wrap svg { width: 100%; height: auto; display: block; }
    .donut-wrap { display: flex; gap: 1.4rem; align-items: center; flex-wrap: wrap; }
    .donut-wrap svg { flex: none; }
    .legend { flex: 1; min-width: 200px; display: flex; flex-direction: column; gap: 0.55rem; }
    .legend-row { display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 0.6rem; font-size: 0.9rem; }
    .legend-row .lname { display: flex; align-items: center; gap: 0.55rem; color: var(--text); }
    .legend-row .swatch { width: 10px; height: 10px; border-radius: 50%; }
    .legend-row .lpct { color: var(--muted); font-variant-numeric: tabular-nums; }
    .legend-row .lval { display: inline-flex; align-items: center; gap: 0.4rem; font-variant-numeric: tabular-nums; font-weight: 600; }
    .legend-row .lval .swatch { width: 8px; height: 8px; }

    /* recent leads table */
    .table-card { padding: 1.3rem 0; }
    .table-head { display: flex; align-items: center; justify-content: space-between; padding: 0 1.4rem 0.9rem; }
    .table-head h3 { margin: 0; font-size: 1.12rem; }
    .link { color: var(--purple); font-weight: 600; font-size: 0.9rem; text-decoration: none; cursor: pointer; background: none; border: none; font-family: inherit; }
    .tscroll { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; min-width: 620px; }
    thead th { text-align: left; padding: 0.7rem 1rem; color: var(--muted); font-weight: 600; font-size: 0.82rem; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); background: #fafbfc; }
    thead th:first-child { padding-left: 1.4rem; }
    tbody td { padding: 0.85rem 1rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
    tbody td:first-child { padding-left: 1.4rem; color: var(--faint); font-variant-numeric: tabular-nums; }
    tbody tr { cursor: pointer; }
    tbody tr:hover { background: #fafafe; }
    .cell-name { display: flex; align-items: center; gap: 0.7rem; }
    .cell-name .avatar { width: 34px; height: 34px; font-size: 0.78rem; }
    .cell-name .nm { font-weight: 600; }
    .pill { display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 0.78rem; font-weight: 600; }
    .pill-good { background: var(--good-bg); color: var(--good-fg); }
    .pill-new  { background: var(--new-bg);  color: var(--new-fg); }
    .pill-warn { background: var(--warn-bg); color: var(--warn-fg); }
    .pill-bad  { background: var(--bad-bg);  color: var(--bad-fg); }
    .pill-gray { background: var(--gray-bg); color: var(--gray-fg); }
    .kebab { background: none; border: none; color: var(--faint); cursor: pointer; font-size: 1.1rem; padding: 0 0.4rem; }
    .val { font-weight: 650; font-variant-numeric: tabular-nums; }

    /* bottom banner */
    .banner { margin-top: 1.3rem; background: linear-gradient(100deg, var(--purple-100), #e0e7ff); border-radius: var(--radius); padding: 1.4rem 1.6rem; display: flex; align-items: center; gap: 1.2rem; flex-wrap: wrap; }
    .banner .bico { width: 54px; height: 54px; border-radius: 14px; background: #fff; display: grid; place-items: center; font-size: 1.5rem; flex: none; box-shadow: 0 4px 12px rgba(124,58,237,.18); }
    .banner .btxt { flex: 1; min-width: 220px; }
    .banner h4 { margin: 0 0 0.25rem; font-size: 1.1rem; }
    .banner p { margin: 0; color: #4b5563; font-size: 0.9rem; }

    .btn { border: none; border-radius: 11px; padding: 0.7rem 1.3rem; font-weight: 650; font-size: 0.9rem; cursor: pointer; font-family: inherit; background: var(--purple); color: #fff; box-shadow: 0 6px 16px rgba(124,58,237,.3); transition: all .15s; }
    .btn:hover { background: var(--purple-600); transform: translateY(-1px); }
    .btn.block { width: 100%; }
    .btn.small { padding: 0.45rem 0.9rem; font-size: 0.82rem; }
    .btn.secondary { background: #fff; color: var(--purple-600); border: 1px solid var(--purple-100); box-shadow: none; }
    .run-status { color: var(--muted); font-size: 0.85rem; margin: 0.8rem 0 0; }
    .muted { color: var(--muted); font-size: 0.9rem; }
    .empty { color: var(--faint); font-size: 0.9rem; padding: 1rem 1.4rem; }
    .subpage { display: none; }
    .subpage .panel { margin-bottom: 1.3rem; }

    /* demo modal */
    #modal { position: fixed; inset: 0; background: rgba(17,24,39,.5); backdrop-filter: blur(3px); display: none; align-items: center; justify-content: center; z-index: 70; padding: 1rem; }
    #modal.open { display: flex; }
    .modal-card { background: var(--card); border-radius: var(--radius); width: min(880px, 96vw); max-height: 92vh; overflow: hidden; display: flex; flex-direction: column; }
    .modal-head { display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.3rem; border-bottom: 1px solid var(--border); }
    .modal-head h3 { margin: 0; font-size: 1.05rem; }
    .modal-body { padding: 1.1rem 1.3rem; overflow: auto; }
    .device-toggle { display: flex; gap: 0.4rem; margin-bottom: 0.85rem; }
    .device-toggle button { padding: 0.34rem 0.85rem; border-radius: 9999px; border: 1px solid var(--border-2); background: #fff; color: var(--muted); cursor: pointer; font-size: 0.78rem; }
    .device-toggle button.active { background: var(--purple); color: #fff; border-color: var(--purple); }
    .preview-frame-wrap { display: flex; justify-content: center; }
    iframe#demo-preview { border: 1px solid var(--border); border-radius: 12px; width: 100%; height: 520px; background: #fff; }

    /* chat */
    #chat-toggle { position: fixed; bottom: 22px; right: 22px; width: 54px; height: 54px; border-radius: 50%; background: var(--purple); color: #fff; border: none; font-size: 1.3rem; cursor: pointer; box-shadow: 0 8px 24px rgba(124,58,237,.4); z-index: 60; }
    #chat-panel { position: fixed; bottom: 86px; right: 22px; width: 340px; max-height: 480px; background: var(--card); border: 1px solid var(--border-2); border-radius: var(--radius); z-index: 60; display: none; flex-direction: column; overflow: hidden; box-shadow: 0 18px 50px rgba(16,24,40,.25); }
    #chat-panel.open { display: flex; }
    #chat-header { padding: 0.8rem 1rem; font-weight: 600; font-size: 0.9rem; border-bottom: 1px solid var(--border); background: var(--purple); color: #fff; }
    #chat-messages { flex: 1; overflow-y: auto; padding: 0.85rem 1rem; display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.85rem; }
    .chat-msg { padding: 0.5rem 0.75rem; border-radius: 13px; max-width: 86%; line-height: 1.45; }
    .chat-msg.user { align-self: flex-end; background: var(--purple); color: #fff; }
    .chat-msg.bot { align-self: flex-start; background: #f1f0f7; color: var(--text); }
    #chat-input-row { display: flex; border-top: 1px solid var(--border); }
    #chat-input { flex: 1; border: none; background: transparent; color: var(--text); padding: 0.8rem; font-size: 0.85rem; font-family: inherit; }
    #chat-send { border: none; background: var(--purple); color: #fff; padding: 0 1.1rem; cursor: pointer; font-family: inherit; }

    :focus-visible { outline: 2px solid var(--purple); outline-offset: 2px; }

    /* ---------- responsive ---------- */
    @media (max-width: 1050px) { .kpis { grid-template-columns: repeat(2, 1fr); } .charts { grid-template-columns: 1fr; } }
    @media (max-width: 820px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { position: static; height: auto; flex-direction: row; align-items: center; gap: 0.5rem; overflow-x: auto; padding: 0.7rem 0.9rem; }
      .logo { padding: 0 0.5rem; font-size: 1rem; }
      .nav { flex-direction: row; gap: 0.2rem; }
      .nav button { padding: 0.45rem 0.7rem; white-space: nowrap; }
      .nav .ico { display: none; }
      .side-spacer, .promo, .profile { display: none; }
      .main { padding: 1.2rem 1rem 3rem; }
    }
    @media (max-width: 520px) { .kpis { grid-template-columns: 1fr 1fr; gap: 0.8rem; } .topbar h1 { font-size: 1.4rem; } }
  </style>
</head>
<body>
  <div class="app">
    <!-- ==================== SIDEBAR ==================== -->
    <aside class="sidebar">
      <div class="logo"><span class="mark">◆</span> Obsidian Labs</div>
      <nav class="nav" id="nav">
        <button data-page="dashboard" class="active"><span class="ico">▦</span> Dashboard</button>
        <button data-page="leads"><span class="ico">☰</span> Leads</button>
        <button data-page="demos"><span class="ico">▤</span> Demos</button>
        <button data-page="outreach"><span class="ico">✉</span> Outreach</button>
        <button data-page="dashboard"><span class="ico">◔</span> Analytics</button>
        <button id="nav-settings"><span class="ico">⚙</span> Settings</button>
      </nav>
      <div class="side-spacer"></div>
      <div class="promo">
        <div class="rocket">🚀</div>
        <h4>Grow your pipeline</h4>
        <p>Gather new local businesses and build demos automatically — 100% local.</p>
        <button class="btn block" id="promo-run">Run Pipeline</button>
      </div>
      <div class="profile">
        <div class="avatar" style="background:#7c3aed;">RC</div>
        <div class="who">Robert Castro<small>themortgagemaster01@gmail.com</small></div>
      </div>
    </aside>

    <!-- ==================== MAIN ==================== -->
    <main class="main">
      <div class="topbar">
        <div>
          <h1>Dashboard</h1>
          <p class="sub">Welcome back, Robert! Here's what's happening with your leads.</p>
        </div>
        <div class="top-actions">
          <button class="chip" id="range-chip">📅 <span id="range-label">This month</span></button>
          <button class="icon-btn" id="settings-btn" title="Settings / backend URL">🔔<span class="badge"></span></button>
        </div>
      </div>

      <!-- ===== DASHBOARD PAGE ===== -->
      <section id="page-dashboard">
        <!-- KPI cards -->
        <div class="kpis">
          <div class="card kpi">
            <div class="kico p">👥</div>
            <div class="klabel">Total Leads</div>
            <div class="kvalue" id="k-leads">–</div>
            <div class="kdelta flat" id="d-leads">—</div>
            <div class="kspark" id="s-leads"></div>
          </div>
          <div class="card kpi">
            <div class="kico b">🎯</div>
            <div class="klabel">Hot Leads</div>
            <div class="kvalue" id="k-hot">–</div>
            <div class="kdelta flat" id="d-hot">—</div>
            <div class="kspark" id="s-hot"></div>
          </div>
          <div class="card kpi">
            <div class="kico t">📤</div>
            <div class="klabel">Demos Generated</div>
            <div class="kvalue" id="k-demos">–</div>
            <div class="kdelta flat" id="d-demos">—</div>
            <div class="kspark" id="s-demos"></div>
          </div>
          <div class="card kpi">
            <div class="kico o">📝</div>
            <div class="klabel">Outreach Drafts</div>
            <div class="kvalue" id="k-drafts">–</div>
            <div class="kdelta flat" id="d-drafts">—</div>
            <div class="kspark" id="s-drafts"></div>
          </div>
        </div>

        <!-- charts -->
        <div class="charts">
          <div class="card panel area-wrap">
            <div class="panel-head">
              <h3>Lead Growth</h3>
              <select class="range" id="growth-range">
                <option value="8">This Month</option>
                <option value="30">Last 30 pts</option>
                <option value="5">Last 5 pts</option>
              </select>
            </div>
            <div id="area-chart"></div>
          </div>
          <div class="card panel">
            <div class="panel-head"><h3>Leads by Niche</h3></div>
            <div class="donut-wrap">
              <div id="donut-chart"></div>
              <div class="legend" id="donut-legend"></div>
            </div>
          </div>
        </div>

        <p class="run-status" id="run-status">Click a lead to preview its generated demo site.</p>

        <!-- recent leads -->
        <div class="card table-card">
          <div class="table-head">
            <h3>Recent Leads</h3>
            <button class="link" data-goto="leads">View all leads</button>
          </div>
          <div class="tscroll">
            <table>
              <thead><tr><th>#</th><th>Name</th><th>Niche</th><th>Status</th><th>Town</th><th>Value</th><th></th></tr></thead>
              <tbody id="recent-tbody"><tr><td colspan="7" class="empty">Loading…</td></tr></tbody>
            </table>
          </div>
        </div>

        <!-- bottom banner -->
        <div class="banner">
          <div class="bico">🎯</div>
          <div class="btxt">
            <h4>Turn hot leads into revenue</h4>
            <p>Approve a demo and its outreach draft, then send it yourself. Nothing here ever auto-sends.</p>
          </div>
          <button class="btn" id="banner-run">Run Pipeline</button>
        </div>
      </section>

      <!-- ===== LEADS PAGE ===== -->
      <section id="page-leads" class="subpage">
        <div class="card table-card">
          <div class="table-head"><h3>All Leads</h3></div>
          <div class="tscroll">
            <table>
              <thead><tr><th>#</th><th>Name</th><th>Niche</th><th>Status</th><th>Town</th><th>Value</th><th></th></tr></thead>
              <tbody id="all-tbody"><tr><td colspan="7" class="empty">Loading…</td></tr></tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- ===== DEMOS PAGE ===== -->
      <section id="page-demos" class="subpage">
        <div class="card panel"><div class="panel-head"><h3>Demos</h3></div><div id="demos-list" class="muted">Loading…</div></div>
      </section>

      <!-- ===== OUTREACH PAGE ===== -->
      <section id="page-outreach" class="subpage">
        <div class="card panel">
          <div class="panel-head"><h3>Outreach Drafts</h3></div>
          <p class="muted">Drafts only — approving here just logs the approval. Sending is a separate, deliberate step outside this dashboard.</p>
          <div id="outreach-list" class="muted">Loading…</div>
        </div>
      </section>
    </main>
  </div>

  <!-- demo preview modal -->
  <div id="modal">
    <div class="modal-card">
      <div class="modal-head"><h3 id="modal-title">Demo preview</h3><button class="kebab" id="modal-close" style="font-size:1.4rem;">✕</button></div>
      <div class="modal-body">
        <div class="device-toggle">
          <button data-device="Desktop" class="active">Desktop</button>
          <button data-device="Tablet">Tablet</button>
          <button data-device="Mobile">Mobile</button>
        </div>
        <div class="preview-frame-wrap">
          <iframe id="demo-preview" title="Demo site preview"></iframe>
        </div>
      </div>
    </div>
  </div>

  <!-- chat -->
  <button id="chat-toggle" title="Ask the Obsidian Labs assistant">💬</button>
  <div id="chat-panel">
    <div id="chat-header">Obsidian Labs Assistant</div>
    <div id="chat-messages"></div>
    <div id="chat-input-row">
      <input id="chat-input" type="text" placeholder="Ask about your pipeline…" />
      <button id="chat-send">Send</button>
    </div>
  </div>

  <script>
    /* =================================================================
       Config
       ================================================================= */
    function getApiBase() { return localStorage.getItem("obsidian_api_base") || "http://localhost:8502"; }
    function setApiBase(url) { localStorage.setItem("obsidian_api_base", url.replace(/\/$/, "")); }
    function getRevPer() { return Number(localStorage.getItem("obsidian_rev_per")) || 2500; }
    function setRevPer(v) { localStorage.setItem("obsidian_rev_per", String(v)); }

    let API_BASE = getApiBase();
    let leadsCache = [];
    let currentSlug = null;
    let currentDevice = "Desktop";
    let currentDemoHtml = "";

    const NICHE_COLORS = ["#7c3aed", "#3b82f6", "#14b8a6", "#f59e0b", "#ec4899", "#94a3b8"];

    /* ---------- helpers ---------- */
    function money(n) { return "$" + Math.round(n).toLocaleString("en-US"); }
    function slugify(name) { return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "lead"; }
    function isHot(l) { return String(l.is_hot_lead).toLowerCase() === "true"; }
    function initials(name) { return (name || "?").split(/\s+/).slice(0, 2).map(w => w[0] || "").join("").toUpperCase() || "?"; }
    function hashColor(s) { let h = 0; for (let i = 0; i < s.length; i++) h = s.charCodeAt(i) + ((h << 5) - h); return `hsl(${Math.abs(h) % 360} 55% 55%)`; }
    function statusPill(l) {
      const s = l.status, perf = Number(l.perf_score) || 0;
      if (s === "no_website") return ["No Website", "pill-bad"];
      if (s === "unreachable") return ["Unreachable", "pill-bad"];
      if (s === "api_error") return ["Grade Error", "pill-gray"];
      if (isHot(l)) return ["Hot", "pill-new"];
      if (perf <= 50) return ["Needs Work", "pill-warn"];
      return ["Healthy", "pill-good"];
    }

    /* ---------- API (same endpoints as v1/v2) ---------- */
    async function apiGet(path) {
      const res = await fetch(API_BASE + path);
      if (!res.ok) throw new Error(`${path} -> ${res.status}`);
      return res.json();
    }
    async function apiPost(path, body) {
      const res = await fetch(API_BASE + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}) });
      if (!res.ok) throw new Error(`${path} -> ${res.status}`);
      return res.json();
    }

    /* ---------- history (real, accumulates in localStorage) ---------- */
    function getHistory() { try { return JSON.parse(localStorage.getItem("obsidian_history") || "[]"); } catch (e) { return []; } }
    function pushHistory(s) {
      const h = getHistory();
      const last = h[h.length - 1];
      const snap = { t: Date.now(), leads: s.leads, hot: s.hot_leads, demos: s.demos, drafts: s.outreach_drafts };
      // only append if something changed or >1h since last, to avoid spam
      if (!last || last.leads !== snap.leads || last.hot !== snap.hot || last.demos !== snap.demos || last.drafts !== snap.drafts || (snap.t - last.t) > 3600000) {
        h.push(snap); while (h.length > 40) h.shift();
        localStorage.setItem("obsidian_history", JSON.stringify(h));
      }
      return h;
    }

    /* ================= SVG chart helpers ================= */
    function smoothPath(pts) {
      if (pts.length < 2) return pts.length ? `M${pts[0].x},${pts[0].y}` : "";
      let d = `M${pts[0].x},${pts[0].y}`;
      for (let i = 0; i < pts.length - 1; i++) {
        const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
        const c1x = p1.x + (p2.x - p0.x) / 6, c1y = p1.y + (p2.y - p0.y) / 6;
        const c2x = p2.x - (p3.x - p1.x) / 6, c2y = p2.y - (p3.y - p1.y) / 6;
        d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x},${p2.y}`;
      }
      return d;
    }
    function drawSpark(elId, values, color) {
      const el = document.getElementById(elId);
      if (!values || values.length < 2) { el.innerHTML = `<svg viewBox="0 0 100 34" preserveAspectRatio="none"></svg>`; return; }
      const W = 100, H = 34, min = Math.min(...values), max = Math.max(...values), rng = (max - min) || 1;
      const pts = values.map((v, i) => ({ x: (i / (values.length - 1)) * W, y: H - 3 - ((v - min) / rng) * (H - 8) }));
      const line = smoothPath(pts);
      const gid = "g_" + elId;
      el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        <defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stop-color="${color}" stop-opacity=".25"/><stop offset="1" stop-color="${color}" stop-opacity="0"/>
        </linearGradient></defs>
        <path d="${line} L${W},${H} L0,${H} Z" fill="url(#${gid})"/>
        <path d="${line}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`;
    }
    function niceMax(v) { if (v <= 5) return 5; const p = Math.pow(10, Math.floor(Math.log10(v))); const f = v / p; const n = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10; return n * p; }
    function drawArea(elId, hist, count) {
      const el = document.getElementById(elId);
      const data = hist.slice(-count);
      if (data.length < 2) { el.innerHTML = `<div class="empty" style="padding:2.5rem 0;text-align:center;">Growth appears here as the dashboard records snapshots over time.<br>Run the pipeline a few times to fill it in.</div>`; return; }
      const W = 580, H = 240, padL = 34, padR = 12, padT = 16, padB = 26;
      const leads = data.map(d => d.leads), hot = data.map(d => d.hot);
      const maxY = niceMax(Math.max(...leads, 1));
      const xAt = i => padL + (i / (data.length - 1)) * (W - padL - padR);
      const yAt = v => padT + (1 - v / maxY) * (H - padT - padB);
      const mk = arr => arr.map((v, i) => ({ x: xAt(i), y: yAt(v) }));
      const lp = smoothPath(mk(leads)), hp = smoothPath(mk(hot));
      const base = H - padB;
      const grid = [0, .25, .5, .75, 1].map(f => { const y = padT + f * (H - padT - padB); const val = Math.round(maxY * (1 - f)); return `<line x1="${padL}" x2="${W - padR}" y1="${y}" y2="${y}" stroke="#eef0f3"/><text x="${padL - 6}" y="${y + 3}" text-anchor="end" font-size="10" fill="#9ca3af">${val}</text>`; }).join("");
      const step = Math.max(1, Math.ceil(data.length / 6));
      const xlabels = data.map((d, i) => (i % step === 0 || i === data.length - 1) ? `<text x="${xAt(i)}" y="${H - 6}" text-anchor="middle" font-size="10" fill="#9ca3af">${d.label || (i + 1)}</text>` : "").join("");
      const lastX = xAt(data.length - 1), lastY = yAt(leads[leads.length - 1]);
      el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
        <defs><linearGradient id="areaGrad" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#7c3aed" stop-opacity=".28"/><stop offset="1" stop-color="#7c3aed" stop-opacity="0"/></linearGradient></defs>
        ${grid}
        <path d="${lp} L${lastX},${base} L${padL},${base} Z" fill="url(#areaGrad)"/>
        <path d="${hp}" fill="none" stroke="#c4b5fd" stroke-width="2.5" stroke-linecap="round"/>
        <path d="${lp}" fill="none" stroke="#7c3aed" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="${lastX}" cy="${lastY}" r="5" fill="#7c3aed" stroke="#fff" stroke-width="2"/>
        <g><rect x="${Math.min(lastX - 26, W - 58)}" y="${Math.max(lastY - 34, 2)}" width="52" height="22" rx="6" fill="#fff" stroke="#e5e7eb"/><text x="${Math.min(lastX, W - 32)}" y="${Math.max(lastY - 19, 17)}" text-anchor="middle" font-size="11" font-weight="700" fill="#111827">${leads[leads.length - 1]}</text></g>
        ${xlabels}
      </svg>`;
    }
    function drawDonut(elId, legendId, segments) {
      const el = document.getElementById(elId), leg = document.getElementById(legendId);
      const total = segments.reduce((a, s) => a + s.value, 0);
      const R = 70, SW = 22, C = 2 * Math.PI * R, cx = 90, cy = 90;
      if (!total) { el.innerHTML = `<svg width="180" height="180"><circle cx="90" cy="90" r="${R}" fill="none" stroke="#eef0f3" stroke-width="${SW}"/></svg>`; leg.innerHTML = `<div class="empty">No leads yet.</div>`; return; }
      let off = 0;
      const arcs = segments.map(s => {
        const len = (s.value / total) * C;
        const seg = `<circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${s.color}" stroke-width="${SW}" stroke-dasharray="${len.toFixed(2)} ${(C - len).toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"/>`;
        off += len; return seg;
      }).join("");
      el.innerHTML = `<svg width="180" height="180" viewBox="0 0 180 180">${arcs}
        <text x="90" y="86" text-anchor="middle" font-size="26" font-weight="750" fill="#111827">${total}</text>
        <text x="90" y="106" text-anchor="middle" font-size="12" fill="#9ca3af">Total</text></svg>`;
      leg.innerHTML = segments.map(s => {
        const pct = Math.round((s.value / total) * 100);
        return `<div class="legend-row"><span class="lname"><span class="swatch" style="background:${s.color}"></span>${s.label}</span><span class="lpct">${pct}%</span><span class="lval"><span class="swatch" style="background:${s.color}"></span>${s.value}</span></div>`;
      }).join("");
    }

    /* ================= data rendering ================= */
    function setDelta(elId, hist, key) {
      const el = document.getElementById(elId);
      if (hist.length < 2) { el.className = "kdelta flat"; el.textContent = "—"; return; }
      const prev = hist[hist.length - 2][key], now = hist[hist.length - 1][key];
      if (!prev) { el.className = "kdelta flat"; el.textContent = now ? "▲ new" : "—"; return; }
      const pct = ((now - prev) / prev) * 100, up = pct >= 0;
      el.className = "kdelta " + (Math.abs(pct) < 0.1 ? "flat" : up ? "up" : "down");
      el.textContent = `${up ? "▲" : "▼"} ${Math.abs(pct).toFixed(1)}% vs last run`;
    }
    async function loadStatus() {
      try {
        const s = await apiGet("/api/status");
        document.getElementById("k-leads").textContent = s.leads;
        document.getElementById("k-hot").textContent = s.hot_leads;
        document.getElementById("k-demos").textContent = s.demos;
        document.getElementById("k-drafts").textContent = s.outreach_drafts;
        const h = pushHistory(s);
        drawSpark("s-leads", h.map(x => x.leads), "#7c3aed");
        drawSpark("s-hot", h.map(x => x.hot), "#3b82f6");
        drawSpark("s-demos", h.map(x => x.demos), "#14b8a6");
        drawSpark("s-drafts", h.map(x => x.drafts), "#f59e0b");
        setDelta("d-leads", h, "leads"); setDelta("d-hot", h, "hot"); setDelta("d-demos", h, "demos"); setDelta("d-drafts", h, "drafts");
        drawArea("area-chart", h, Number(document.getElementById("growth-range").value));
      } catch (e) {
        document.getElementById("run-status").textContent = "Backend unreachable — is fastapi_backend running on :8502?";
      }
    }
    async function loadLeads() {
      try { leadsCache = await apiGet("/api/leads"); } catch (e) { leadsCache = []; }
      renderDonut();
      renderTable("recent-tbody", leadsCache.slice(0, 6));
      renderTable("all-tbody", leadsCache);
    }
    function renderDonut() {
      const counts = {};
      leadsCache.forEach(l => { const k = (l.type || "other").trim() || "other"; counts[k] = (counts[k] || 0) + 1; });
      const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
      const top = entries.slice(0, 5);
      const restVal = entries.slice(5).reduce((a, e) => a + e[1], 0);
      const segs = top.map((e, i) => ({ label: e[0].replace(/\b\w/g, c => c.toUpperCase()), value: e[1], color: NICHE_COLORS[i] }));
      if (restVal) segs.push({ label: "Other", value: restVal, color: NICHE_COLORS[5] });
      drawDonut("donut-chart", "donut-legend", segs);
    }
    function rowHTML(l, i) {
      const [label, cls] = statusPill(l);
      const val = isHot(l) ? money(getRevPer()) : "—";
      return `<tr data-slug="${slugify(l.name)}">
        <td>${i + 1}</td>
        <td><div class="cell-name"><span class="avatar" style="background:${hashColor(l.name || "")}">${initials(l.name)}</span><span class="nm">${l.name || ""}</span></div></td>
        <td>${(l.type || "").replace(/\b\w/g, c => c.toUpperCase())}</td>
        <td><span class="pill ${cls}">${label}</span></td>
        <td>${l.town || "—"}</td>
        <td class="val">${val}</td>
        <td><button class="kebab" title="Preview demo">⋮</button></td>
      </tr>`;
    }
    function renderTable(tbodyId, rows) {
      const tb = document.getElementById(tbodyId);
      if (!rows.length) { tb.innerHTML = `<tr><td colspan="7" class="empty">No leads yet. Run the pipeline to gather some.</td></tr>`; return; }
      tb.innerHTML = rows.map((l, i) => rowHTML(l, i)).join("");
      tb.querySelectorAll("tr[data-slug]").forEach(tr => tr.addEventListener("click", () => openDemo(tr.dataset.slug)));
    }

    /* ---------- demo modal ---------- */
    async function openDemo(slug) {
      currentSlug = slug;
      document.getElementById("modal-title").textContent = slug;
      document.getElementById("modal").classList.add("open");
      const iframe = document.getElementById("demo-preview");
      iframe.srcdoc = `<p style="font-family:system-ui;color:#999;padding:2rem;">Loading…</p>`;
      try { const demo = await apiGet(`/api/demos/${slug}`); currentDemoHtml = demo.html; renderPreview(); }
      catch (e) { currentDemoHtml = ""; iframe.srcdoc = `<p style="font-family:system-ui;color:#999;padding:2rem;">No demo generated yet for “${slug}”. Run the pipeline to build one.</p>`; }
    }
    function renderPreview() {
      const widths = { Desktop: "100%", Tablet: "768px", Mobile: "390px" };
      const iframe = document.getElementById("demo-preview");
      iframe.style.width = widths[currentDevice]; iframe.style.margin = currentDevice === "Desktop" ? "0" : "0 auto";
      if (currentDemoHtml) iframe.srcdoc = currentDemoHtml;
    }
    document.querySelectorAll(".device-toggle button").forEach(b => b.addEventListener("click", () => {
      document.querySelectorAll(".device-toggle button").forEach(x => x.classList.remove("active"));
      b.classList.add("active"); currentDevice = b.dataset.device; renderPreview();
    }));
    document.getElementById("modal-close").addEventListener("click", () => document.getElementById("modal").classList.remove("open"));
    document.getElementById("modal").addEventListener("click", e => { if (e.target.id === "modal") document.getElementById("modal").classList.remove("open"); });

    /* ---------- demos + outreach pages ---------- */
    async function loadDemos() {
      const el = document.getElementById("demos-list");
      try { const d = await apiGet("/api/demos"); el.innerHTML = d.length ? d.map(x => `<div class="legend-row" style="grid-template-columns:1fr auto;padding:.6rem 0;border-bottom:1px solid var(--border);cursor:pointer" data-slug="${x.slug}"><strong>${x.slug}</strong><button class="btn small secondary">Preview</button></div>`).join("") : `<div class="empty">No demos generated yet.</div>`; el.querySelectorAll("[data-slug]").forEach(r => r.addEventListener("click", () => openDemo(r.dataset.slug))); }
      catch (e) { el.innerHTML = `<div class="empty">Backend unreachable.</div>`; }
    }
    async function loadOutreach() {
      const el = document.getElementById("outreach-list");
      try {
        const drafts = await apiGet("/api/outreach");
        if (!drafts.length) { el.innerHTML = `<div class="empty">No outreach drafts yet.</div>`; return; }
        let html = "";
        for (const d of drafts) { const full = await apiGet(`/api/outreach/${d.slug}`); html += `<div class="card panel" style="margin-bottom:.8rem"><strong>${d.slug}</strong><pre style="white-space:pre-wrap;font-family:inherit;font-size:.85rem;color:#374151;line-height:1.5;margin:.6rem 0 .8rem">${full.content.replace(/</g, "&lt;")}</pre><button class="btn small" data-approve="${d.slug}">Approve</button></div>`; }
        el.innerHTML = html;
        el.querySelectorAll("[data-approve]").forEach(b => b.addEventListener("click", async () => { await apiPost("/api/approve", { kind: "outreach_approved", identifier: b.dataset.approve }); b.textContent = "Approved ✓"; b.disabled = true; }));
      } catch (e) { el.innerHTML = `<div class="empty">Backend unreachable.</div>`; }
    }

    /* ---------- navigation ---------- */
    function goToPage(page) {
      document.querySelectorAll("#nav button[data-page]").forEach(b => b.classList.toggle("active", b.dataset.page === page));
      ["dashboard", "leads", "demos", "outreach"].forEach(p => { document.getElementById(`page-${p}`).style.display = p === page ? "" : "none"; });
      if (page === "demos") loadDemos();
      if (page === "outreach") loadOutreach();
    }
    document.querySelectorAll("#nav button[data-page]").forEach(b => b.addEventListener("click", () => goToPage(b.dataset.page)));
    document.querySelectorAll("[data-goto]").forEach(b => b.addEventListener("click", () => goToPage(b.dataset.goto)));
    document.getElementById("growth-range").addEventListener("change", () => drawArea("area-chart", getHistory(), Number(document.getElementById("growth-range").value)));

    /* ---------- run pipeline ---------- */
    async function runPipeline() {
      const st = document.getElementById("run-status"); st.textContent = "Starting pipeline in the background…";
      try { await apiPost("/api/run-pipeline", { stage: "all", towns: ["Mahopac", "Carmel"], niches: ["dentist", "roofer"], limit: 5 }); st.textContent = "Pipeline started. Check output/logs/pipeline_run.log, or refresh shortly."; }
      catch (e) { st.textContent = "Failed to start — is the backend running?"; }
    }
    document.getElementById("promo-run").addEventListener("click", runPipeline);
    document.getElementById("banner-run").addEventListener("click", runPipeline);

    /* ---------- settings (backend URL + price per deal) ---------- */
    function openSettings() {
      const next = prompt("Backend URL (fastapi_backend address — e.g. https://xxxx.ngrok-free.app or http://localhost:8502):", getApiBase());
      if (next && next.trim()) { setApiBase(next.trim()); API_BASE = getApiBase(); refreshAll(); }
    }
    document.getElementById("settings-btn").addEventListener("click", openSettings);
    document.getElementById("nav-settings").addEventListener("click", openSettings);
    document.getElementById("range-chip").addEventListener("click", () => {
      const cur = getRevPer(); const n = Number((prompt("Average price per closed deal (used for the Value column):", cur) || "").replace(/[^0-9.]/g, ""));
      if (n > 0) { setRevPer(n); renderTable("recent-tbody", leadsCache.slice(0, 6)); renderTable("all-tbody", leadsCache); }
    });

    /* ---------- chat ---------- */
    const chatPanel = document.getElementById("chat-panel"), chatMessages = document.getElementById("chat-messages"), chatInput = document.getElementById("chat-input");
    document.getElementById("chat-toggle").addEventListener("click", () => chatPanel.classList.toggle("open"));
    function addChatMsg(t, who) { const d = document.createElement("div"); d.className = `chat-msg ${who}`; d.textContent = t; chatMessages.appendChild(d); chatMessages.scrollTop = chatMessages.scrollHeight; }
    async function sendChat() {
      const msg = chatInput.value.trim(); if (!msg) return;
      addChatMsg(msg, "user"); chatInput.value = ""; addChatMsg("Thinking…", "bot");
      try { const res = await apiPost("/api/chat", { message: msg }); chatMessages.lastChild.textContent = res.reply || "(no response)"; }
      catch (e) { chatMessages.lastChild.textContent = "Couldn't reach the assistant — is fastapi_backend + Ollama running?"; }
    }
    document.getElementById("chat-send").addEventListener("click", sendChat);
    chatInput.addEventListener("keydown", e => { if (e.key === "Enter") sendChat(); });

    /* ---------- PWA + boot ---------- */
    if ("serviceWorker" in navigator) window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
    function refreshAll() { loadStatus(); loadLeads(); }
    addChatMsg("Hi! I'm your pipeline assistant. Ask about your hot leads, drafts, or pricing.", "bot");
    refreshAll();
    setInterval(loadStatus, 15000);
  </script>
</body>
</html>

```

## `tesla_style_dashboard_v2.html`  
_(686 lines)_

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Obsidian Labs — Mission Control</title>
  <link rel="manifest" href="manifest.json" />
  <link rel="icon" href="icon-192.png" />
  <link rel="apple-touch-icon" href="icon-192.png" />
  <meta name="theme-color" content="#0b0b0b" />
  <style>
    /* ============================================================
       Obsidian Labs v2 — dark, Tesla/Apple-inspired glassmorphism.
       Single self-contained file. Talks to the SAME fastapi_backend
       on :8502 — no backend changes. Deliberately dark, single-world.
       ============================================================ */
    :root {
      --bg: #0b0b0b;
      --panel: rgba(255,255,255,.045);
      --panel-hover: rgba(255,255,255,.07);
      --border: rgba(255,255,255,.09);
      --border-strong: rgba(255,255,255,.16);
      --accent: #3b82f6;
      --accent-soft: rgba(59,130,246,.16);
      --accent-glow: rgba(59,130,246,.45);
      --text: #f5f5f7;
      --muted: #99a1af;      /* blue-biased neutral, chosen not defaulted */
      --faint: #6b7280;
      --good: #22c55e;
      --warn: #f59e0b;
      --bad:  #ef4444;
      --gray: #6b7280;
      --radius: 18px;
      --radius-sm: 12px;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      color: var(--text);
      background: radial-gradient(1200px 700px at 50% -15%, #16181d 0%, #0b0b0b 45%, #000 100%);
      background-attachment: fixed;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
      -webkit-font-smoothing: antialiased;
      letter-spacing: -0.01em;
    }
    a { color: inherit; }
    .wrap { max-width: 1360px; margin: 0 auto; padding: 1.1rem 1.5rem 5rem; }

    /* ---------- header ---------- */
    .topbar {
      display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
      padding: 0.4rem 0 1.2rem;
    }
    .brand { display: flex; align-items: center; gap: 0.6rem; font-weight: 650; font-size: 1.05rem; }
    .brand .mark {
      width: 26px; height: 26px; border-radius: 8px;
      background: linear-gradient(150deg, var(--accent), #1e40af);
      box-shadow: 0 0 18px var(--accent-glow);
      display: grid; place-items: center;
    }
    .brand .mark::after { content: ""; width: 9px; height: 9px; background: #fff; border-radius: 2px; }
    .navtabs { display: flex; gap: 0.2rem; background: var(--panel); border: 1px solid var(--border);
      border-radius: 9999px; padding: 4px; }
    .navtabs button {
      background: none; border: none; color: var(--muted); font-weight: 550; font-size: 0.86rem;
      padding: 0.42rem 0.95rem; border-radius: 9999px; cursor: pointer; transition: all .18s;
    }
    .navtabs button:hover { color: var(--text); }
    .navtabs button.active { background: var(--text); color: #0b0b0b; }
    .spacer { flex: 1; }
    .ghost-btn {
      display: inline-flex; align-items: center; gap: 0.5rem;
      background: var(--panel); border: 1px solid var(--border); color: var(--muted);
      border-radius: 10px; padding: 0.42rem 0.7rem; font-size: 0.8rem; cursor: pointer; transition: all .18s;
    }
    .ghost-btn:hover { color: var(--text); border-color: var(--border-strong); background: var(--panel-hover); }
    kbd {
      font-family: inherit; font-size: 0.72rem; background: rgba(255,255,255,.08);
      border: 1px solid var(--border); border-radius: 5px; padding: 1px 6px;
    }

    /* ---------- glass card ---------- */
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      backdrop-filter: blur(18px) saturate(120%);
      -webkit-backdrop-filter: blur(18px) saturate(120%);
      box-shadow: 0 1px 0 rgba(255,255,255,.04) inset, 0 12px 40px rgba(0,0,0,.35);
    }
    .card.pad { padding: 1.35rem 1.4rem; }
    .card h2 { margin: 0 0 1rem; font-size: 1rem; font-weight: 600; letter-spacing: -0.02em; }

    /* ---------- hero: ring + KPIs ---------- */
    .hero { display: grid; grid-template-columns: 300px 1fr; gap: 1.2rem; margin-bottom: 1.2rem; }
    .ring-card { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.9rem; text-align: center; }
    .ring {
      position: relative; width: 168px; height: 168px; border-radius: 50%;
      display: grid; place-items: center;
      border: 8px solid var(--accent-soft);
      box-shadow: 0 0 30px var(--accent-glow), inset 0 0 26px rgba(59,130,246,.12);
      animation: pulse 2.6s infinite ease-in-out;
    }
    .ring.offline { border-color: rgba(239,68,68,.18); box-shadow: 0 0 26px rgba(239,68,68,.4), inset 0 0 24px rgba(239,68,68,.1); animation: none; }
    .ring .ring-num { font-size: 2.5rem; font-weight: 700; line-height: 1; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; }
    .ring .ring-lbl { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.14em; margin-top: 4px; }
    .ring-status { font-size: 0.82rem; color: var(--muted); display: inline-flex; align-items: center; gap: 0.45rem; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--good); box-shadow: 0 0 8px var(--good); }
    .dot.bad { background: var(--bad); box-shadow: 0 0 8px var(--bad); }
    @keyframes pulse { 50% { box-shadow: 0 0 52px var(--accent-glow), inset 0 0 26px rgba(59,130,246,.2); } }
    @media (prefers-reduced-motion: reduce) { .ring { animation: none; } }

    .kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
    .kpi { padding: 1.15rem 1.2rem; cursor: default; }
    .kpi .label { font-size: 0.76rem; color: var(--muted); letter-spacing: 0.02em; }
    .kpi .value { font-size: 1.95rem; font-weight: 700; letter-spacing: -0.03em; margin-top: 0.35rem; font-variant-numeric: tabular-nums; }
    .kpi .sub { font-size: 0.74rem; color: var(--faint); margin-top: 0.3rem; }
    .kpi.revenue { grid-column: span 1; cursor: pointer; position: relative; }
    .kpi.revenue .value { color: var(--accent); }
    .kpi.revenue:hover { border-color: var(--border-strong); }
    .kpi.accent { background: linear-gradient(160deg, rgba(59,130,246,.12), rgba(59,130,246,.02)); }

    /* ---------- buttons ---------- */
    .btn {
      border: none; border-radius: 11px; padding: 0.62rem 1.3rem; font-weight: 600; font-size: 0.88rem;
      cursor: pointer; transition: all .16s; font-family: inherit;
      background: var(--accent); color: #fff; box-shadow: 0 6px 20px rgba(59,130,246,.35);
    }
    .btn:hover { filter: brightness(1.08); transform: translateY(-1px); }
    .btn.secondary { background: var(--panel); color: var(--text); border: 1px solid var(--border); box-shadow: none; }
    .btn.secondary:hover { background: var(--panel-hover); border-color: var(--border-strong); }
    .btn:disabled { opacity: .4; cursor: not-allowed; transform: none; filter: none; }
    .btn.small { padding: 0.4rem 0.9rem; font-size: 0.8rem; }

    .actionrow { display: flex; align-items: center; gap: 0.7rem; flex-wrap: wrap; margin-bottom: 1.2rem; }
    .run-status { color: var(--muted); font-size: 0.83rem; margin: 0 0 0 0.2rem; }

    /* ---------- main grid ---------- */
    .two-col { display: grid; grid-template-columns: 1.05fr 1.35fr; gap: 1.2rem; }

    /* lead cards */
    .lead-list { display: flex; flex-direction: column; gap: 0.6rem; }
    .lead-item {
      display: grid; grid-template-columns: 1fr auto; gap: 0.4rem 0.8rem; align-items: center;
      padding: 0.8rem 0.95rem; border-radius: var(--radius-sm);
      border: 1px solid var(--border); background: rgba(255,255,255,.02); cursor: pointer; transition: all .16s;
    }
    .lead-item:hover { background: var(--panel-hover); border-color: var(--border-strong); transform: translateX(2px); }
    .lead-item.selected { border-color: var(--accent); background: var(--accent-soft); }
    .lead-name { font-weight: 600; font-size: 0.92rem; }
    .lead-meta { font-size: 0.76rem; color: var(--muted); margin-top: 2px; }
    .lead-right { display: flex; align-items: center; gap: 0.6rem; }
    .score { font-variant-numeric: tabular-nums; font-weight: 600; font-size: 0.9rem; color: var(--muted); }
    .flame { font-size: 0.85rem; }

    .pill { display: inline-block; padding: 3px 10px; border-radius: 9999px; font-size: 0.72rem; font-weight: 600; border: 1px solid transparent; }
    .pill-red   { background: rgba(239,68,68,.15);  color: #fca5a5; border-color: rgba(239,68,68,.3); }
    .pill-amber { background: rgba(245,158,11,.15); color: #fcd34d; border-color: rgba(245,158,11,.3); }
    .pill-green { background: rgba(34,197,94,.15);  color: #86efac; border-color: rgba(34,197,94,.3); }
    .pill-gray  { background: rgba(107,114,128,.2); color: #cbd5e1; border-color: rgba(107,114,128,.35); }

    /* preview */
    .device-toggle { display: flex; gap: 0.4rem; margin-bottom: 0.85rem; }
    .device-toggle button {
      padding: 0.34rem 0.85rem; border-radius: 9999px; border: 1px solid var(--border);
      background: var(--panel); color: var(--muted); cursor: pointer; font-size: 0.78rem; transition: all .16s;
    }
    .device-toggle button.active { background: var(--text); color: #0b0b0b; border-color: var(--text); }
    .preview-frame-wrap { display: flex; justify-content: center; }
    iframe#demo-preview {
      border: 1px solid var(--border); border-radius: var(--radius-sm);
      width: 100%; height: 560px; background: #fff; transition: width .2s;
    }

    /* activity feed */
    .feed { display: flex; flex-direction: column; gap: 0.15rem; }
    .feed-item { display: flex; gap: 0.7rem; align-items: baseline; padding: 0.5rem 0; border-bottom: 1px solid var(--border); font-size: 0.85rem; }
    .feed-item:last-child { border-bottom: none; }
    .feed-time { color: var(--faint); font-size: 0.72rem; font-variant-numeric: tabular-nums; white-space: nowrap; min-width: 52px; }
    .feed-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); margin-top: 6px; flex: none; }

    .draft-card { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 1rem 1.1rem; margin-bottom: 0.75rem; background: rgba(255,255,255,.02); }
    .draft-card strong { font-size: 0.9rem; }
    .draft-card pre { white-space: pre-wrap; font-family: inherit; font-size: 0.83rem; color: #d7dae0; margin: 0.6rem 0 0.8rem; line-height: 1.5; }
    .muted { color: var(--muted); font-size: 0.85rem; }
    .empty { color: var(--faint); font-size: 0.86rem; padding: 0.6rem 0; }

    /* ---------- chat ---------- */
    #chat-toggle {
      position: fixed; bottom: 22px; right: 22px; width: 56px; height: 56px; border-radius: 50%;
      background: var(--accent); color: #fff; border: none; font-size: 1.35rem; cursor: pointer;
      box-shadow: 0 8px 28px var(--accent-glow); z-index: 60;
    }
    #chat-panel {
      position: fixed; bottom: 88px; right: 22px; width: 350px; max-height: 500px;
      background: rgba(20,22,27,.82); backdrop-filter: blur(24px) saturate(140%); -webkit-backdrop-filter: blur(24px) saturate(140%);
      border: 1px solid var(--border-strong); border-radius: var(--radius); z-index: 60;
      display: none; flex-direction: column; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,.55);
    }
    #chat-panel.open { display: flex; }
    #chat-header { padding: 0.8rem 1rem; font-weight: 600; font-size: 0.9rem; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 0.5rem; }
    #chat-messages { flex: 1; overflow-y: auto; padding: 0.85rem 1rem; display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.85rem; }
    .chat-msg { padding: 0.5rem 0.75rem; border-radius: 13px; max-width: 86%; line-height: 1.45; }
    .chat-msg.user { align-self: flex-end; background: var(--accent); color: #fff; }
    .chat-msg.bot { align-self: flex-start; background: rgba(255,255,255,.07); color: var(--text); }
    #chat-input-row { display: flex; border-top: 1px solid var(--border); }
    #chat-input { flex: 1; border: none; background: transparent; color: var(--text); padding: 0.8rem; font-size: 0.85rem; font-family: inherit; }
    #chat-input::placeholder { color: var(--faint); }
    #chat-send { border: none; background: var(--accent); color: #fff; padding: 0 1.1rem; cursor: pointer; font-family: inherit; }

    /* ---------- command palette ---------- */
    #palette-overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,.55); backdrop-filter: blur(3px);
      display: none; align-items: flex-start; justify-content: center; z-index: 80; padding-top: 12vh;
    }
    #palette-overlay.open { display: flex; }
    #palette {
      width: min(560px, 92vw); background: rgba(20,22,27,.92);
      backdrop-filter: blur(26px) saturate(140%); -webkit-backdrop-filter: blur(26px) saturate(140%);
      border: 1px solid var(--border-strong); border-radius: 16px; overflow: hidden; box-shadow: 0 30px 80px rgba(0,0,0,.6);
    }
    #palette-input { width: 100%; border: none; background: transparent; color: var(--text); font-size: 1rem; padding: 1rem 1.15rem; font-family: inherit; border-bottom: 1px solid var(--border); }
    #palette-input::placeholder { color: var(--faint); }
    #palette-list { list-style: none; margin: 0; padding: 0.4rem; max-height: 46vh; overflow-y: auto; }
    #palette-list li { display: flex; align-items: center; gap: 0.7rem; padding: 0.6rem 0.8rem; border-radius: 10px; cursor: pointer; font-size: 0.9rem; }
    #palette-list li .cmd-ico { width: 22px; text-align: center; opacity: .8; }
    #palette-list li .cmd-tag { margin-left: auto; font-size: 0.72rem; color: var(--faint); }
    #palette-list li.active, #palette-list li:hover { background: var(--accent-soft); }

    :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

    @media (max-width: 940px) {
      .hero { grid-template-columns: 1fr; }
      .two-col { grid-template-columns: 1fr; }
      .kpis { grid-template-columns: repeat(2, 1fr); }
    }
    @media (max-width: 560px) {
      .wrap { padding: 1rem 1rem 5rem; }
      .kpis { grid-template-columns: repeat(2, 1fr); }
      .navtabs { order: 3; width: 100%; justify-content: space-between; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <!-- header -->
    <div class="topbar">
      <div class="brand"><span class="mark"></span> Obsidian Labs</div>
      <div class="navtabs" role="tablist">
        <button data-page="dashboard" class="active">Mission Control</button>
        <button data-page="leads">Leads</button>
        <button data-page="demos">Demos</button>
        <button data-page="outreach">Outreach</button>
      </div>
      <div class="spacer"></div>
      <button class="ghost-btn" id="palette-btn" title="Command palette"><span>Search</span> <kbd>⌘K</kbd></button>
      <button class="ghost-btn" id="settings-btn" title="Set backend URL">⚙ Backend</button>
    </div>

    <!-- ===================== DASHBOARD PAGE ===================== -->
    <div id="page-dashboard">
      <!-- hero: AI status ring + KPI cards -->
      <div class="hero">
        <div class="card pad ring-card">
          <div class="ring" id="ring">
            <div>
              <div class="ring-num" id="ring-num">–</div>
              <div class="ring-lbl">Leads</div>
            </div>
          </div>
          <div class="ring-status" id="ring-status"><span class="dot" id="ring-dot"></span> Checking backend…</div>
        </div>

        <div class="kpis">
          <div class="card kpi"><div class="label">Leads</div><div class="value" id="m-leads">–</div><div class="sub">in the pipeline</div></div>
          <div class="card kpi"><div class="label">Hot leads</div><div class="value" id="m-hot">–</div><div class="sub">ready to pitch</div></div>
          <div class="card kpi"><div class="label">Demos generated</div><div class="value" id="m-demos">–</div><div class="sub">preview-ready sites</div></div>
          <div class="card kpi"><div class="label">Outreach drafts</div><div class="value" id="m-outreach">–</div><div class="sub">awaiting approval</div></div>
          <div class="card kpi revenue accent" id="revenue-card" title="Click to set your price-per-deal">
            <div class="label">Potential revenue</div><div class="value" id="m-revenue">–</div>
            <div class="sub" id="m-revenue-sub">hot leads × price</div>
          </div>
          <div class="card kpi"><div class="label">Guardrail</div><div class="value" style="font-size:1rem;line-height:1.35;font-weight:600;">100% local<br>Nothing auto-sends</div></div>
        </div>
      </div>

      <div class="actionrow">
        <button class="btn" id="run-pipeline-btn">▶ Run Pipeline</button>
        <button class="btn secondary" id="approve-btn" disabled>Approve &amp; Send</button>
        <span class="run-status" id="run-status">Select a lead to preview its generated demo.</span>
      </div>

      <div class="two-col">
        <div class="card pad">
          <h2>Leads</h2>
          <div class="lead-list" id="leads-list"><div class="empty">Loading…</div></div>
        </div>
        <div class="card pad">
          <h2>Demo preview</h2>
          <div class="device-toggle">
            <button data-device="Desktop" class="active">Desktop</button>
            <button data-device="Tablet">Tablet</button>
            <button data-device="Mobile">Mobile</button>
          </div>
          <div class="preview-frame-wrap">
            <iframe id="demo-preview" title="Demo site preview" srcdoc="<p style='font-family:system-ui;color:#999;padding:2rem;'>Select a lead to preview its demo.</p>"></iframe>
          </div>
        </div>
      </div>

      <!-- live activity feed -->
      <div class="card pad" style="margin-top:1.2rem;">
        <h2>Live activity</h2>
        <div class="feed" id="feed"></div>
      </div>
    </div>

    <!-- ===================== LEADS PAGE ===================== -->
    <div id="page-leads" style="display:none;">
      <div class="card pad">
        <h2>All leads</h2>
        <div class="lead-list" id="leads-full-list"><div class="empty">Loading…</div></div>
      </div>
    </div>

    <!-- ===================== DEMOS PAGE ===================== -->
    <div id="page-demos" style="display:none;">
      <div class="card pad">
        <h2>Demos</h2>
        <div id="demos-list" class="muted">Loading…</div>
      </div>
    </div>

    <!-- ===================== OUTREACH PAGE ===================== -->
    <div id="page-outreach" style="display:none;">
      <div class="card pad">
        <h2>Outreach drafts</h2>
        <p class="muted" style="margin-top:-0.4rem;">Drafts only — approving here just logs the approval. Sending is a separate, deliberate step outside this dashboard.</p>
        <div id="outreach-list" class="muted">Loading…</div>
      </div>
    </div>
  </div>

  <!-- chat -->
  <button id="chat-toggle" title="Ask the Obsidian Labs assistant">💬</button>
  <div id="chat-panel">
    <div id="chat-header"><span class="dot"></span> Obsidian Labs Assistant</div>
    <div id="chat-messages"></div>
    <div id="chat-input-row">
      <input id="chat-input" type="text" placeholder="Ask about your pipeline…" />
      <button id="chat-send">Send</button>
    </div>
  </div>

  <!-- command palette -->
  <div id="palette-overlay">
    <div id="palette" role="dialog" aria-label="Command palette">
      <input id="palette-input" type="text" placeholder="Search leads, jump to a section, run an action…" autocomplete="off" />
      <ul id="palette-list"></ul>
    </div>
  </div>

  <script>
    /* ===================================================================
       Config — backend URL + price-per-deal, both remembered per device.
       =================================================================== */
    function getApiBase() { return localStorage.getItem("obsidian_api_base") || "http://localhost:8502"; }
    function setApiBase(url) { localStorage.setItem("obsidian_api_base", url.replace(/\/$/, "")); }
    function getRevPer() { return Number(localStorage.getItem("obsidian_rev_per")) || 2500; }
    function setRevPer(v) { localStorage.setItem("obsidian_rev_per", String(v)); }

    let API_BASE = getApiBase();
    let currentDevice = "Desktop";
    let currentSlug = null;
    let leadsCache = [];
    let lastStatus = null;

    /* ---------- tiny helpers ---------- */
    function money(n) { return "$" + Math.round(n).toLocaleString("en-US"); }
    function slugify(name) { return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "lead"; }
    function pillFor(status, perf) {
      perf = Number(perf) || 0;
      if (status === "no_website") return ["No Website", "pill-red"];
      if (status === "unreachable") return ["Unreachable", "pill-red"];
      if (status === "api_error") return ["Grade Error", "pill-gray"];
      if (perf <= 50) return ["Needs Work", "pill-amber"];
      return ["Healthy", "pill-green"];
    }
    function isHot(l) { return String(l.is_hot_lead).toLowerCase() === "true"; }

    /* ---------- API layer (same endpoints as v1) ---------- */
    async function apiGet(path) {
      const res = await fetch(API_BASE + path);
      if (!res.ok) throw new Error(`${path} -> ${res.status}`);
      return res.json();
    }
    async function apiPost(path, body) {
      const res = await fetch(API_BASE + path, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      if (!res.ok) throw new Error(`${path} -> ${res.status}`);
      return res.json();
    }

    /* ---------- activity feed ---------- */
    const activity = [];
    function pushActivity(text) {
      const d = new Date();
      const t = d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
      activity.unshift({ t, text });
      if (activity.length > 12) activity.pop();
      renderFeed();
    }
    function renderFeed() {
      const el = document.getElementById("feed");
      if (!activity.length) { el.innerHTML = `<div class="empty">No activity yet — run the pipeline to get started.</div>`; return; }
      el.innerHTML = activity.map(a =>
        `<div class="feed-item"><span class="feed-time">${a.t}</span><span class="feed-dot"></span><span>${a.text}</span></div>`
      ).join("");
    }

    /* ---------- status: KPIs, ring, revenue ---------- */
    function setRing(online, leads) {
      const ring = document.getElementById("ring");
      const dot = document.getElementById("ring-dot");
      const st = document.getElementById("ring-status");
      document.getElementById("ring-num").textContent = online ? leads : "–";
      ring.classList.toggle("offline", !online);
      dot.classList.toggle("bad", !online);
      st.innerHTML = online
        ? `<span class="dot" id="ring-dot"></span> Pipeline online`
        : `<span class="dot bad" id="ring-dot"></span> Backend offline`;
    }
    function renderRevenue(hot) {
      const per = getRevPer();
      document.getElementById("m-revenue").textContent = money(hot * per);
      document.getElementById("m-revenue-sub").textContent = `${hot} hot × ${money(per)}`;
    }
    async function loadStatus() {
      try {
        const s = await apiGet("/api/status");
        lastStatus = s;
        document.getElementById("m-leads").textContent = s.leads;
        document.getElementById("m-hot").textContent = s.hot_leads;
        document.getElementById("m-demos").textContent = s.demos;
        document.getElementById("m-outreach").textContent = s.outreach_drafts;
        renderRevenue(s.hot_leads);
        setRing(true, s.leads);
      } catch (e) {
        setRing(false, 0);
      }
    }

    /* ---------- leads ---------- */
    async function loadLeads() {
      try { leadsCache = await apiGet("/api/leads"); pushActivity(`Loaded ${leadsCache.length} lead${leadsCache.length === 1 ? "" : "s"}.`); }
      catch (e) { leadsCache = []; }
      renderLeadList("leads-list", true);
      renderLeadList("leads-full-list", false);
    }
    function leadItemHTML(l, compact) {
      const [label, cls] = pillFor(l.status, l.perf_score);
      const hot = isHot(l);
      const sel = slugify(l.name) === currentSlug ? " selected" : "";
      const meta = compact
        ? `${l.type || ""}${l.town ? " · " + l.town : ""}`
        : `${l.type || ""}${l.town ? " · " + l.town : ""} · score ${l.perf_score || 0}`;
      return `<div class="lead-item${sel}" data-slug="${slugify(l.name)}" tabindex="0">
        <div><div class="lead-name">${hot ? "🔥 " : ""}${l.name || ""}</div><div class="lead-meta">${meta}</div></div>
        <div class="lead-right">${compact ? `<span class="score">${l.perf_score || 0}</span>` : ""}<span class="pill ${cls}">${label}</span></div>
      </div>`;
    }
    function renderLeadList(elId, compact) {
      const el = document.getElementById(elId);
      if (!leadsCache.length) { el.innerHTML = `<div class="empty">No leads yet. Hit ▶ Run Pipeline to gather some.</div>`; return; }
      el.innerHTML = leadsCache.map(l => leadItemHTML(l, compact)).join("");
      el.querySelectorAll(".lead-item").forEach(row => {
        const go = () => selectLead(row.dataset.slug);
        row.addEventListener("click", go);
        row.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
      });
    }
    async function selectLead(slug) {
      currentSlug = slug;
      document.getElementById("approve-btn").disabled = false;
      renderLeadList("leads-list", true);
      renderLeadList("leads-full-list", false);
      try {
        const demo = await apiGet(`/api/demos/${slug}`);
        renderPreview(demo.html);
        document.getElementById("run-status").textContent = `Previewing the demo for “${slug}”.`;
      } catch (e) {
        document.getElementById("demo-preview").srcdoc =
          `<p style='font-family:system-ui;color:#999;padding:2rem;'>No demo generated yet for “${slug}”.</p>`;
        document.getElementById("run-status").textContent = `No demo generated yet for “${slug}”.`;
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

    /* ---------- actions ---------- */
    document.getElementById("approve-btn").addEventListener("click", async () => {
      if (!currentSlug) return;
      try {
        await apiPost("/api/approve", { kind: "dashboard_approve_and_send", identifier: currentSlug });
        document.getElementById("run-status").textContent = `Logged approval for “${currentSlug}”. This does NOT send anything.`;
        pushActivity(`Approved “${currentSlug}” (logged, not sent).`);
      } catch (e) { document.getElementById("run-status").textContent = "Couldn't reach the backend to log approval."; }
    });
    document.getElementById("run-pipeline-btn").addEventListener("click", async () => {
      const st = document.getElementById("run-status");
      st.textContent = "Starting pipeline in the background…";
      try {
        await apiPost("/api/run-pipeline", { stage: "all", towns: ["Mahopac", "Carmel"], niches: ["dentist", "roofer"], limit: 5 });
        st.textContent = "Pipeline started. Check output/logs/pipeline_run.log, or refresh in a bit.";
        pushActivity("Pipeline run started (scrape → grade → demo → outreach).");
      } catch (e) { st.textContent = "Failed to start — is the backend running?"; }
    });

    /* ---------- demos + outreach pages ---------- */
    async function loadDemos() {
      const el = document.getElementById("demos-list");
      try {
        const demos = await apiGet("/api/demos");
        if (!demos.length) { el.innerHTML = `<div class="empty">No demos generated yet.</div>`; return; }
        el.innerHTML = demos.map(d => `<div class="draft-card"><strong>${d.slug}</strong></div>`).join("");
      } catch (e) { el.innerHTML = `<div class="empty">Backend unreachable.</div>`; }
    }
    async function loadOutreach() {
      const el = document.getElementById("outreach-list");
      try {
        const drafts = await apiGet("/api/outreach");
        if (!drafts.length) { el.innerHTML = `<div class="empty">No outreach drafts yet.</div>`; return; }
        let html = "";
        for (const d of drafts) {
          const full = await apiGet(`/api/outreach/${d.slug}`);
          html += `<div class="draft-card"><strong>${d.slug}</strong>
            <pre>${full.content.replace(/</g, "&lt;")}</pre>
            <button class="btn secondary small" data-approve-slug="${d.slug}">Approve</button></div>`;
        }
        el.innerHTML = html;
        el.querySelectorAll("[data-approve-slug]").forEach(btn => {
          btn.addEventListener("click", async () => {
            await apiPost("/api/approve", { kind: "outreach_approved", identifier: btn.dataset.approveSlug });
            btn.textContent = "Approved ✓"; btn.disabled = true;
            pushActivity(`Approved outreach draft “${btn.dataset.approveSlug}”.`);
          });
        });
      } catch (e) { el.innerHTML = `<div class="empty">Backend unreachable.</div>`; }
    }

    /* ---------- nav tabs ---------- */
    function goToPage(page) {
      document.querySelectorAll(".navtabs button").forEach(b => b.classList.toggle("active", b.dataset.page === page));
      ["dashboard", "leads", "demos", "outreach"].forEach(p => {
        document.getElementById(`page-${p}`).style.display = p === page ? "" : "none";
      });
      if (page === "demos") loadDemos();
      if (page === "outreach") loadOutreach();
    }
    document.querySelectorAll(".navtabs button").forEach(btn => btn.addEventListener("click", () => goToPage(btn.dataset.page)));

    /* ---------- revenue card: editable price-per-deal ---------- */
    document.getElementById("revenue-card").addEventListener("click", () => {
      const cur = getRevPer();
      const next = prompt("Average price per closed deal (used for Potential Revenue):", cur);
      const n = Number((next || "").replace(/[^0-9.]/g, ""));
      if (n > 0) { setRevPer(n); if (lastStatus) renderRevenue(lastStatus.hot_leads); }
    });

    /* ---------- chat ---------- */
    const chatPanel = document.getElementById("chat-panel");
    const chatMessages = document.getElementById("chat-messages");
    const chatInput = document.getElementById("chat-input");
    document.getElementById("chat-toggle").addEventListener("click", () => chatPanel.classList.toggle("open"));
    function addChatMsg(text, who) {
      const div = document.createElement("div");
      div.className = `chat-msg ${who}`; div.textContent = text;
      chatMessages.appendChild(div); chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    async function sendChat() {
      const msg = chatInput.value.trim();
      if (!msg) return;
      addChatMsg(msg, "user"); chatInput.value = ""; addChatMsg("Thinking…", "bot");
      try {
        const res = await apiPost("/api/chat", { message: msg });
        chatMessages.lastChild.textContent = res.reply || "(no response)";
      } catch (e) {
        chatMessages.lastChild.textContent = "Couldn't reach the assistant — is fastapi_backend + Ollama running?";
      }
    }
    document.getElementById("chat-send").addEventListener("click", sendChat);
    chatInput.addEventListener("keydown", e => { if (e.key === "Enter") sendChat(); });

    /* ---------- settings ---------- */
    document.getElementById("settings-btn").addEventListener("click", () => {
      const next = prompt(
        "Backend URL (your fastapi_backend.py address — e.g. https://xxxx.ngrok-free.app, or http://localhost:8502 on the same laptop):",
        getApiBase()
      );
      if (next && next.trim()) { setApiBase(next.trim()); API_BASE = getApiBase(); refreshAll(); }
    });

    /* ---------- command palette (⌘K / Ctrl+K) ---------- */
    const overlay = document.getElementById("palette-overlay");
    const pInput = document.getElementById("palette-input");
    const pList = document.getElementById("palette-list");
    let pActive = 0, pItems = [];
    const COMMANDS = [
      { ico: "◫", label: "Go to Mission Control", tag: "Section", run: () => goToPage("dashboard") },
      { ico: "☰", label: "Go to Leads", tag: "Section", run: () => goToPage("leads") },
      { ico: "▦", label: "Go to Demos", tag: "Section", run: () => goToPage("demos") },
      { ico: "✉", label: "Go to Outreach", tag: "Section", run: () => goToPage("outreach") },
      { ico: "▶", label: "Run Pipeline", tag: "Action", run: () => document.getElementById("run-pipeline-btn").click() },
      { ico: "⟳", label: "Refresh data", tag: "Action", run: () => refreshAll() },
      { ico: "💬", label: "Open chat assistant", tag: "Action", run: () => chatPanel.classList.add("open") },
      { ico: "⚙", label: "Set backend URL", tag: "Action", run: () => document.getElementById("settings-btn").click() },
    ];
    function openPalette() { overlay.classList.add("open"); pInput.value = ""; buildPalette(""); pInput.focus(); }
    function closePalette() { overlay.classList.remove("open"); }
    function buildPalette(q) {
      q = q.toLowerCase();
      const cmds = COMMANDS.filter(c => c.label.toLowerCase().includes(q));
      const leadHits = leadsCache
        .filter(l => (l.name || "").toLowerCase().includes(q) && q)
        .slice(0, 6)
        .map(l => ({ ico: "🔎", label: l.name, tag: "Lead", run: () => { goToPage("dashboard"); selectLead(slugify(l.name)); } }));
      pItems = [...cmds, ...leadHits];
      pActive = 0;
      pList.innerHTML = pItems.map((it, i) =>
        `<li data-i="${i}" class="${i === 0 ? "active" : ""}"><span class="cmd-ico">${it.ico}</span><span>${it.label}</span><span class="cmd-tag">${it.tag}</span></li>`
      ).join("") || `<li class="empty" style="color:var(--faint);cursor:default;">No matches</li>`;
      pList.querySelectorAll("li[data-i]").forEach(li => {
        li.addEventListener("click", () => runPaletteItem(Number(li.dataset.i)));
      });
    }
    function runPaletteItem(i) { const it = pItems[i]; if (it) { closePalette(); it.run(); } }
    function movePalette(d) {
      if (!pItems.length) return;
      pActive = (pActive + d + pItems.length) % pItems.length;
      pList.querySelectorAll("li[data-i]").forEach(li => li.classList.toggle("active", Number(li.dataset.i) === pActive));
      const active = pList.querySelector("li.active"); if (active) active.scrollIntoView({ block: "nearest" });
    }
    pInput.addEventListener("input", () => buildPalette(pInput.value));
    pInput.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { e.preventDefault(); movePalette(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); movePalette(-1); }
      else if (e.key === "Enter") { e.preventDefault(); runPaletteItem(pActive); }
      else if (e.key === "Escape") closePalette();
    });
    overlay.addEventListener("click", e => { if (e.target === overlay) closePalette(); });
    document.getElementById("palette-btn").addEventListener("click", openPalette);
    document.addEventListener("keydown", e => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); overlay.classList.contains("open") ? closePalette() : openPalette(); }
    });

    /* ---------- PWA ---------- */
    if ("serviceWorker" in navigator) {
      window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
    }

    /* ---------- boot ---------- */
    function refreshAll() { loadStatus(); loadLeads(); }
    addChatMsg("Hi! I'm your pipeline assistant. Ask about your hot leads, drafts, or pricing.", "bot");
    renderFeed();
    refreshAll();
    setInterval(loadStatus, 15000);
  </script>
</body>
</html>

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

# Automation & media

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

# PWA shell

## `manifest.json`  
_(14 lines)_

```json
{
  "name": "Obsidian Labs Pipeline Dashboard",
  "short_name": "Obsidian Labs",
  "description": "Local AI lead-gen pipeline dashboard - review leads, demos, and outreach drafts.",
  "start_url": "dashboard_leadflow.html",
  "display": "standalone",
  "background_color": "#f6f7f9",
  "theme_color": "#f6f7f9",
  "icons": [
    { "src": "icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}

```

## `sw.js`  
_(43 lines)_

```javascript
// Obsidian Labs Dashboard - minimal offline app-shell cache.
// Caches the static shell (HTML/CSS/JS/icons) so the dashboard opens instantly and
// works if briefly offline. Does NOT cache API responses from fastapi_backend - live
// data always comes from the network.
const CACHE_NAME = "obsidian-labs-shell-v3";
const SHELL_FILES = [
  "dashboard_leadflow.html",
  "tesla_style_dashboard_v2.html",
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

# Prompt templates

## `templates/demo_system_prompt.md`  
_(39 lines)_

```markdown
<!--
  STARTER TEMPLATE — replace with your real design-standards content from Drive.
  This is a sensible default so demo_gen_local.py runs today. It intentionally
  matches the hard guardrails ensure_guardrails() checks for (noindex meta,
  expiry banner, obsidianlabshq.io watermark) so those are baked into the output
  rather than injected after the fact.
-->
You are the lead front-end designer at **Obsidian Labs**, a premium web-design studio.
Your job: generate ONE complete, self-contained, single-file HTML demo website for a
single local business, at the quality bar of a top agency — not a template, not a
generic "AI look."

## Non-negotiable output rules
- Output ONLY the HTML document. Start at `<!DOCTYPE html>`. No explanation, no markdown fences.
- Everything inline in one file: CSS in a `<style>` tag, any JS in a `<script>` tag. No external
  build step and no external JS/CSS/font CDNs (assume the file is opened directly).
- Include `<meta name="robots" content="noindex, nofollow">` in the `<head>` — this is a private
  preview, it must never be indexed.
- Add a slim banner at the very top of `<body>`:
  `Preview built by Obsidian Labs — expires {expiry_date}` (use the exact expiry_date value given).
- Add a small footer at the very bottom: `Built at obsidianlabshq.io`.
- Use ONLY the real business data provided. Never invent phone numbers, addresses, reviews,
  prices, or awards. If a field is missing, design gracefully around its absence.

## Quality bar
- Distinctive, intentional typography (system fonts are fine; avoid a bland default look).
- Strong visual hierarchy, generous spacing, a cohesive palette suited to the niche.
- Mobile-first: this is the version most owners will open. It must feel designed, not shrunk.
- One clear primary call-to-action that drives real business (call, book, request a quote, order).

## Recommended sections (adapt to the niche)
1. Hero — business name, a specific one-line value proposition, primary CTA.
2. Services / menu / offerings — the 3–5 things this business is known for.
3. Trust — real ratings/reviews if provided; otherwise a simple credibility strip.
4. Location & contact — address, phone, hours (only what's provided), and a clear CTA.
5. Footer — hours/contact recap + the Obsidian Labs watermark line above.

Design like the owner will see it and think "this looks more expensive than my current site."

```

## `templates/email_system_prompt.md`  
_(59 lines)_

````markdown
<!--
  STARTER TEMPLATE — replace with your real outreach-voice content from Drive.
  Default so outreach_local.py runs today. Matches ensure_compliance() (physical
  address + unsubscribe link must appear) and the pricing/brand from the handoff.
-->
You write cold-outreach email drafts for **Obsidian Labs**, a local web-design studio.
These are DRAFTS ONLY — a human reviews and sends them manually. Nothing is auto-sent.

## Voice
- Low-pressure, specific, and human. Never pushy, never hypey, never "AI-built."
- Lead with one specific, real observation about *their* current site or online presence
  (slow on mobile, no online booking, outdated look, no website at all) — not generic flattery.
- Sell the outcome (more customers, a professional first impression, easy mobile booking),
  never the method or the technology.
- Short. 4–7 sentences per email. Plain language.

## Pricing (state plainly when relevant; don't over-explain)
- Starter one-page site: **$1,495** flat
- Professional: **$2,500** (most popular)
- Business Growth: **$4,500+**
- Optional care plan: **$50/month** (hosting + small edits)

## Compliance (required in EVERY email — CAN-SPAM)
- Include the physical mailing address exactly as given: `{physical_address}`.
- Include an unsubscribe line with the link exactly as given: `{unsubscribe_link}`.
- No false or misleading claims. No fabricated results, reviews, or urgency.
- Reference the demo using the provided `demo_link` value (do not invent a URL).

## Output format (follow exactly)
Produce a **3-email sequence** in Markdown:

```
## Email 1 — Intro + demo
Subject: <subject>

<body — lead with the specific observation, mention the demo, soft ask>

<physical address>
Unsubscribe: <unsubscribe link>

## Email 2 — Follow-up (send ~3 days later if no reply)
Subject: <subject>

<body — light nudge, offer to tailor the demo>

<physical address>
Unsubscribe: <unsubscribe link>

## Email 3 — Final, low-key close (send ~4 days after Email 2)
Subject: <subject>

<body — last soft touch, easy yes/no, leave the door open>

<physical address>
Unsubscribe: <unsubscribe link>
```

End each email with a genuinely easy next step (a quick reply, a look at the demo) — never a hard CTA.

````

## `templates/reference_demos/wallys-super-service.html`  
_(82 lines)_

```html
<!DOCTYPE html>
<!-- SAMPLE reference demo (fictional business) — quality bar only, not a real client. -->
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="robots" content="noindex, nofollow" />
  <title>Wally's Super Service — Auto Repair in Anytown</title>
  <style>
    :root { --ink:#141414; --paper:#f7f5f1; --brand:#c0392b; --brand-d:#96271b; --muted:#6b6b60; }
    * { box-sizing: border-box; margin: 0; }
    body { font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: #141414; background: #f7f5f1; line-height: 1.5; }
    .banner { background: #111; color: #fff; text-align: center; padding: .5rem; font-size: .85rem; }
    .wrap { max-width: 1080px; margin: 0 auto; padding: 0 1.5rem; }
    header { display: flex; justify-content: space-between; align-items: center; padding: 1.2rem 0; }
    .logo { font-weight: 800; letter-spacing: -.02em; font-size: 1.25rem; }
    .logo span { color: #c0392b; }
    .btn { display: inline-block; background: #c0392b; color: #fff; text-decoration: none; font-weight: 700; padding: .8rem 1.5rem; border-radius: 8px; }
    .btn:hover { background: #96271b; }
    .hero { display: grid; grid-template-columns: 1.1fr .9fr; gap: 2rem; align-items: center; padding: 3rem 0; }
    .hero h1 { font-size: 2.8rem; line-height: 1.05; letter-spacing: -.03em; }
    .hero p { margin: 1rem 0 1.6rem; font-size: 1.1rem; color: #4b4b45; max-width: 42ch; }
    .hero .card { background: #fff; border-radius: 16px; padding: 1.6rem; box-shadow: 0 20px 50px rgba(0,0,0,.08); }
    .hero .card h3 { font-size: 1rem; text-transform: uppercase; letter-spacing: .08em; color: #6b6b60; }
    .hours { list-style: none; padding: 0; margin: .6rem 0 0; }
    .hours li { display: flex; justify-content: space-between; padding: .35rem 0; border-bottom: 1px solid #eee; }
    .services { padding: 2.5rem 0; }
    .services h2 { font-size: 1.8rem; letter-spacing: -.02em; margin-bottom: 1.4rem; }
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.2rem; }
    .svc { background: #fff; border-radius: 14px; padding: 1.4rem; border: 1px solid #ecebe6; }
    .svc h3 { font-size: 1.1rem; margin-bottom: .4rem; }
    .svc p { color: #6b6b60; font-size: .95rem; }
    .cta { background: #141414; color: #fff; border-radius: 20px; padding: 2.6rem; text-align: center; margin: 2rem 0; }
    .cta h2 { font-size: 1.9rem; letter-spacing: -.02em; }
    .cta p { color: #c9c9c2; margin: .6rem 0 1.4rem; }
    footer { text-align: center; color: #8a8a80; font-size: .85rem; padding: 2rem 0; }
    @media (max-width: 760px) { .hero { grid-template-columns: 1fr; } .grid { grid-template-columns: 1fr; } .hero h1 { font-size: 2.1rem; } }
  </style>
</head>
<body>
  <div class="banner">Preview built by Obsidian Labs — expires {expiry_date}</div>
  <div class="wrap">
    <header>
      <div class="logo">Wally's <span>Super Service</span></div>
      <a class="btn" href="tel:+15550000000">Call (555) 000-0000</a>
    </header>

    <section class="hero">
      <div>
        <h1>Honest auto repair, done right the first time.</h1>
        <p>Family-owned in Anytown for 20 years. Fast diagnostics, fair prices, and a two-year warranty on every major repair.</p>
        <a class="btn" href="#book">Book an appointment</a>
      </div>
      <div class="card">
        <h3>Open today</h3>
        <ul class="hours">
          <li><span>Mon–Fri</span><span>7:30 – 6:00</span></li>
          <li><span>Saturday</span><span>8:00 – 2:00</span></li>
          <li><span>Sunday</span><span>Closed</span></li>
        </ul>
      </div>
    </section>

    <section class="services">
      <h2>What we do</h2>
      <div class="grid">
        <div class="svc"><h3>Diagnostics</h3><p>Check-engine lights read and explained in plain English — no upsells.</p></div>
        <div class="svc"><h3>Brakes & tires</h3><p>Same-day brake service and tire changes, most makes and models.</p></div>
        <div class="svc"><h3>Oil & maintenance</h3><p>Fast oil changes and scheduled maintenance to keep you on the road.</p></div>
      </div>
    </section>

    <section class="cta" id="book">
      <h2>Need a repair this week?</h2>
      <p>Call or book online — we'll get you a real quote before any work starts.</p>
      <a class="btn" href="tel:+15550000000">Call (555) 000-0000</a>
    </section>
  </div>
  <footer>123 Main St, Anytown &middot; (555) 000-0000<br />Built at obsidianlabshq.io</footer>
</body>
</html>

```

## `templates/reference_demos/README.md`  
_(16 lines)_

```markdown
# Reference demos

`demo_gen_local.py` optionally loads one file here as a **few-shot code-quality
example** — a concrete "this is the bar" sample the local model imitates for
structure and polish (never for content).

- `wallys-super-service.html` — a **sample** reference (a fictional auto shop),
  provided so demo generation has a quality bar out of the box. It is not a real
  client. Replace it with one of your own best shipped demos for higher fidelity
  to your actual style.

The generator is explicitly told to copy *technique*, not content — it must never
reuse the reference business's name, address, phone, or reviews for a different lead.
If this folder is empty, demo generation still works (it just runs without a few-shot
example, and prints a NOTE).

```

# Config & deps

## `requirements.txt`  
_(25 lines)_

```text
# Obsidian Labs — full system dependencies (engine + backend + dashboards).
# Install:  pip install -r requirements.txt

# --- FastAPI backend + PWA dashboards ---
fastapi>=0.110,<1.0
uvicorn>=0.29,<1.0
pydantic>=2.0,<3.0

# --- Shared ---
requests>=2.31,<3.0
python-dotenv>=1.0,<2.0
pillow>=10.0,<11.0
schedule>=1.2,<2.0

# --- Streamlit review dashboard (engine) ---
streamlit>=1.36,<2.0
pandas>=2.0,<3.0

# --- Local LLM + RAG (Ollama + Chroma) ---
langchain-ollama>=0.1,<1.0
langchain-community>=0.2,<1.0
langchain-text-splitters>=0.2,<1.0
langchain-chroma>=0.1,<1.0
chromadb>=0.5,<1.0

```

## `.env.example`  
_(41 lines)_

```ini
# Obsidian Labs pipeline - environment variables (copy to .env at the repo root).
# Save as plain UTF-8. A stray BOM is handled by the code (load_dotenv uses utf-8-sig).

# ===================== REQUIRED =====================

# Google Cloud API key with BOTH "Places API" and "PageSpeed Insights API" enabled.
# Used by scraper.py (find businesses) and grader.py (score their sites).
GOOGLE_API_KEY=

# RAG source document locations (Google Drive + Obsidian vault).
# On Windows these are typically a mounted drive letter, e.g. G:\My Drive.
GDRIVE_PATH=C:\Users\Laptop\My Drive
OBSIDIAN_VAULT_PATH=C:\Users\Laptop\My Drive\Shipper Vault

# ===================== OLLAMA (local LLM) =====================
# Defaults match the models the handoff pulls; override only if you use others.
OLLAMA_MODEL=qwen2.5:14b-instruct-q4_K_M
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_BASE_URL=http://localhost:11434

# Where the local Chroma RAG index is persisted (relative to repo root is fine).
CHROMA_DB_PATH=./chroma_db

# ===================== OUTREACH (CAN-SPAM) =====================
# Included in every outreach draft. Use your real business mailing address.
PHYSICAL_ADDRESS=85 Wixon Pond Rd, Mahopac, NY 10541
UNSUBSCRIBE_LINK=https://obsidianlabshq.io/unsubscribe

# ===================== OPTIONAL =====================
# Stock-photo fallback in media_enhancer.py (free key: unsplash.com/developers)
UNSPLASH_ACCESS_KEY=

# Telegram ping when the nightly orchestrator starts/finishes/fails
OL_TELEGRAM_TOKEN=
OL_TELEGRAM_CHAT_ID=

# Nightly orchestrator tuning
OL_STAGE_TIMEOUT=1800
OL_NIGHTLY_LIMIT=5
OL_RUN_AT=02:00

```

## `.streamlit/config.toml`  
_(11 lines)_

```toml
# Dark theme for the Streamlit review dashboard (python pipeline.py --stage dashboard).
[theme]
base = "dark"
primaryColor = "#cc0000"
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#161a22"
textColor = "#f5f5f5"

[server]
headless = true

```

## `.gitignore`  
_(15 lines)_

```text
# Secrets & local config
.env

# Pipeline runtime output (leads, demos, drafts, logs, dedup state)
output/

# Local RAG index
chroma_db/

# Python
__pycache__/
*.py[cod]
venv/
.venv/

```

## `setup.ps1`  
_(123 lines)_

```powershell
<#
  Obsidian Labs - one-shot setup & launch (Windows PowerShell)
  --------------------------------------------------------------
  This MERGES the new dashboard/backend files (the folder this script lives in)
  into your existing engine repo, installs deps, pulls the Ollama models, then
  launches Ollama + the backend and opens the dashboard.

  Easiest way to run it (clones the new files, then runs this):
     cd $env:USERPROFILE
     git clone --branch claude/powershell-capabilities-pmxppx --depth 1 `
       https://github.com/themortgagemaster01-eng/anthony-nigrelli-mortgage.git obsidian_new
     cd obsidian_new\obsidian-local-pipeline
     powershell -ExecutionPolicy Bypass -File .\setup.ps1

  Nothing here ever sends an email. Safe to re-run.
  Edit the CONFIG block only if your folders differ.
#>

# ============================ CONFIG ============================
$Engine     = "C:\Users\Laptop\obsidian-local-pipeline"   # where the engine lives (pipeline.py, scraper.py, ...)
$Source     = $PSScriptRoot                               # the new files = the folder THIS script is in
$EngineRepo = "https://github.com/themortgagemaster01-eng/obsidian-local-pipeline.git"
$GitEmail   = "themortgagemaster01@gmail.com"
$GitName    = "Robert"
$BackendPort = 8502
$Models     = @("qwen2.5:14b-instruct-q4_K_M", "nomic-embed-text")
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
    Say "    Git:    https://git-scm.com/download/win"
    Say "    Python: https://www.python.org/downloads/  (tick 'Add to PATH')"
    Say "    Ollama: https://ollama.com/download"
    return
}
Say "  OK - all three found." "Green"
if (-not (git config --global user.email)) { git config --global user.email $GitEmail }
if (-not (git config --global user.name))  { git config --global user.name  $GitName }

# --- 2. make sure the ENGINE repo is present on this laptop ---
Say "[2/6] Locating engine repo..." "Yellow"
if (-not (Test-Path (Join-Path $Engine "pipeline.py"))) {
    if (-not (Test-Path $Engine)) {
        Say "  Engine not found - cloning $EngineRepo ..." "DarkGray"
        git clone $EngineRepo $Engine
    } else {
        Say "  Folder exists but pipeline.py is missing." "DarkYellow"
        Say "  Make sure $Engine is your obsidian-local-pipeline clone, then re-run." "DarkYellow"
    }
} else {
    try { Push-Location $Engine; git pull --ff-only 2>$null; Pop-Location } catch {}
}
Say "  Engine: $Engine" "Green"

# --- 3. merge the NEW files (this folder) into the engine repo ---
Say "[3/6] Copying new dashboard + backend files into the engine..." "Yellow"
if ($Source -and ($Source -ne $Engine)) {
    Get-ChildItem -Path $Source -File | Where-Object { $_.Name -ne "setup.ps1" } |
        Copy-Item -Destination $Engine -Force
    foreach ($d in "docs") {
        $sd = Join-Path $Source $d
        if (Test-Path $sd) { Copy-Item $sd -Destination $Engine -Recurse -Force }
    }
    Say "  Copied new files into $Engine" "Green"
} else {
    Say "  (Script is already inside the engine folder - nothing to copy.)" "DarkGray"
}

# --- 4. python packages ---
Say "[4/6] Installing Python packages..." "Yellow"
$venv = Join-Path $Engine "venv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv; Say "  venv activated." "DarkGray" }
python -m pip install --quiet --upgrade pip
$reqs = Join-Path $Engine "requirements.txt"
if (Test-Path $reqs) { python -m pip install --quiet -r $reqs }
else { python -m pip install --quiet fastapi uvicorn pydantic requests pillow python-dotenv schedule }
Say "  Packages installed." "Green"

# --- 4b. .env sanity ---
$envFile = Join-Path $Engine ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $Engine ".env.example") $envFile -ErrorAction SilentlyContinue
    Say "  Created .env from .env.example - add your GOOGLE_API_KEY before running the pipeline." "DarkYellow"
} elseif (-not (Select-String -Path $envFile -Pattern '^GOOGLE_API_KEY=.+' -Quiet)) {
    Say "  NOTE: GOOGLE_API_KEY is not set in .env - scrape/grade stages need it (Places + PageSpeed)." "DarkYellow"
}

# --- 5. ollama models ---
Say "[5/6] Checking Ollama models (first run may download several GB)..." "Yellow"
$installed = (ollama list) 2>$null
foreach ($m in $Models) {
    if ($installed -match [regex]::Escape($m)) { Say "  Already have $m" "DarkGray" }
    else { Say "  Pulling $m ..." "DarkGray"; ollama pull $m }
}
Say "  Models ready." "Green"

# --- 6. launch ---
Say "[6/6] Launching Ollama + backend..." "Yellow"
Start-Process powershell -ArgumentList '-NoExit','-Command','Write-Host "Ollama - keep me open"; ollama serve'
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList '-NoExit','-Command',"Set-Location '$Engine'; Write-Host 'Backend - keep me open'; uvicorn fastapi_backend:app --port $BackendPort"
Start-Sleep -Seconds 3

$dashboard = Join-Path $Engine "dashboard_leadflow.html"
if (-not (Test-Path $dashboard)) { $dashboard = Join-Path $Engine "tesla_style_dashboard_v2.html" }
if (-not (Test-Path $dashboard)) { $dashboard = Join-Path $Engine "tesla_style_dashboard_with_chat.html" }
if (Test-Path $dashboard) { Start-Process $dashboard }

Say "`n=== Done! ===" "Cyan"
Say "Two new windows opened (Ollama + Backend) - leave them running." "White"
Say "Dashboard opened in your browser. Click 'Run Pipeline' to gather your first leads." "White"
Say "Phone access: run 'ngrok http $BackendPort', then paste that URL into the dashboard settings.`n" "White"

```

# Docs

## `README.md`  
_(127 lines)_

````markdown
# Obsidian Labs — Local Pipeline (new files, reconstructed)

A $0-cost, fully local AI pipeline for local-business lead generation, demo-site
generation, and outreach drafting. Nothing here calls a paid AI API — it runs on
[Ollama](https://ollama.com) (local LLM) plus a local RAG index. **Nothing in this
system auto-sends anything** — a human reviews and approves drafts in a dashboard,
then sends manually.

This is the **complete system**: the core engine (scrape → grade → RAG → demo → outreach)
plus the FastAPI backend, three dashboard skins, the nightly orchestrator, and media
enhancer. Flow: scrape local businesses → grade their current site → build a personalized
demo with a local LLM → draft a compliant outreach email → review/approve in a dashboard →
**you send manually**.

> **Docs:** see [`docs/`](docs/) for the business playbook (find → build → ship → sell)
> and the design spec + blueprint for a dark "Tesla v2" dashboard redesign.

## The engine (scrape → grade → RAG → demo → outreach)

| File | Purpose |
| --- | --- |
| `pipeline.py` | CLI orchestrator — runs any stage or `--stage all` |
| `scraper.py` | Finds local businesses via Google Places → `output/leads.csv` |
| `grader.py` | Scores each site via PageSpeed Insights → `output/leads_graded.csv` |
| `rag_setup.py` | Builds the local `chroma_db` index from your Drive/Obsidian docs |
| `demo_gen_local.py` | Generates a demo site per hot lead via local Ollama + RAG |
| `outreach_local.py` | Drafts a 3-touch, CAN-SPAM outreach sequence per hot lead |
| `dashboard.py` | Original Streamlit review dashboard (`--stage dashboard`, port 8501) |
| `templates/` | System prompts for demo + outreach generation, and a reference demo |

> `scraper.py` and `grader.py` are faithful re-implementations of the documented
> interface — swap in your real versions from Drive if they have custom logic.
> The `templates/*.md` prompts are **starter** content; replace them with your real
> design-standards / voice docs for on-brand output.

## The dashboard + automation layer

| File | Purpose |
| --- | --- |
| `autonomous_orchestrator.py` | Nightly scheduler v2 — fail-fast, dedup, Telegram notify, rotating logs, `--now` flag |
| `media_enhancer.py` | Sharpens/enhances real scraped photos (Pillow); optional Unsplash stock-photo fallback |
| `outreach_generator.py` | Drafts the $1,495 pitch email via local Ollama, grounded in RAG |
| `fastapi_backend.py` | API server (port 8502) powering the dashboard |
| `dashboard_leadflow.html` | **Current dashboard** — light, LeadFlow-style: sidebar nav, KPI cards with sparklines, lead-growth area chart, leads-by-niche donut, recent-leads table, demo-preview modal, chat, PWA |
| `tesla_style_dashboard_v2.html` | Alt dashboard — dark Tesla/Apple glassmorphism (status ring, ⌘K palette); same backend |
| `tesla_style_dashboard_with_chat.html` | Original v1 dashboard (light, tables); same backend |
| `dashboard_leadflow_preview.html` / `dashboard_v2_preview.html` / `dashboard_preview.html` | Self-contained sample-data previews (shareable, no backend) |
| `manifest.json` / `sw.js` | PWA manifest + service worker (installs the current dashboard as an app) |

> Three dashboard skins ship here — all talk to the **same** `fastapi_backend` with no
> backend changes. `dashboard_leadflow.html` is the current default; swap the one you
> prefer into `manifest.json` `start_url` to change which installs as the app.
| `icon-192.png` / `icon-512.png` | App icons (placeholder brand mark — swap for the real assets) |
| `requirements.txt` | Full dependency list for the whole system (engine + backend + dashboards) |
| `.env.example` | Template for the `.env` file (copy to `.env` and fill in) |
| `.streamlit/config.toml` | Dark theme for the Streamlit review dashboard |

## Two outreach drafters (both write `output/outreach/<slug>.md`)

- `outreach_local.py` — the engine's **3-touch** CAN-SPAM sequence; run by `pipeline.py`.
- `outreach_generator.py` — a single **$1,495 pitch** email; run by `autonomous_orchestrator.py`.

Use whichever fits; they're interchangeable entry points over the same data.

## Quick start

```bash
# 1. install everything
pip install -r requirements.txt

# 2. configure environment
cp .env.example .env      # then edit paths/keys

# 3. run the backend (leave running)
uvicorn fastapi_backend:app --port 8502 --reload

# 4. open the dashboard
#    - locally: open dashboard_leadflow.html  (alt skins: tesla_style_dashboard_v2.html, tesla_style_dashboard_with_chat.html)
#    - on a phone: serve via GitHub Pages + point the settings/backend URL at an ngrok tunnel
```

### Run the pipeline (the engine)

Needs a running `ollama serve` (with the two models pulled) and `GOOGLE_API_KEY` in `.env`.

```bash
# full run: scrape -> grade -> rag_ingest -> demo -> outreach
python pipeline.py --towns Mahopac Carmel --niches dentist roofer --limit 5

# or a single stage
python pipeline.py --stage scrape --towns Mahopac --niches dentist --limit 5
python pipeline.py --stage grade
python pipeline.py --stage rag_ingest     # rebuild the RAG index after adding docs
python pipeline.py --stage demo
python pipeline.py --stage outreach

# the original Streamlit review dashboard (port 8501)
python pipeline.py --stage dashboard
```

Or just click **Run Pipeline** in any of the web dashboards (it calls the backend,
which launches `pipeline.py` in the background and logs to `output/logs/pipeline_run.log`).

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

````

## `docs/README.md`  
_(23 lines)_

```markdown
# Obsidian Labs — Docs

Reference material for the pipeline and business around it.

| Doc | What it is |
| --- | --- |
| [business-playbook.md](business-playbook.md) | The full **find → build → ship → sell** playbook for selling premium one-page sites to local businesses (niche demos, Google Maps prospecting, outreach templates, pricing, follow-up). Synthesized from @bounceidc's July 2026 thread + Claude Code setup details. |
| [dashboard-v2-prompt.md](dashboard-v2-prompt.md) | A ready-to-paste prompt for generating a **v2 dashboard** — a Tesla/Apple-style dark glassmorphism redesign of `tesla_style_dashboard_with_chat.html` that keeps every current feature and needs **no backend changes**. |
| [tesla-dashboard-blueprint.md](tesla-dashboard-blueprint.md) | The **design blueprint** the v2 prompt refers to — color tokens, glassmorphism card CSS, animated status ring, layout sketch, and the feature list (command palette, live activity feed, KPI + Potential Revenue cards). |

## How these fit together

- **business-playbook.md** is the *why/how you make money* — the sales loop the pipeline feeds.
- **dashboard-v2-prompt.md** + **tesla-dashboard-blueprint.md** are the *design spec* for the next
  iteration of the dashboard UI. The current shipped dashboard is the light-themed
  `../tesla_style_dashboard_with_chat.html`; these two describe the dark "premium" v2 that would
  replace its look while reusing the same `fastapi_backend.py` API contract.

> Note: the v2 blueprint suggests a Next.js/React/Tailwind stack in one section, but the
> prompt itself asks for a **single self-contained HTML file** that works with the existing
> FastAPI backend on port 8502 — that single-file path is the one that matches how the current
> dashboard is built and deployed (GitHub Pages + ngrok, no build step).

```

## `docs/business-playbook.md`  
_(277 lines)_

````markdown
# Claude-Powered Local Website Business Guide
**Synthesized from the X post by @bounceidc (July 2026) + practical setup details for Claude Code**

This document compiles the full workflow for using Claude (Pro + Desktop App + Code mode + design skills) to build premium custom one-page websites for local businesses and sell them. It focuses on the complete loop: **find → build → ship → sell**.

The original post emphasizes that the *build* part is now commoditized and fast. The real work (and money) is in consistent, personalized outreach with finished demos.

---

## 1. Overview & Why This Works Right Now

**What's real:**
- Claude Code (in the desktop app) can generate full custom sites from scratch — no templates or Wix-like output.
- Two skills dramatically improve quality and remove the generic "AI look":
  - `frontend-design` (official Anthropic)
  - `UI/UX Pro Max` (community)
- Local businesses (restaurants, gyms, dentists, contractors, realtors, med spas, etc.) still pay $1,000–$5,000 for premium one-pagers. Many have outdated 2015-era sites or none at all.
- A thriving business with an embarrassing site already knows it needs fixing — you're not creating demand, you're capturing it.

**What's not real:**
- Nobody pays you just for knowing how to prompt. The money comes after you do outreach and deliver a finished demo.
- Realistic first deals take consistent effort (20 sends/week is a good target).

**The window:**
Collapsed build cost + closed quality gap + market that hasn't noticed yet = opportunity. It stays open until more people run this loop.

**Core loop (run weekly):**
1. Find 20 businesses on Google Maps (high-rated but bad site).
2. Build **one** strong demo for the niche (not per business).
3. Record 40-second screen capture (desktop + mobile).
4. Send personalized outreach with the video.
5. Follow up.
6. Close → build/host the real site + offer $50/mo care plan.

---

## 2. Prerequisites & Setup

### Get Claude Pro
- Subscribe at claude.ai (or via desktop app). ~$20/month.
- Pro unlocks stronger coding performance and full access to the skills/plugin system.

### Install the Claude Desktop App
- Download official app: https://claude.com/download (Mac, Windows, Linux versions available).
- Install and sign in with your Anthropic account.
- The app includes **Claude Code** features: open local folders as workspaces, generate/edit/preview code, manage skills, and run autonomous sessions.

**Note:** The desktop app may download a large VM bundle (~13 GB) for secure code execution. This is normal for Claude Code functionality.

### Install the Two Key Design Skills
These skills are what make the output look expensive instead of generic AI.

**Option A – Commands in Claude Code (recommended for precision)**
In the desktop app / Claude Code interface, use slash commands:

```bash
# Add marketplaces
/plugin marketplace add anthropics/skills
/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill

# Install skills (run after adding marketplaces)
/plugin install frontend-design@anthropics/skills
/plugin install ui-ux-pro-max@ui-ux-pro-max-skill
```

**Option B – GUI in Desktop App**
- Look for **Customize** (left sidebar or + button).
- Go to **Skills** or **Plugins** tab.
- Browse directory or search for the skill names.
- Install `frontend-design` and `UI/UX Pro Max`.
- Enable them globally or per project/workspace.

**What they do:**
- `frontend-design`: Guides production-ready HTML/CSS/JS or React with distinctive typography, creative layouts, thoughtful animations, and actively avoids overused fonts/patterns.
- `UI/UX Pro Max`: Provides a large database of UI styles, color palettes (60+), font pairings (50+), industry-specific design systems, accessibility/performance checklists, and stack-specific guidelines. Great for consistent premium output.

After installation, switch to **auto mode** (or equivalent) so Claude applies the skills without constant permission prompts.

**Tip:** Create a dedicated workspace folder for your client projects. Open it in the desktop app.

---

## 3. Building High-Quality Demos

### Preparation (once per niche)
- Pick a niche (e.g., Thai restaurants, local gyms, dental practices).
- Gather 3–5 reference screenshots from Dribbble, Awwwards, or Pinterest ("modern [niche] website design").
- Put them in a `/reference` folder inside your workspace.
- These images are shown to Claude — better than describing design in words.

### The Master Build Prompt
Use a structured prompt. The highest-leverage part is the final sentence that forces Claude to ask clarifying questions before generating code.

**Copy-paste template (customize the bracketed parts):**

```
Build a premium, modern, agency-quality one-page website for [SPECIFIC BUSINESS TYPE / NICHE, e.g. a Thai restaurant called "Thai Basil" in Cheshire CT].

Key requirements:
- Looks like a high-end agency built it (distinctive typography, excellent visual hierarchy, thoughtful spacing, subtle professional animations).
- Outstanding mobile experience (most visitors will see this version).
- Clear calls-to-action that drive real business results (reservations, bookings, leads, calls).
- Sections to include: [list them, e.g. Hero with strong headline + primary CTA, About/Story, Menu/ Services highlights, Social proof/testimonials, Location & contact, Footer].

Use the installed `frontend-design` and `UI/UX Pro Max` skills for production-grade output. Avoid generic AI aesthetics, overused fonts (e.g. Inter as default), template-like layouts, or low-effort components.

Before writing any code, ask me 5–7 specific clarifying questions about:
- Visual direction and overall aesthetic
- Color palette preferences or brand colors
- Priority sections and information hierarchy
- Copy tone and voice
- Animation level and interactions
- Target customer and key conversions

Once I answer, generate a complete, self-contained, high-quality HTML/CSS/JS site (single file or clean project structure) that I can immediately preview and iterate on.
```

**Why this works:** Claude stops, asks smart questions, and your answers become the foundation. You fight the output far less later.

### Polish & Iteration Passes (do these every time)
After the first version lands (~10 minutes):

**Pass 1 – Grade it**
```
Grade this website against premium agency standards. List specific, prioritized improvements for hierarchy, typography, spacing, visual weight, color usage, and mobile behavior. Be direct and constructive.
```

**Pass 2 – Make it expensive (batch improvements)**
```
Make this site feel expensive and premium. Apply a batch of improvements focused on:
- Tighter visual hierarchy and breathing room
- More distinctive and intentional typography
- Better color harmony and contrast
- Subtle, purposeful animations and micro-interactions
- Professional polish on buttons, cards, and sections

Do not fix things one by one — propose and apply a cohesive set of upgrades.
```

**Final Mobile Pass (critical)**
```
Perform a dedicated mobile optimization pass. Decide what hides, tightens, stacks, resizes, or becomes sticky on small screens. Ensure the mobile version feels intentional and not just a shrunk desktop site. This is the version most real visitors will see.
```

**Efficiency tip from the post:** Build **one demo per niche**, not per business. The Thai restaurant demo works for all Thai restaurants on your list. Record one 40-second video of it scrolling on desktop and phone — that video becomes your outreach ammo.

---

## 4. Finding Buyers on Google Maps (15 minutes per batch)

You're not looking for businesses that "need" a website. You're looking for **profitable businesses with bad/outdated sites**.

**Search strategy:**
- Open Google Maps.
- Pick one niche + one city/area (e.g., "Thai restaurant Cheshire CT" or "gym near me").
- Filter for 4.4+ stars (thriving businesses).
- Look for sites that look old, broken on mobile, missing key sections, or nonexistent.

**Build a simple spreadsheet list of 20:**
- Business name
- Contact (owner email if findable, or Instagram/Facebook — wherever owners actually respond)
- One specific, observable problem with their current site (this becomes your opener)

**Why high-rated businesses?** A failing business won't spend $1,500–$2,500 on a site. A successful one with an embarrassing site already feels the pain and has the budget.

---

## 5. Outreach & Closing (The Part Most People Skip)

You have a list + a niche demo + a short video. Now send.

**Recommended message template** (email or Instagram DM — wherever the owner is):

```
Hi [Owner Name or "Team at Business Name"],

I put together a quick demo of what a modern, high-converting website could look like for [Business Name / your niche].

[Attach or embed the 40-second screen recording video here]

A few things stood out when I looked at your current site: [specific problem you noted, e.g. "the menu doesn't display properly on phones" or "there's no easy way for customers to book online"].

I build clean, premium one-page sites like the one in the video. Flat price for the project is $[500–800 small market / $1,000–2,500 metro]. I also offer an optional $50/month care plan that covers hosting, updates, and small edits.

Would you be open to a quick look at the demo and chatting about whether something like this would help bring in more customers?

Best,
[Your Name]
```

**Rules that make it work (from the post):**
- Lead with the **video**, not your credentials.
- Name **one specific problem** with *their* site.
- State the flat price plainly.
- **Never say "AI-built"** — sell the outcome (more customers, better mobile experience, professional image), not the method.
- Follow up 3 days later if no reply: "Did the video land okay? Happy to tweak the demo to better match what you need."

**Pricing guidance:**
- Small markets / simpler niches: $500–$800
- Metro / higher-value niches (med spas, professional services): $1,000–$2,500
- Add-on: $50/month recurring care plan (hosting + edits). 10 care clients = $500/mo passive for minimal work.

**Realistic ramp:**
- 20 sends → 3–6 replies → 0–2 deals (most yeses come after follow-up).
- Two solid clients per month at ~$1,500 average = $3,000/month on part-time hours.
- Your growing library of demos makes every subsequent month faster.

**What kills 90% of attempts:**
- Polishing one demo for a week instead of sending it.
- Pitching the technology ("AI website") instead of outcomes.
- Choosing niches you personally like instead of niches that pay.
- No follow-up.
- Pricing too low ($200 range signals low quality).

---

## 6. Shipping the Real Site

- Only buy hosting/domain **after** the client says yes.
- Simple static hosting (Netlify, Vercel, or basic provider) + custom domain works great.
- Cost: Often $40–45 for the first year with a free domain.
- Common mistake: Zipping the whole project folder instead of the contents. `index.html` must be at the root of the zip.

---

## 7. Realistic Expectations & Mindset

This is **not** "press button, get rich." It is a repeatable system that rewards consistent execution.

- Building speed improves quickly once skills are installed and you have reference workflows.
- The bottleneck for most people is **sending the messages**. The ones making money treat it like a small sales job (20 personalized sends + follow-ups per week).
- Start small: One niche, one demo, 20 sends. Learn from replies.
- Track everything in a simple spreadsheet (businesses contacted, replies, deals closed, revenue).
- Legal/tax note: Treat this as a real small business (invoicing, contracts, taxes). Simple one-page service agreements protect both sides.

---

## 8. How to Use This Document with Claude

**Recommended workflow:**
1. Upload or paste this entire Markdown file into a new **Claude Project** (or chat with file upload).
2. Tell Claude: "Use this guide as your knowledge base. When I ask you to build a website for [niche/business], follow the master prompt structure, apply the installed skills, and go through the polish passes."
3. For each new client/niche, start a fresh conversation or sub-project and reference this file.
4. Ask Claude to help you:
   - Customize the master prompt for a specific business
   - Draft personalized outreach messages
   - Analyze a competitor's site and suggest improvements
   - Generate follow-up templates
   - Brainstorm niche ideas or Google Maps search strings for your area

---

## Bonus: Quick-Start Checklist

- [ ] Claude Pro active
- [ ] Desktop app installed and signed in
- [ ] `frontend-design` and `UI/UX Pro Max` skills installed globally
- [ ] Workspace folder created and opened in the app
- [ ] First niche chosen + 3–5 reference images collected
- [ ] Master prompt customized and tested on one demo
- [ ] 40-second demo video recorded
- [ ] Spreadsheet template ready for 20 businesses
- [ ] First 20 outreach messages drafted and ready to send

---

**Document version:** July 13, 2026  
**Source inspiration:** X post by @bounceidc (full thread)  
**Compiled & enhanced for practical use with Claude Code**

---

*This is a synthesized, actionable guide. The interface and exact skill installation commands in Claude may evolve — always check the latest in-app help or official docs if a command doesn't work. The principles (demo-first selling + consistent personalized outreach) remain powerful regardless of tool changes.*

**Next action:** Pick one niche you're interested in testing, tell me (or tell Claude after uploading this file), and we can generate your first customized prompt + starter site right away. 

You now have everything in one clean Markdown file ready to feed to Claude. Upload it, reference it, and start running the loop. Good luck!
````

## `docs/dashboard-v2-prompt.md`  
_(164 lines)_

````markdown
# Obsidian Labs — Tesla-Inspired Dashboard Prompt for Claude

**Purpose**  
This file contains everything you need to generate a clean, cool-looking, easy-to-use dashboard for the Obsidian Labs local lead-generation pipeline.  

The goal is a **premium but simple** Tesla/Apple-style interface (dark glassmorphism, animated status ring, nice KPI cards, minimal clutter) that still works 100% with your existing FastAPI backend and keeps every current feature.

You can copy the big prompt block below and paste it directly into Claude (or any strong LLM).

---

## Ready-to-Paste Prompt for Claude

```
You are a senior frontend engineer who specializes in premium, minimalist, Tesla and Apple-inspired interfaces that still feel simple and usable every day.

I run a small web design business called Obsidian Labs. I have a fully local AI pipeline that:
- Scrapes local businesses
- Grades their current websites
- Generates personalized demo websites using a local LLM (Ollama)
- Drafts outreach emails

Nothing ever sends automatically. A human reviews leads, demos, and drafts in a dashboard, then approves manually before sending anything.

### Current Working Dashboard
I already have a functional dashboard (`tesla_style_dashboard_with_chat.html` + `fastapi_backend.py` running on port 8502). It can:
- Load live leads, demos, and outreach drafts from the backend
- Preview demo HTML in an iframe with Desktop / Tablet / Mobile toggle
- Show outreach drafts with Approve buttons (approval only logs to a CSV — nothing is sent)
- Has a built-in chat widget that talks to local Ollama through the backend
- Has a "Run Pipeline" button
- Is a PWA (installable on phone)
- Lets me change the backend URL via a settings gear (stored in localStorage)

The current version works but looks basic (light theme, tables, red accents). I want it to look **cool and premium** while staying easy and simple to use.

### Design Vision
Use the Tesla + Apple inspired style from the attached Claude blueprint:
- Dark theme with radial gradient background (dark #0b0b0b at top fading to black)
- Glassmorphism: frosted glass cards with backdrop-filter blur, subtle borders, soft shadows, and gentle hover lift
- Minimal clean typography
- Smooth animations and transitions
- Animated status / AI ring (blue accent)
- Clean KPI cards (including a "Potential Revenue" card)
- Keep the whole interface feeling simple and calm — not busy or overwhelming

### Must Keep (Do Not Remove or Break)
- All existing functionality with the current FastAPI backend (no changes needed to fastapi_backend.py)
- Demo preview iframe with device size toggle
- Outreach draft list with Approve buttons
- Built-in AI chat widget (calls local Ollama)
- "Run Pipeline" button
- Settings gear for backend URL
- PWA support (manifest + service worker references)
- Approval system only logs — never sends anything
- Fully local operation

### Specific Improvements I Want
1. Apply the full dark glassmorphism theme and card styles from the Claude Tesla Dashboard Blueprint.
2. Add an animated Status / AI Ring (use the CSS from the blueprint). Place it prominently — maybe as "Pipeline Status" or "AI Health".
3. Create nice KPI cards at the top:
   - Leads
   - Hot Leads
   - Demos Generated
   - Outreach Drafts
   - Potential Revenue (calculate hot leads × $2,500 as a starting point, or make it easy to adjust)
4. Add a lightweight Command Palette (Ctrl/Cmd + K) that feels Tesla-like. It should let me quickly search leads, switch sections, refresh data, or open the chat.
5. Add a small Live Activity Feed (recent pipeline actions, new leads, approvals). Keep it simple.
6. Improve empty states and loading states so everything feels polished.
7. Prefer cards over heavy tables where it improves the visual feel without adding complexity.
8. Keep the layout clean and simple (header + main content area is fine). Make it mobile-friendly and PWA-ready.

### Output Instructions
- Return a **single self-contained HTML file** (everything in one file like the current dashboard).
- It must work perfectly with the existing FastAPI backend on port 8502 without any backend changes.
- Include the PWA manifest and service worker links so it remains installable.
- Add helpful code comments for new sections.
- Prioritize **easy + simple daily use** while making it look genuinely cool and premium.

Use the CSS variables, glassmorphism card styles, and status ring example from the Claude Tesla Dashboard Blueprint I provided earlier as your visual foundation.

Generate the complete updated HTML file now.
```

---

## Claude Tesla Dashboard Blueprint — Key CSS (for reference)

Copy this into Claude if the model needs the exact styles:

```css
:root {
  --bg: #0b0b0b;
  --panel: rgba(255, 255, 255, .06);
  --border: rgba(255, 255, 255, .08);
  --accent: #3b82f6;
  --text: #f5f5f5;
  --muted: #9ca3af;
  --radius: 18px;
}

body {
  background: radial-gradient(circle at top, #111, #000);
  color: var(--text);
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.card {
  backdrop-filter: blur(18px);
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: transform .25s ease, box-shadow .25s ease;
}

.card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}

/* Animated Status Ring */
.ring {
  width: 180px;
  height: 180px;
  border-radius: 50%;
  border: 8px solid rgba(59, 130, 246, .2);
  box-shadow: 0 0 30px rgba(59, 130, 246, .4);
  animation: pulse 2s infinite ease-in-out;
}

@keyframes pulse {
  50% {
    box-shadow: 0 0 50px rgba(59, 130, 246, .8);
  }
}
```

---

## How to Use This File

1. Open this Markdown file.
2. Copy the entire block under **"Ready-to-Paste Prompt for Claude"**.
3. Paste it into Claude (or your preferred LLM).
4. (Optional) Also attach or paste your current `tesla_style_dashboard_with_chat.html` if you want Claude to use it as the exact base.
5. Ask Claude to output the full single-file HTML.
6. Save the result as `dashboard.html` (or similar) and test it with your running FastAPI backend.

---

## Notes & Guardrails

- The new dashboard must remain **100% local** and respect the existing guardrails (approvals only log — nothing auto-sends).
- Keep the experience **easy and simple** for daily use while making it look cool and premium.
- No changes are required to `fastapi_backend.py` or the pipeline scripts.
- This version focuses on the **computer/local** experience first (cloud/hybrid access can be added later).

---

**File created:** 2026-07-13  
**For:** Robert Castro – Obsidian Labs Dashboard v2

You can now send the prompt above directly to Claude. Let me know when you want the next step (full generated HTML from me, cloud setup guide, PDF version of this file, etc.).

````

## `docs/tesla-dashboard-blueprint.md`  
_(101 lines)_

````markdown
# Claude Implementation Guide – Tesla-Inspired AI Dashboard

## Design Goals
- Tesla + Apple inspired UI
- Glassmorphism
- Minimal typography
- Keyboard-first
- Mobile-first PWA
- AI-first workflow

## Color Palette
```css
:root{
 --bg:#0b0b0b;
 --panel:rgba(255,255,255,.06);
 --border:rgba(255,255,255,.08);
 --accent:#3b82f6;
 --text:#f5f5f5;
 --muted:#9ca3af;
 --radius:18px;
}
body{
 background:radial-gradient(circle at top,#111,#000);
 color:var(--text);
 font-family:Inter,sans-serif;
}
.card{
 backdrop-filter:blur(18px);
 background:var(--panel);
 border:1px solid var(--border);
 border-radius:var(--radius);
 transition:.25s;
}
.card:hover{transform:translateY(-3px);}
```

## Landing Dashboard
- Greeting
- AI Status Ring (animated)
- Revenue cards
- Pipeline cards
- Live activity feed
- AI chat

## Layout
```
+-------------------------------+
| Header                        |
+----------+--------------------+
| Sidebar  | Mission Control    |
|          | KPI Cards          |
|          | Activity Feed      |
|          | AI Chat            |
+----------+--------------------+
```

## Components
### KPI Card
```html
<div class="card">
 <h3>Potential Revenue</h3>
 <h1>$43,500</h1>
 <small>+12%</small>
</div>
```

### Status Ring
```css
.ring{
 width:180px;height:180px;border-radius:50%;
 border:8px solid rgba(59,130,246,.2);
 box-shadow:0 0 30px rgba(59,130,246,.4);
 animation:pulse 2s infinite;
}
@keyframes pulse{
50%{box-shadow:0 0 50px rgba(59,130,246,.8);}
}
```

## Features
1. Command palette (Ctrl/Cmd+K)
2. Voice control
3. Before/after preview slider
4. Interactive pipeline
5. Live AI activity
6. Mission Control map
7. Mobile bottom navigation

## Suggested Stack
- Next.js
- React
- Tailwind CSS
- Framer Motion
- shadcn/ui
- Supabase
- Cloudflare R2
- Vercel

## Claude Instructions
Build a premium production-ready interface that feels like Tesla software. Avoid tables unless necessary. Use cards, subtle animation, frosted glass, dark theme, responsive layout, accessibility, and clean component architecture.

````

# Self-contained previews (sample-data copies of the dashboards)

## `dashboard_leadflow_preview.html`  
_(710 lines)_

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Obsidian Labs — Dashboard (Preview)</title>
  <meta name="theme-color" content="#f6f7f9" />
  <style>
    /* ============================================================
       Obsidian Labs — LeadFlow-style light dashboard.
       Single self-contained file. Same fastapi_backend on :8502,
       no backend changes. Charts are hand-drawn inline SVG (CSP-safe).
       ============================================================ */
    :root {
      --purple: #7c3aed;
      --purple-600: #6d28d9;
      --purple-50: #f3effe;
      --purple-100: #ede9fe;
      --blue: #3b82f6;
      --teal: #14b8a6;
      --orange: #f59e0b;
      --bg: #f6f7f9;
      --card: #ffffff;
      --border: #eceef2;
      --border-2: #e5e7eb;
      --text: #111827;
      --muted: #6b7280;
      --faint: #9ca3af;
      --good-bg: #dcfce7; --good-fg: #15803d;
      --new-bg: #dbeafe;  --new-fg: #1d4ed8;
      --warn-bg: #fef3c7; --warn-fg: #b45309;
      --bad-bg: #fee2e2;  --bad-fg: #b91c1c;
      --gray-bg: #f1f5f9; --gray-fg: #475569;
      --radius: 16px;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0; background: var(--bg); color: var(--text);
      font-family: system-ui, -apple-system, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      -webkit-font-smoothing: antialiased; letter-spacing: -0.011em;
    }
    .app { display: grid; grid-template-columns: 248px 1fr; min-height: 100vh; }

    /* ---------- sidebar ---------- */
    .sidebar { background: var(--card); border-right: 1px solid var(--border); padding: 1.25rem 0.9rem; display: flex; flex-direction: column; gap: 0.35rem; position: sticky; top: 0; height: 100vh; }
    .logo { display: flex; align-items: center; gap: 0.6rem; font-weight: 700; font-size: 1.15rem; padding: 0.2rem 0.6rem 1rem; }
    .logo .mark { width: 34px; height: 34px; border-radius: 10px; background: linear-gradient(150deg, var(--purple), #4f46e5); display: grid; place-items: center; color: #fff; font-size: 1.05rem; box-shadow: 0 6px 16px rgba(124,58,237,.35); }
    .nav { display: flex; flex-direction: column; gap: 0.15rem; }
    .nav button { display: flex; align-items: center; gap: 0.75rem; width: 100%; text-align: left; background: none; border: none; padding: 0.62rem 0.8rem; border-radius: 11px; font-size: 0.92rem; font-weight: 550; color: var(--muted); cursor: pointer; font-family: inherit; transition: all .15s; }
    .nav button:hover { background: var(--bg); color: var(--text); }
    .nav button.active { background: var(--purple-100); color: var(--purple-600); font-weight: 650; }
    .nav .ico { width: 20px; height: 20px; flex: none; opacity: .9; }
    .side-spacer { flex: 1; }
    .promo { background: var(--purple-50); border: 1px solid var(--purple-100); border-radius: var(--radius); padding: 1.1rem; text-align: center; margin: 0.5rem 0.3rem; }
    .promo .rocket { font-size: 1.5rem; }
    .promo h4 { margin: 0.5rem 0 0.3rem; font-size: 1.02rem; }
    .promo p { margin: 0 0 0.85rem; font-size: 0.82rem; color: var(--muted); line-height: 1.4; }
    .profile { display: flex; align-items: center; gap: 0.6rem; padding: 0.7rem 0.6rem 0.2rem; border-top: 1px solid var(--border); margin-top: 0.3rem; }
    .avatar { width: 38px; height: 38px; border-radius: 50%; display: grid; place-items: center; color: #fff; font-weight: 650; font-size: 0.85rem; flex: none; }
    .profile .who { font-size: 0.86rem; font-weight: 600; line-height: 1.2; }
    .profile .who small { display: block; color: var(--faint); font-weight: 400; font-size: 0.76rem; }

    /* ---------- main ---------- */
    .main { padding: 1.6rem 2rem 3rem; min-width: 0; }
    .topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
    .topbar h1 { margin: 0 0 0.25rem; font-size: 1.7rem; letter-spacing: -0.03em; }
    .topbar .sub { margin: 0; color: var(--muted); font-size: 0.92rem; max-width: 40ch; }
    .top-actions { display: flex; align-items: center; gap: 0.6rem; }
    .chip { display: inline-flex; align-items: center; gap: 0.5rem; background: var(--card); border: 1px solid var(--border-2); border-radius: 11px; padding: 0.55rem 0.85rem; font-size: 0.85rem; font-weight: 550; cursor: pointer; }
    .icon-btn { width: 42px; height: 42px; border-radius: 11px; background: var(--card); border: 1px solid var(--border-2); cursor: pointer; font-size: 1rem; position: relative; }
    .icon-btn .badge { position: absolute; top: 9px; right: 10px; width: 7px; height: 7px; background: var(--purple); border-radius: 50%; }

    .card { background: var(--card); border: 1px solid var(--border); border-radius: var(--radius); box-shadow: 0 1px 2px rgba(16,24,40,.04); }

    /* KPI row */
    .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.1rem; margin-bottom: 1.3rem; }
    .kpi { padding: 1.15rem 1.2rem; }
    .kpi .kico { width: 42px; height: 42px; border-radius: 11px; display: grid; place-items: center; font-size: 1.1rem; margin-bottom: 0.85rem; }
    .kico.p { background: var(--purple-100); color: var(--purple-600); }
    .kico.b { background: #dbeafe; color: var(--blue); }
    .kico.t { background: #ccfbf1; color: #0f766e; }
    .kico.o { background: #fef3c7; color: #b45309; }
    .kpi .klabel { font-size: 0.85rem; color: var(--muted); }
    .kpi .kvalue { font-size: 1.85rem; font-weight: 750; letter-spacing: -0.03em; margin: 0.1rem 0 0.35rem; font-variant-numeric: tabular-nums; }
    .kpi .kdelta { font-size: 0.8rem; font-weight: 600; display: inline-flex; gap: 0.3rem; align-items: center; }
    .kdelta.up { color: #15803d; } .kdelta.down { color: #b91c1c; } .kdelta.flat { color: var(--faint); }
    .kpi .kspark { margin-top: 0.7rem; height: 34px; }
    .kpi .kspark svg { width: 100%; height: 100%; display: block; }

    /* charts row */
    .charts { display: grid; grid-template-columns: 1fr 1fr; gap: 1.3rem; margin-bottom: 1.3rem; }
    .panel { padding: 1.3rem 1.4rem; }
    .panel-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.4rem; }
    .panel-head h3 { margin: 0; font-size: 1.12rem; letter-spacing: -0.02em; }
    select.range { border: 1px solid var(--border-2); border-radius: 9px; padding: 0.4rem 0.6rem; font-size: 0.82rem; font-family: inherit; background: var(--card); color: var(--text); cursor: pointer; }
    .area-wrap svg { width: 100%; height: auto; display: block; }
    .donut-wrap { display: flex; gap: 1.4rem; align-items: center; flex-wrap: wrap; }
    .donut-wrap svg { flex: none; }
    .legend { flex: 1; min-width: 200px; display: flex; flex-direction: column; gap: 0.55rem; }
    .legend-row { display: grid; grid-template-columns: 1fr auto auto; align-items: center; gap: 0.6rem; font-size: 0.9rem; }
    .legend-row .lname { display: flex; align-items: center; gap: 0.55rem; color: var(--text); }
    .legend-row .swatch { width: 10px; height: 10px; border-radius: 50%; }
    .legend-row .lpct { color: var(--muted); font-variant-numeric: tabular-nums; }
    .legend-row .lval { display: inline-flex; align-items: center; gap: 0.4rem; font-variant-numeric: tabular-nums; font-weight: 600; }
    .legend-row .lval .swatch { width: 8px; height: 8px; }

    /* recent leads table */
    .table-card { padding: 1.3rem 0; }
    .table-head { display: flex; align-items: center; justify-content: space-between; padding: 0 1.4rem 0.9rem; }
    .table-head h3 { margin: 0; font-size: 1.12rem; }
    .link { color: var(--purple); font-weight: 600; font-size: 0.9rem; text-decoration: none; cursor: pointer; background: none; border: none; font-family: inherit; }
    .tscroll { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; min-width: 620px; }
    thead th { text-align: left; padding: 0.7rem 1rem; color: var(--muted); font-weight: 600; font-size: 0.82rem; border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); background: #fafbfc; }
    thead th:first-child { padding-left: 1.4rem; }
    tbody td { padding: 0.85rem 1rem; border-bottom: 1px solid var(--border); vertical-align: middle; }
    tbody td:first-child { padding-left: 1.4rem; color: var(--faint); font-variant-numeric: tabular-nums; }
    tbody tr { cursor: pointer; }
    tbody tr:hover { background: #fafafe; }
    .cell-name { display: flex; align-items: center; gap: 0.7rem; }
    .cell-name .avatar { width: 34px; height: 34px; font-size: 0.78rem; }
    .cell-name .nm { font-weight: 600; }
    .pill { display: inline-block; padding: 4px 12px; border-radius: 9999px; font-size: 0.78rem; font-weight: 600; }
    .pill-good { background: var(--good-bg); color: var(--good-fg); }
    .pill-new  { background: var(--new-bg);  color: var(--new-fg); }
    .pill-warn { background: var(--warn-bg); color: var(--warn-fg); }
    .pill-bad  { background: var(--bad-bg);  color: var(--bad-fg); }
    .pill-gray { background: var(--gray-bg); color: var(--gray-fg); }
    .kebab { background: none; border: none; color: var(--faint); cursor: pointer; font-size: 1.1rem; padding: 0 0.4rem; }
    .val { font-weight: 650; font-variant-numeric: tabular-nums; }

    /* bottom banner */
    .banner { margin-top: 1.3rem; background: linear-gradient(100deg, var(--purple-100), #e0e7ff); border-radius: var(--radius); padding: 1.4rem 1.6rem; display: flex; align-items: center; gap: 1.2rem; flex-wrap: wrap; }
    .banner .bico { width: 54px; height: 54px; border-radius: 14px; background: #fff; display: grid; place-items: center; font-size: 1.5rem; flex: none; box-shadow: 0 4px 12px rgba(124,58,237,.18); }
    .banner .btxt { flex: 1; min-width: 220px; }
    .banner h4 { margin: 0 0 0.25rem; font-size: 1.1rem; }
    .banner p { margin: 0; color: #4b5563; font-size: 0.9rem; }

    .btn { border: none; border-radius: 11px; padding: 0.7rem 1.3rem; font-weight: 650; font-size: 0.9rem; cursor: pointer; font-family: inherit; background: var(--purple); color: #fff; box-shadow: 0 6px 16px rgba(124,58,237,.3); transition: all .15s; }
    .btn:hover { background: var(--purple-600); transform: translateY(-1px); }
    .btn.block { width: 100%; }
    .btn.small { padding: 0.45rem 0.9rem; font-size: 0.82rem; }
    .btn.secondary { background: #fff; color: var(--purple-600); border: 1px solid var(--purple-100); box-shadow: none; }
    .run-status { color: var(--muted); font-size: 0.85rem; margin: 0.8rem 0 0; }
    .muted { color: var(--muted); font-size: 0.9rem; }
    .empty { color: var(--faint); font-size: 0.9rem; padding: 1rem 1.4rem; }
    .subpage { display: none; }
    .subpage .panel { margin-bottom: 1.3rem; }

    /* demo modal */
    #modal { position: fixed; inset: 0; background: rgba(17,24,39,.5); backdrop-filter: blur(3px); display: none; align-items: center; justify-content: center; z-index: 70; padding: 1rem; }
    #modal.open { display: flex; }
    .modal-card { background: var(--card); border-radius: var(--radius); width: min(880px, 96vw); max-height: 92vh; overflow: hidden; display: flex; flex-direction: column; }
    .modal-head { display: flex; align-items: center; justify-content: space-between; padding: 1rem 1.3rem; border-bottom: 1px solid var(--border); }
    .modal-head h3 { margin: 0; font-size: 1.05rem; }
    .modal-body { padding: 1.1rem 1.3rem; overflow: auto; }
    .device-toggle { display: flex; gap: 0.4rem; margin-bottom: 0.85rem; }
    .device-toggle button { padding: 0.34rem 0.85rem; border-radius: 9999px; border: 1px solid var(--border-2); background: #fff; color: var(--muted); cursor: pointer; font-size: 0.78rem; }
    .device-toggle button.active { background: var(--purple); color: #fff; border-color: var(--purple); }
    .preview-frame-wrap { display: flex; justify-content: center; }
    iframe#demo-preview { border: 1px solid var(--border); border-radius: 12px; width: 100%; height: 520px; background: #fff; }

    /* chat */
    #chat-toggle { position: fixed; bottom: 22px; right: 22px; width: 54px; height: 54px; border-radius: 50%; background: var(--purple); color: #fff; border: none; font-size: 1.3rem; cursor: pointer; box-shadow: 0 8px 24px rgba(124,58,237,.4); z-index: 60; }
    #chat-panel { position: fixed; bottom: 86px; right: 22px; width: 340px; max-height: 480px; background: var(--card); border: 1px solid var(--border-2); border-radius: var(--radius); z-index: 60; display: none; flex-direction: column; overflow: hidden; box-shadow: 0 18px 50px rgba(16,24,40,.25); }
    #chat-panel.open { display: flex; }
    #chat-header { padding: 0.8rem 1rem; font-weight: 600; font-size: 0.9rem; border-bottom: 1px solid var(--border); background: var(--purple); color: #fff; }
    #chat-messages { flex: 1; overflow-y: auto; padding: 0.85rem 1rem; display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.85rem; }
    .chat-msg { padding: 0.5rem 0.75rem; border-radius: 13px; max-width: 86%; line-height: 1.45; }
    .chat-msg.user { align-self: flex-end; background: var(--purple); color: #fff; }
    .chat-msg.bot { align-self: flex-start; background: #f1f0f7; color: var(--text); }
    #chat-input-row { display: flex; border-top: 1px solid var(--border); }
    #chat-input { flex: 1; border: none; background: transparent; color: var(--text); padding: 0.8rem; font-size: 0.85rem; font-family: inherit; }
    #chat-send { border: none; background: var(--purple); color: #fff; padding: 0 1.1rem; cursor: pointer; font-family: inherit; }

    :focus-visible { outline: 2px solid var(--purple); outline-offset: 2px; }

    /* ---------- responsive ---------- */
    @media (max-width: 1050px) { .kpis { grid-template-columns: repeat(2, 1fr); } .charts { grid-template-columns: 1fr; } }
    @media (max-width: 820px) {
      .app { grid-template-columns: 1fr; }
      .sidebar { position: static; height: auto; flex-direction: row; align-items: center; gap: 0.5rem; overflow-x: auto; padding: 0.7rem 0.9rem; }
      .logo { padding: 0 0.5rem; font-size: 1rem; }
      .nav { flex-direction: row; gap: 0.2rem; }
      .nav button { padding: 0.45rem 0.7rem; white-space: nowrap; }
      .nav .ico { display: none; }
      .side-spacer, .promo, .profile { display: none; }
      .main { padding: 1.2rem 1rem 3rem; }
    }
    @media (max-width: 520px) { .kpis { grid-template-columns: 1fr 1fr; gap: 0.8rem; } .topbar h1 { font-size: 1.4rem; } }
  </style>
</head>
<body>
  <div style="background:#111;color:#e5e7eb;font-size:.78rem;text-align:center;padding:.5rem 1rem;">
    <strong style="color:#a78bfa;">Preview</strong> &middot; sample data, no live backend &mdash; exactly how this looks &amp; behaves once <code>fastapi_backend</code> is running.
  </div>
  <div class="app">
    <!-- ==================== SIDEBAR ==================== -->
    <aside class="sidebar">
      <div class="logo"><span class="mark">◆</span> Obsidian Labs</div>
      <nav class="nav" id="nav">
        <button data-page="dashboard" class="active"><span class="ico">▦</span> Dashboard</button>
        <button data-page="leads"><span class="ico">☰</span> Leads</button>
        <button data-page="demos"><span class="ico">▤</span> Demos</button>
        <button data-page="outreach"><span class="ico">✉</span> Outreach</button>
        <button data-page="dashboard"><span class="ico">◔</span> Analytics</button>
        <button id="nav-settings"><span class="ico">⚙</span> Settings</button>
      </nav>
      <div class="side-spacer"></div>
      <div class="promo">
        <div class="rocket">🚀</div>
        <h4>Grow your pipeline</h4>
        <p>Gather new local businesses and build demos automatically — 100% local.</p>
        <button class="btn block" id="promo-run">Run Pipeline</button>
      </div>
      <div class="profile">
        <div class="avatar" style="background:#7c3aed;">RC</div>
        <div class="who">Robert Castro<small>themortgagemaster01@gmail.com</small></div>
      </div>
    </aside>

    <!-- ==================== MAIN ==================== -->
    <main class="main">
      <div class="topbar">
        <div>
          <h1>Dashboard</h1>
          <p class="sub">Welcome back, Robert! Here's what's happening with your leads.</p>
        </div>
        <div class="top-actions">
          <button class="chip" id="range-chip">📅 <span id="range-label">This month</span></button>
          <button class="icon-btn" id="settings-btn" title="Settings / backend URL">🔔<span class="badge"></span></button>
        </div>
      </div>

      <!-- ===== DASHBOARD PAGE ===== -->
      <section id="page-dashboard">
        <!-- KPI cards -->
        <div class="kpis">
          <div class="card kpi">
            <div class="kico p">👥</div>
            <div class="klabel">Total Leads</div>
            <div class="kvalue" id="k-leads">–</div>
            <div class="kdelta flat" id="d-leads">—</div>
            <div class="kspark" id="s-leads"></div>
          </div>
          <div class="card kpi">
            <div class="kico b">🎯</div>
            <div class="klabel">Hot Leads</div>
            <div class="kvalue" id="k-hot">–</div>
            <div class="kdelta flat" id="d-hot">—</div>
            <div class="kspark" id="s-hot"></div>
          </div>
          <div class="card kpi">
            <div class="kico t">📤</div>
            <div class="klabel">Demos Generated</div>
            <div class="kvalue" id="k-demos">–</div>
            <div class="kdelta flat" id="d-demos">—</div>
            <div class="kspark" id="s-demos"></div>
          </div>
          <div class="card kpi">
            <div class="kico o">📝</div>
            <div class="klabel">Outreach Drafts</div>
            <div class="kvalue" id="k-drafts">–</div>
            <div class="kdelta flat" id="d-drafts">—</div>
            <div class="kspark" id="s-drafts"></div>
          </div>
        </div>

        <!-- charts -->
        <div class="charts">
          <div class="card panel area-wrap">
            <div class="panel-head">
              <h3>Lead Growth</h3>
              <select class="range" id="growth-range">
                <option value="8">This Month</option>
                <option value="30">Last 30 pts</option>
                <option value="5">Last 5 pts</option>
              </select>
            </div>
            <div id="area-chart"></div>
          </div>
          <div class="card panel">
            <div class="panel-head"><h3>Leads by Niche</h3></div>
            <div class="donut-wrap">
              <div id="donut-chart"></div>
              <div class="legend" id="donut-legend"></div>
            </div>
          </div>
        </div>

        <p class="run-status" id="run-status">Click a lead to preview its generated demo site.</p>

        <!-- recent leads -->
        <div class="card table-card">
          <div class="table-head">
            <h3>Recent Leads</h3>
            <button class="link" data-goto="leads">View all leads</button>
          </div>
          <div class="tscroll">
            <table>
              <thead><tr><th>#</th><th>Name</th><th>Niche</th><th>Status</th><th>Town</th><th>Value</th><th></th></tr></thead>
              <tbody id="recent-tbody"><tr><td colspan="7" class="empty">Loading…</td></tr></tbody>
            </table>
          </div>
        </div>

        <!-- bottom banner -->
        <div class="banner">
          <div class="bico">🎯</div>
          <div class="btxt">
            <h4>Turn hot leads into revenue</h4>
            <p>Approve a demo and its outreach draft, then send it yourself. Nothing here ever auto-sends.</p>
          </div>
          <button class="btn" id="banner-run">Run Pipeline</button>
        </div>
      </section>

      <!-- ===== LEADS PAGE ===== -->
      <section id="page-leads" class="subpage">
        <div class="card table-card">
          <div class="table-head"><h3>All Leads</h3></div>
          <div class="tscroll">
            <table>
              <thead><tr><th>#</th><th>Name</th><th>Niche</th><th>Status</th><th>Town</th><th>Value</th><th></th></tr></thead>
              <tbody id="all-tbody"><tr><td colspan="7" class="empty">Loading…</td></tr></tbody>
            </table>
          </div>
        </div>
      </section>

      <!-- ===== DEMOS PAGE ===== -->
      <section id="page-demos" class="subpage">
        <div class="card panel"><div class="panel-head"><h3>Demos</h3></div><div id="demos-list" class="muted">Loading…</div></div>
      </section>

      <!-- ===== OUTREACH PAGE ===== -->
      <section id="page-outreach" class="subpage">
        <div class="card panel">
          <div class="panel-head"><h3>Outreach Drafts</h3></div>
          <p class="muted">Drafts only — approving here just logs the approval. Sending is a separate, deliberate step outside this dashboard.</p>
          <div id="outreach-list" class="muted">Loading…</div>
        </div>
      </section>
    </main>
  </div>

  <!-- demo preview modal -->
  <div id="modal">
    <div class="modal-card">
      <div class="modal-head"><h3 id="modal-title">Demo preview</h3><button class="kebab" id="modal-close" style="font-size:1.4rem;">✕</button></div>
      <div class="modal-body">
        <div class="device-toggle">
          <button data-device="Desktop" class="active">Desktop</button>
          <button data-device="Tablet">Tablet</button>
          <button data-device="Mobile">Mobile</button>
        </div>
        <div class="preview-frame-wrap">
          <iframe id="demo-preview" title="Demo site preview"></iframe>
        </div>
      </div>
    </div>
  </div>

  <!-- chat -->
  <button id="chat-toggle" title="Ask the Obsidian Labs assistant">💬</button>
  <div id="chat-panel">
    <div id="chat-header">Obsidian Labs Assistant</div>
    <div id="chat-messages"></div>
    <div id="chat-input-row">
      <input id="chat-input" type="text" placeholder="Ask about your pipeline…" />
      <button id="chat-send">Send</button>
    </div>
  </div>

  <script>
    /* =================================================================
       Config
       ================================================================= */
    function getApiBase() { return localStorage.getItem("obsidian_api_base") || "http://localhost:8502"; }
    function setApiBase(url) { localStorage.setItem("obsidian_api_base", url.replace(/\/$/, "")); }
    function getRevPer() { return Number(localStorage.getItem("obsidian_rev_per")) || 2500; }
    function setRevPer(v) { localStorage.setItem("obsidian_rev_per", String(v)); }

    let API_BASE = getApiBase();
    let leadsCache = [];
    let currentSlug = null;
    let currentDevice = "Desktop";
    let currentDemoHtml = "";

    const NICHE_COLORS = ["#7c3aed", "#3b82f6", "#14b8a6", "#f59e0b", "#ec4899", "#94a3b8"];

    /* ---------- helpers ---------- */
    function money(n) { return "$" + Math.round(n).toLocaleString("en-US"); }
    function slugify(name) { return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "lead"; }
    function isHot(l) { return String(l.is_hot_lead).toLowerCase() === "true"; }
    function initials(name) { return (name || "?").split(/\s+/).slice(0, 2).map(w => w[0] || "").join("").toUpperCase() || "?"; }
    function hashColor(s) { let h = 0; for (let i = 0; i < s.length; i++) h = s.charCodeAt(i) + ((h << 5) - h); return `hsl(${Math.abs(h) % 360} 55% 55%)`; }
    function statusPill(l) {
      const s = l.status, perf = Number(l.perf_score) || 0;
      if (s === "no_website") return ["No Website", "pill-bad"];
      if (s === "unreachable") return ["Unreachable", "pill-bad"];
      if (s === "api_error") return ["Grade Error", "pill-gray"];
      if (isHot(l)) return ["Hot", "pill-new"];
      if (perf <= 50) return ["Needs Work", "pill-warn"];
      return ["Healthy", "pill-good"];
    }

    /* ---------- PREVIEW: baked-in sample data, fully self-contained ---------- */
    const DEMO_A = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>*{margin:0;box-sizing:border-box;font-family:system-ui,sans-serif}.hero{background:linear-gradient(135deg,#0e7490,#155e75);color:#fff;padding:60px 26px;text-align:center}.hero h1{font-size:2rem}.hero p{opacity:.9;margin-top:10px}.cta{display:inline-block;margin-top:20px;background:#fff;color:#155e75;padding:12px 26px;border-radius:9999px;font-weight:700;text-decoration:none}.row{display:flex;flex-wrap:wrap;gap:14px;padding:32px 26px}.card{flex:1 1 200px;border:1px solid #e5e7eb;border-radius:14px;padding:18px}.card h3{color:#155e75}.card p{color:#6b7280;margin-top:8px;font-size:.9rem}.bar{background:#f1f5f9;padding:16px;text-align:center;color:#475569;font-size:.85rem}</style></head><body><div class="hero"><h1>Mahopac Family Dental</h1><p>Gentle, modern dentistry &mdash; now booking new patients.</p><a class="cta" href="#">Book an appointment</a></div><div class="row"><div class="card"><h3>Same-day visits</h3><p>Emergency slots every day.</p></div><div class="card"><h3>Insurance friendly</h3><p>We handle the paperwork.</p></div><div class="card"><h3>Kids welcome</h3><p>A calm team families trust.</p></div></div><div class="bar">123 Lake Blvd, Mahopac NY &middot; (845) 555-0142</div></body></html>`;
    const DEMO_B = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>*{margin:0;box-sizing:border-box;font-family:Georgia,serif}.hero{background:#1c1917;color:#fbbf24;padding:60px 26px;text-align:center}.hero h1{font-size:2.1rem;letter-spacing:.04em}.hero p{color:#e7e5e4;margin-top:10px;font-family:system-ui}.cta{display:inline-block;margin-top:20px;background:#fbbf24;color:#1c1917;padding:12px 26px;border-radius:6px;font-weight:700;text-decoration:none;font-family:system-ui}.svc{padding:32px 26px;max-width:520px;margin:0 auto}.svc div{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eee;font-family:system-ui}</style></head><body><div class="hero"><h1>SHEAR ELEGANCE</h1><p>Carmel&rsquo;s studio for cut, color &amp; style.</p><a class="cta" href="#">Reserve your chair</a></div><div class="svc"><div><span>Cut &amp; style</span><span>$65+</span></div><div><span>Full color</span><span>$120+</span></div><div><span>Balayage</span><span>$180+</span></div></div></body></html>`;
    const SAMPLE = {
      leads: [
        { name: "Mahopac Family Dental",   type: "dentist",     town: "Mahopac",  perf_score: 34, status: "graded",      is_hot_lead: "true"  },
        { name: "Summit Roofing Co",       type: "roofer",      town: "Carmel",   perf_score: 0,  status: "no_website",  is_hot_lead: "true"  },
        { name: "Lakeside Bistro",         type: "restaurant",  town: "Mahopac",  perf_score: 78, status: "graded",      is_hot_lead: "false" },
        { name: "Shear Elegance Salon",    type: "salon",       town: "Carmel",   perf_score: 45, status: "graded",      is_hot_lead: "true"  },
        { name: "Carmel Auto Care",        type: "auto shop",   town: "Carmel",   perf_score: 0,  status: "unreachable", is_hot_lead: "false" },
        { name: "Brewster Dental Group",   type: "dentist",     town: "Brewster", perf_score: 52, status: "graded",      is_hot_lead: "false" },
        { name: "Iron Peak Gym",           type: "gym",         town: "Mahopac",  perf_score: 41, status: "graded",      is_hot_lead: "true"  },
        { name: "Hudson Valley Roofing",   type: "roofer",      town: "Carmel",   perf_score: 0,  status: "no_website",  is_hot_lead: "false" },
        { name: "Bella Nails & Spa",       type: "salon",       town: "Mahopac",  perf_score: 63, status: "graded",      is_hot_lead: "false" },
        { name: "Tony's Auto Body",        type: "auto shop",   town: "Brewster", perf_score: 38, status: "graded",      is_hot_lead: "true"  },
        { name: "Green Thumb Landscaping", type: "landscaping", town: "Carmel",   perf_score: 55, status: "graded",      is_hot_lead: "false" },
        { name: "Corner Cafe",             type: "restaurant",  town: "Mahopac",  perf_score: 70, status: "graded",      is_hot_lead: "false" }
      ],
      demoHtml: { "mahopac-family-dental": DEMO_A, "shear-elegance-salon": DEMO_B, "iron-peak-gym": DEMO_A, "lakeside-bistro": DEMO_B },
      outreach: {
        "mahopac-family-dental": `Subject: Quick question about your Mahopac dentist website\n\nHi Dr. Alvarez,\n\nYour site loads slowly on phones and there's no easy "book online" button up top. I built a faster, mobile-first home page so you can see the difference.\n\nOur Starter site is a flat $1,495. Want me to send the preview link?\n\nBest,\nObsidian Labs`,
        "summit-roofing-co": `Subject: Summit Roofing — a website in a day\n\nHi Summit team,\n\nI noticed Summit Roofing doesn't have a website yet, so folks searching in Carmel land on competitors. I put together a clean one-pager with a quote request form.\n\nStarter build is $1,495, flat. Happy to send the demo — interested?\n\nBest,\nObsidian Labs`,
        "iron-peak-gym": `Subject: More sign-ups for Iron Peak Gym\n\nHi Iron Peak,\n\nYour current page hides your class schedule and pricing on mobile. I rebuilt the hero with a "Start free trial" button front and center.\n\nStarter site is $1,495. Want a look at the demo?\n\nBest,\nObsidian Labs`
      }
    };
    function computeStatus() {
      const hot = SAMPLE.leads.filter(l => String(l.is_hot_lead).toLowerCase() === "true").length;
      return { leads: SAMPLE.leads.length, hot_leads: hot, demos: Object.keys(SAMPLE.demoHtml).length, outreach_drafts: Object.keys(SAMPLE.outreach).length,
               pricing: { starter: 1495, professional: 2500, business_growth: "4500+" }, guardrails: "Runs 100% locally. Nothing auto-sends." };
    }
    function cannedChat(msg) {
      const m = (msg || "").toLowerCase();
      if (m.includes("hot")) return "You have 5 hot leads: Mahopac Family Dental, Summit Roofing, Shear Elegance Salon, Iron Peak Gym, and Tony's Auto Body. Summit and Hudson Valley have no site at all — easy first conversations.";
      if (m.includes("price") || m.includes("cost") || m.includes("revenue") || m.includes("value") || m.includes("$")) return "Pricing: Starter $1,495 / Professional $2,500 / Business Growth $4,500+. The Value column shows your price-per-deal for hot leads (tap the date chip to change it).";
      if (m.includes("send")) return "Nothing auto-sends. Approving only logs it — you send manually when ready.";
      return "This is a preview reply. Against the live backend I answer from your real pipeline stats via local Ollama.";
    }
    const SAMPLE_HISTORY = [
      { label: "May 12", leads: 3,  hot: 1, demos: 0, drafts: 0 },
      { label: "May 15", leads: 4,  hot: 1, demos: 1, drafts: 0 },
      { label: "May 19", leads: 6,  hot: 2, demos: 1, drafts: 1 },
      { label: "May 22", leads: 7,  hot: 2, demos: 2, drafts: 1 },
      { label: "May 26", leads: 8,  hot: 3, demos: 2, drafts: 2 },
      { label: "May 29", leads: 9,  hot: 3, demos: 3, drafts: 2 },
      { label: "Jun 2",  leads: 10, hot: 4, demos: 3, drafts: 3 },
      { label: "Jun 5",  leads: 11, hot: 4, demos: 4, drafts: 3 },
      { label: "Jun 9",  leads: 12, hot: 5, demos: 4, drafts: 3 }
    ];
    async function apiGet(path) {
      await new Promise(r => setTimeout(r, 80));
      if (path === "/api/status") return computeStatus();
      if (path === "/api/leads") return SAMPLE.leads;
      if (path === "/api/demos") return Object.keys(SAMPLE.demoHtml).map(s => ({ slug: s }));
      if (path.startsWith("/api/demos/")) { const s = decodeURIComponent(path.split("/").pop()); if (SAMPLE.demoHtml[s]) return { slug: s, html: SAMPLE.demoHtml[s] }; throw new Error(`${path} -> 404`); }
      if (path === "/api/outreach") return Object.keys(SAMPLE.outreach).map(s => ({ slug: s }));
      if (path.startsWith("/api/outreach/")) { const s = decodeURIComponent(path.split("/").pop()); return { slug: s, content: SAMPLE.outreach[s] || "" }; }
      throw new Error(`${path} -> 404`);
    }
    async function apiPost(path, body) {
      await new Promise(r => setTimeout(r, 120));
      if (path === "/api/chat") return { reply: cannedChat((body || {}).message) };
      if (path === "/api/approve") return { status: "logged", ...(body || {}) };
      if (path === "/api/run-pipeline") return { status: "started" };
      return {};
    }
    function getHistory() { return SAMPLE_HISTORY; }
    function pushHistory() { return SAMPLE_HISTORY; }

    /* ================= SVG chart helpers ================= */
    function smoothPath(pts) {
      if (pts.length < 2) return pts.length ? `M${pts[0].x},${pts[0].y}` : "";
      let d = `M${pts[0].x},${pts[0].y}`;
      for (let i = 0; i < pts.length - 1; i++) {
        const p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
        const c1x = p1.x + (p2.x - p0.x) / 6, c1y = p1.y + (p2.y - p0.y) / 6;
        const c2x = p2.x - (p3.x - p1.x) / 6, c2y = p2.y - (p3.y - p1.y) / 6;
        d += ` C${c1x.toFixed(1)},${c1y.toFixed(1)} ${c2x.toFixed(1)},${c2y.toFixed(1)} ${p2.x},${p2.y}`;
      }
      return d;
    }
    function drawSpark(elId, values, color) {
      const el = document.getElementById(elId);
      if (!values || values.length < 2) { el.innerHTML = `<svg viewBox="0 0 100 34" preserveAspectRatio="none"></svg>`; return; }
      const W = 100, H = 34, min = Math.min(...values), max = Math.max(...values), rng = (max - min) || 1;
      const pts = values.map((v, i) => ({ x: (i / (values.length - 1)) * W, y: H - 3 - ((v - min) / rng) * (H - 8) }));
      const line = smoothPath(pts);
      const gid = "g_" + elId;
      el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
        <defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stop-color="${color}" stop-opacity=".25"/><stop offset="1" stop-color="${color}" stop-opacity="0"/>
        </linearGradient></defs>
        <path d="${line} L${W},${H} L0,${H} Z" fill="url(#${gid})"/>
        <path d="${line}" fill="none" stroke="${color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`;
    }
    function niceMax(v) { if (v <= 5) return 5; const p = Math.pow(10, Math.floor(Math.log10(v))); const f = v / p; const n = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10; return n * p; }
    function drawArea(elId, hist, count) {
      const el = document.getElementById(elId);
      const data = hist.slice(-count);
      if (data.length < 2) { el.innerHTML = `<div class="empty" style="padding:2.5rem 0;text-align:center;">Growth appears here as the dashboard records snapshots over time.<br>Run the pipeline a few times to fill it in.</div>`; return; }
      const W = 580, H = 240, padL = 34, padR = 12, padT = 16, padB = 26;
      const leads = data.map(d => d.leads), hot = data.map(d => d.hot);
      const maxY = niceMax(Math.max(...leads, 1));
      const xAt = i => padL + (i / (data.length - 1)) * (W - padL - padR);
      const yAt = v => padT + (1 - v / maxY) * (H - padT - padB);
      const mk = arr => arr.map((v, i) => ({ x: xAt(i), y: yAt(v) }));
      const lp = smoothPath(mk(leads)), hp = smoothPath(mk(hot));
      const base = H - padB;
      const grid = [0, .25, .5, .75, 1].map(f => { const y = padT + f * (H - padT - padB); const val = Math.round(maxY * (1 - f)); return `<line x1="${padL}" x2="${W - padR}" y1="${y}" y2="${y}" stroke="#eef0f3"/><text x="${padL - 6}" y="${y + 3}" text-anchor="end" font-size="10" fill="#9ca3af">${val}</text>`; }).join("");
      const step = Math.max(1, Math.ceil(data.length / 6));
      const xlabels = data.map((d, i) => (i % step === 0 || i === data.length - 1) ? `<text x="${xAt(i)}" y="${H - 6}" text-anchor="middle" font-size="10" fill="#9ca3af">${d.label || (i + 1)}</text>` : "").join("");
      const lastX = xAt(data.length - 1), lastY = yAt(leads[leads.length - 1]);
      el.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">
        <defs><linearGradient id="areaGrad" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#7c3aed" stop-opacity=".28"/><stop offset="1" stop-color="#7c3aed" stop-opacity="0"/></linearGradient></defs>
        ${grid}
        <path d="${lp} L${lastX},${base} L${padL},${base} Z" fill="url(#areaGrad)"/>
        <path d="${hp}" fill="none" stroke="#c4b5fd" stroke-width="2.5" stroke-linecap="round"/>
        <path d="${lp}" fill="none" stroke="#7c3aed" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="${lastX}" cy="${lastY}" r="5" fill="#7c3aed" stroke="#fff" stroke-width="2"/>
        <g><rect x="${Math.min(lastX - 26, W - 58)}" y="${Math.max(lastY - 34, 2)}" width="52" height="22" rx="6" fill="#fff" stroke="#e5e7eb"/><text x="${Math.min(lastX, W - 32)}" y="${Math.max(lastY - 19, 17)}" text-anchor="middle" font-size="11" font-weight="700" fill="#111827">${leads[leads.length - 1]}</text></g>
        ${xlabels}
      </svg>`;
    }
    function drawDonut(elId, legendId, segments) {
      const el = document.getElementById(elId), leg = document.getElementById(legendId);
      const total = segments.reduce((a, s) => a + s.value, 0);
      const R = 70, SW = 22, C = 2 * Math.PI * R, cx = 90, cy = 90;
      if (!total) { el.innerHTML = `<svg width="180" height="180"><circle cx="90" cy="90" r="${R}" fill="none" stroke="#eef0f3" stroke-width="${SW}"/></svg>`; leg.innerHTML = `<div class="empty">No leads yet.</div>`; return; }
      let off = 0;
      const arcs = segments.map(s => {
        const len = (s.value / total) * C;
        const seg = `<circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${s.color}" stroke-width="${SW}" stroke-dasharray="${len.toFixed(2)} ${(C - len).toFixed(2)}" stroke-dashoffset="${(-off).toFixed(2)}" transform="rotate(-90 ${cx} ${cy})"/>`;
        off += len; return seg;
      }).join("");
      el.innerHTML = `<svg width="180" height="180" viewBox="0 0 180 180">${arcs}
        <text x="90" y="86" text-anchor="middle" font-size="26" font-weight="750" fill="#111827">${total}</text>
        <text x="90" y="106" text-anchor="middle" font-size="12" fill="#9ca3af">Total</text></svg>`;
      leg.innerHTML = segments.map(s => {
        const pct = Math.round((s.value / total) * 100);
        return `<div class="legend-row"><span class="lname"><span class="swatch" style="background:${s.color}"></span>${s.label}</span><span class="lpct">${pct}%</span><span class="lval"><span class="swatch" style="background:${s.color}"></span>${s.value}</span></div>`;
      }).join("");
    }

    /* ================= data rendering ================= */
    function setDelta(elId, hist, key) {
      const el = document.getElementById(elId);
      if (hist.length < 2) { el.className = "kdelta flat"; el.textContent = "—"; return; }
      const prev = hist[hist.length - 2][key], now = hist[hist.length - 1][key];
      if (!prev) { el.className = "kdelta flat"; el.textContent = now ? "▲ new" : "—"; return; }
      const pct = ((now - prev) / prev) * 100, up = pct >= 0;
      el.className = "kdelta " + (Math.abs(pct) < 0.1 ? "flat" : up ? "up" : "down");
      el.textContent = `${up ? "▲" : "▼"} ${Math.abs(pct).toFixed(1)}% vs last run`;
    }
    async function loadStatus() {
      try {
        const s = await apiGet("/api/status");
        document.getElementById("k-leads").textContent = s.leads;
        document.getElementById("k-hot").textContent = s.hot_leads;
        document.getElementById("k-demos").textContent = s.demos;
        document.getElementById("k-drafts").textContent = s.outreach_drafts;
        const h = pushHistory(s);
        drawSpark("s-leads", h.map(x => x.leads), "#7c3aed");
        drawSpark("s-hot", h.map(x => x.hot), "#3b82f6");
        drawSpark("s-demos", h.map(x => x.demos), "#14b8a6");
        drawSpark("s-drafts", h.map(x => x.drafts), "#f59e0b");
        setDelta("d-leads", h, "leads"); setDelta("d-hot", h, "hot"); setDelta("d-demos", h, "demos"); setDelta("d-drafts", h, "drafts");
        drawArea("area-chart", h, Number(document.getElementById("growth-range").value));
      } catch (e) {
        document.getElementById("run-status").textContent = "Backend unreachable — is fastapi_backend running on :8502?";
      }
    }
    async function loadLeads() {
      try { leadsCache = await apiGet("/api/leads"); } catch (e) { leadsCache = []; }
      renderDonut();
      renderTable("recent-tbody", leadsCache.slice(0, 6));
      renderTable("all-tbody", leadsCache);
    }
    function renderDonut() {
      const counts = {};
      leadsCache.forEach(l => { const k = (l.type || "other").trim() || "other"; counts[k] = (counts[k] || 0) + 1; });
      const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
      const top = entries.slice(0, 5);
      const restVal = entries.slice(5).reduce((a, e) => a + e[1], 0);
      const segs = top.map((e, i) => ({ label: e[0].replace(/\b\w/g, c => c.toUpperCase()), value: e[1], color: NICHE_COLORS[i] }));
      if (restVal) segs.push({ label: "Other", value: restVal, color: NICHE_COLORS[5] });
      drawDonut("donut-chart", "donut-legend", segs);
    }
    function rowHTML(l, i) {
      const [label, cls] = statusPill(l);
      const val = isHot(l) ? money(getRevPer()) : "—";
      return `<tr data-slug="${slugify(l.name)}">
        <td>${i + 1}</td>
        <td><div class="cell-name"><span class="avatar" style="background:${hashColor(l.name || "")}">${initials(l.name)}</span><span class="nm">${l.name || ""}</span></div></td>
        <td>${(l.type || "").replace(/\b\w/g, c => c.toUpperCase())}</td>
        <td><span class="pill ${cls}">${label}</span></td>
        <td>${l.town || "—"}</td>
        <td class="val">${val}</td>
        <td><button class="kebab" title="Preview demo">⋮</button></td>
      </tr>`;
    }
    function renderTable(tbodyId, rows) {
      const tb = document.getElementById(tbodyId);
      if (!rows.length) { tb.innerHTML = `<tr><td colspan="7" class="empty">No leads yet. Run the pipeline to gather some.</td></tr>`; return; }
      tb.innerHTML = rows.map((l, i) => rowHTML(l, i)).join("");
      tb.querySelectorAll("tr[data-slug]").forEach(tr => tr.addEventListener("click", () => openDemo(tr.dataset.slug)));
    }

    /* ---------- demo modal ---------- */
    async function openDemo(slug) {
      currentSlug = slug;
      document.getElementById("modal-title").textContent = slug;
      document.getElementById("modal").classList.add("open");
      const iframe = document.getElementById("demo-preview");
      iframe.srcdoc = `<p style="font-family:system-ui;color:#999;padding:2rem;">Loading…</p>`;
      try { const demo = await apiGet(`/api/demos/${slug}`); currentDemoHtml = demo.html; renderPreview(); }
      catch (e) { currentDemoHtml = ""; iframe.srcdoc = `<p style="font-family:system-ui;color:#999;padding:2rem;">No demo generated yet for “${slug}”. Run the pipeline to build one.</p>`; }
    }
    function renderPreview() {
      const widths = { Desktop: "100%", Tablet: "768px", Mobile: "390px" };
      const iframe = document.getElementById("demo-preview");
      iframe.style.width = widths[currentDevice]; iframe.style.margin = currentDevice === "Desktop" ? "0" : "0 auto";
      if (currentDemoHtml) iframe.srcdoc = currentDemoHtml;
    }
    document.querySelectorAll(".device-toggle button").forEach(b => b.addEventListener("click", () => {
      document.querySelectorAll(".device-toggle button").forEach(x => x.classList.remove("active"));
      b.classList.add("active"); currentDevice = b.dataset.device; renderPreview();
    }));
    document.getElementById("modal-close").addEventListener("click", () => document.getElementById("modal").classList.remove("open"));
    document.getElementById("modal").addEventListener("click", e => { if (e.target.id === "modal") document.getElementById("modal").classList.remove("open"); });

    /* ---------- demos + outreach pages ---------- */
    async function loadDemos() {
      const el = document.getElementById("demos-list");
      try { const d = await apiGet("/api/demos"); el.innerHTML = d.length ? d.map(x => `<div class="legend-row" style="grid-template-columns:1fr auto;padding:.6rem 0;border-bottom:1px solid var(--border);cursor:pointer" data-slug="${x.slug}"><strong>${x.slug}</strong><button class="btn small secondary">Preview</button></div>`).join("") : `<div class="empty">No demos generated yet.</div>`; el.querySelectorAll("[data-slug]").forEach(r => r.addEventListener("click", () => openDemo(r.dataset.slug))); }
      catch (e) { el.innerHTML = `<div class="empty">Backend unreachable.</div>`; }
    }
    async function loadOutreach() {
      const el = document.getElementById("outreach-list");
      try {
        const drafts = await apiGet("/api/outreach");
        if (!drafts.length) { el.innerHTML = `<div class="empty">No outreach drafts yet.</div>`; return; }
        let html = "";
        for (const d of drafts) { const full = await apiGet(`/api/outreach/${d.slug}`); html += `<div class="card panel" style="margin-bottom:.8rem"><strong>${d.slug}</strong><pre style="white-space:pre-wrap;font-family:inherit;font-size:.85rem;color:#374151;line-height:1.5;margin:.6rem 0 .8rem">${full.content.replace(/</g, "&lt;")}</pre><button class="btn small" data-approve="${d.slug}">Approve</button></div>`; }
        el.innerHTML = html;
        el.querySelectorAll("[data-approve]").forEach(b => b.addEventListener("click", async () => { await apiPost("/api/approve", { kind: "outreach_approved", identifier: b.dataset.approve }); b.textContent = "Approved ✓"; b.disabled = true; }));
      } catch (e) { el.innerHTML = `<div class="empty">Backend unreachable.</div>`; }
    }

    /* ---------- navigation ---------- */
    function goToPage(page) {
      document.querySelectorAll("#nav button[data-page]").forEach(b => b.classList.toggle("active", b.dataset.page === page));
      ["dashboard", "leads", "demos", "outreach"].forEach(p => { document.getElementById(`page-${p}`).style.display = p === page ? "" : "none"; });
      if (page === "demos") loadDemos();
      if (page === "outreach") loadOutreach();
    }
    document.querySelectorAll("#nav button[data-page]").forEach(b => b.addEventListener("click", () => goToPage(b.dataset.page)));
    document.querySelectorAll("[data-goto]").forEach(b => b.addEventListener("click", () => goToPage(b.dataset.goto)));
    document.getElementById("growth-range").addEventListener("change", () => drawArea("area-chart", getHistory(), Number(document.getElementById("growth-range").value)));

    /* ---------- run pipeline ---------- */
    async function runPipeline() {
      const st = document.getElementById("run-status"); st.textContent = "Starting pipeline in the background…";
      try { await apiPost("/api/run-pipeline", { stage: "all", towns: ["Mahopac", "Carmel"], niches: ["dentist", "roofer"], limit: 5 }); st.textContent = "Pipeline started. Check output/logs/pipeline_run.log, or refresh shortly."; }
      catch (e) { st.textContent = "Failed to start — is the backend running?"; }
    }
    document.getElementById("promo-run").addEventListener("click", runPipeline);
    document.getElementById("banner-run").addEventListener("click", runPipeline);

    /* ---------- settings (backend URL + price per deal) ---------- */
    function openSettings() {
      alert("In the live dashboard this opens your backend URL setting (ngrok https address, or http://localhost:8502). In this preview the data is built-in.");
    }
    document.getElementById("settings-btn").addEventListener("click", openSettings);
    document.getElementById("nav-settings").addEventListener("click", openSettings);
    document.getElementById("range-chip").addEventListener("click", () => {
      const cur = getRevPer(); const n = Number((prompt("Average price per closed deal (used for the Value column):", cur) || "").replace(/[^0-9.]/g, ""));
      if (n > 0) { setRevPer(n); renderTable("recent-tbody", leadsCache.slice(0, 6)); renderTable("all-tbody", leadsCache); }
    });

    /* ---------- chat ---------- */
    const chatPanel = document.getElementById("chat-panel"), chatMessages = document.getElementById("chat-messages"), chatInput = document.getElementById("chat-input");
    document.getElementById("chat-toggle").addEventListener("click", () => chatPanel.classList.toggle("open"));
    function addChatMsg(t, who) { const d = document.createElement("div"); d.className = `chat-msg ${who}`; d.textContent = t; chatMessages.appendChild(d); chatMessages.scrollTop = chatMessages.scrollHeight; }
    async function sendChat() {
      const msg = chatInput.value.trim(); if (!msg) return;
      addChatMsg(msg, "user"); chatInput.value = ""; addChatMsg("Thinking…", "bot");
      try { const res = await apiPost("/api/chat", { message: msg }); chatMessages.lastChild.textContent = res.reply || "(no response)"; }
      catch (e) { chatMessages.lastChild.textContent = "Couldn't reach the assistant — is fastapi_backend + Ollama running?"; }
    }
    document.getElementById("chat-send").addEventListener("click", sendChat);
    chatInput.addEventListener("keydown", e => { if (e.key === "Enter") sendChat(); });

    /* ---------- PWA + boot ---------- */
    /* PWA registration omitted in preview */
    function refreshAll() { loadStatus(); loadLeads(); }
    addChatMsg("Hi! I'm your pipeline assistant. Ask about your hot leads, drafts, or pricing.", "bot");
    refreshAll();
    setInterval(loadStatus, 15000);
  </script>
</body>
</html>

```

## `dashboard_v2_preview.html`  
_(746 lines)_

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Obsidian Labs — Mission Control (Preview)</title>
  <meta name="theme-color" content="#0b0b0b" />
  <style>
    /* ============================================================
       Obsidian Labs v2 — dark, Tesla/Apple-inspired glassmorphism.
       Single self-contained file. Talks to the SAME fastapi_backend
       on :8502 — no backend changes. Deliberately dark, single-world.
       ============================================================ */
    :root {
      --bg: #0b0b0b;
      --panel: rgba(255,255,255,.045);
      --panel-hover: rgba(255,255,255,.07);
      --border: rgba(255,255,255,.09);
      --border-strong: rgba(255,255,255,.16);
      --accent: #3b82f6;
      --accent-soft: rgba(59,130,246,.16);
      --accent-glow: rgba(59,130,246,.45);
      --text: #f5f5f7;
      --muted: #99a1af;      /* blue-biased neutral, chosen not defaulted */
      --faint: #6b7280;
      --good: #22c55e;
      --warn: #f59e0b;
      --bad:  #ef4444;
      --gray: #6b7280;
      --radius: 18px;
      --radius-sm: 12px;
    }
    * { box-sizing: border-box; }
    html, body { height: 100%; }
    body {
      margin: 0;
      color: var(--text);
      background: radial-gradient(1200px 700px at 50% -15%, #16181d 0%, #0b0b0b 45%, #000 100%);
      background-attachment: fixed;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
      -webkit-font-smoothing: antialiased;
      letter-spacing: -0.01em;
    }
    a { color: inherit; }
    .wrap { max-width: 1360px; margin: 0 auto; padding: 1.1rem 1.5rem 5rem; }

    /* ---------- header ---------- */
    .topbar {
      display: flex; align-items: center; gap: 1rem; flex-wrap: wrap;
      padding: 0.4rem 0 1.2rem;
    }
    .brand { display: flex; align-items: center; gap: 0.6rem; font-weight: 650; font-size: 1.05rem; }
    .brand .mark {
      width: 26px; height: 26px; border-radius: 8px;
      background: linear-gradient(150deg, var(--accent), #1e40af);
      box-shadow: 0 0 18px var(--accent-glow);
      display: grid; place-items: center;
    }
    .brand .mark::after { content: ""; width: 9px; height: 9px; background: #fff; border-radius: 2px; }
    .navtabs { display: flex; gap: 0.2rem; background: var(--panel); border: 1px solid var(--border);
      border-radius: 9999px; padding: 4px; }
    .navtabs button {
      background: none; border: none; color: var(--muted); font-weight: 550; font-size: 0.86rem;
      padding: 0.42rem 0.95rem; border-radius: 9999px; cursor: pointer; transition: all .18s;
    }
    .navtabs button:hover { color: var(--text); }
    .navtabs button.active { background: var(--text); color: #0b0b0b; }
    .spacer { flex: 1; }
    .ghost-btn {
      display: inline-flex; align-items: center; gap: 0.5rem;
      background: var(--panel); border: 1px solid var(--border); color: var(--muted);
      border-radius: 10px; padding: 0.42rem 0.7rem; font-size: 0.8rem; cursor: pointer; transition: all .18s;
    }
    .ghost-btn:hover { color: var(--text); border-color: var(--border-strong); background: var(--panel-hover); }
    kbd {
      font-family: inherit; font-size: 0.72rem; background: rgba(255,255,255,.08);
      border: 1px solid var(--border); border-radius: 5px; padding: 1px 6px;
    }

    /* ---------- glass card ---------- */
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      backdrop-filter: blur(18px) saturate(120%);
      -webkit-backdrop-filter: blur(18px) saturate(120%);
      box-shadow: 0 1px 0 rgba(255,255,255,.04) inset, 0 12px 40px rgba(0,0,0,.35);
    }
    .card.pad { padding: 1.35rem 1.4rem; }
    .card h2 { margin: 0 0 1rem; font-size: 1rem; font-weight: 600; letter-spacing: -0.02em; }

    /* ---------- hero: ring + KPIs ---------- */
    .hero { display: grid; grid-template-columns: 300px 1fr; gap: 1.2rem; margin-bottom: 1.2rem; }
    .ring-card { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.9rem; text-align: center; }
    .ring {
      position: relative; width: 168px; height: 168px; border-radius: 50%;
      display: grid; place-items: center;
      border: 8px solid var(--accent-soft);
      box-shadow: 0 0 30px var(--accent-glow), inset 0 0 26px rgba(59,130,246,.12);
      animation: pulse 2.6s infinite ease-in-out;
    }
    .ring.offline { border-color: rgba(239,68,68,.18); box-shadow: 0 0 26px rgba(239,68,68,.4), inset 0 0 24px rgba(239,68,68,.1); animation: none; }
    .ring .ring-num { font-size: 2.5rem; font-weight: 700; line-height: 1; letter-spacing: -0.03em; font-variant-numeric: tabular-nums; }
    .ring .ring-lbl { font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.14em; margin-top: 4px; }
    .ring-status { font-size: 0.82rem; color: var(--muted); display: inline-flex; align-items: center; gap: 0.45rem; }
    .dot { width: 8px; height: 8px; border-radius: 50%; background: var(--good); box-shadow: 0 0 8px var(--good); }
    .dot.bad { background: var(--bad); box-shadow: 0 0 8px var(--bad); }
    @keyframes pulse { 50% { box-shadow: 0 0 52px var(--accent-glow), inset 0 0 26px rgba(59,130,246,.2); } }
    @media (prefers-reduced-motion: reduce) { .ring { animation: none; } }

    .kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; }
    .kpi { padding: 1.15rem 1.2rem; cursor: default; }
    .kpi .label { font-size: 0.76rem; color: var(--muted); letter-spacing: 0.02em; }
    .kpi .value { font-size: 1.95rem; font-weight: 700; letter-spacing: -0.03em; margin-top: 0.35rem; font-variant-numeric: tabular-nums; }
    .kpi .sub { font-size: 0.74rem; color: var(--faint); margin-top: 0.3rem; }
    .kpi.revenue { grid-column: span 1; cursor: pointer; position: relative; }
    .kpi.revenue .value { color: var(--accent); }
    .kpi.revenue:hover { border-color: var(--border-strong); }
    .kpi.accent { background: linear-gradient(160deg, rgba(59,130,246,.12), rgba(59,130,246,.02)); }

    /* ---------- buttons ---------- */
    .btn {
      border: none; border-radius: 11px; padding: 0.62rem 1.3rem; font-weight: 600; font-size: 0.88rem;
      cursor: pointer; transition: all .16s; font-family: inherit;
      background: var(--accent); color: #fff; box-shadow: 0 6px 20px rgba(59,130,246,.35);
    }
    .btn:hover { filter: brightness(1.08); transform: translateY(-1px); }
    .btn.secondary { background: var(--panel); color: var(--text); border: 1px solid var(--border); box-shadow: none; }
    .btn.secondary:hover { background: var(--panel-hover); border-color: var(--border-strong); }
    .btn:disabled { opacity: .4; cursor: not-allowed; transform: none; filter: none; }
    .btn.small { padding: 0.4rem 0.9rem; font-size: 0.8rem; }

    .actionrow { display: flex; align-items: center; gap: 0.7rem; flex-wrap: wrap; margin-bottom: 1.2rem; }
    .run-status { color: var(--muted); font-size: 0.83rem; margin: 0 0 0 0.2rem; }

    /* ---------- main grid ---------- */
    .two-col { display: grid; grid-template-columns: 1.05fr 1.35fr; gap: 1.2rem; }

    /* lead cards */
    .lead-list { display: flex; flex-direction: column; gap: 0.6rem; }
    .lead-item {
      display: grid; grid-template-columns: 1fr auto; gap: 0.4rem 0.8rem; align-items: center;
      padding: 0.8rem 0.95rem; border-radius: var(--radius-sm);
      border: 1px solid var(--border); background: rgba(255,255,255,.02); cursor: pointer; transition: all .16s;
    }
    .lead-item:hover { background: var(--panel-hover); border-color: var(--border-strong); transform: translateX(2px); }
    .lead-item.selected { border-color: var(--accent); background: var(--accent-soft); }
    .lead-name { font-weight: 600; font-size: 0.92rem; }
    .lead-meta { font-size: 0.76rem; color: var(--muted); margin-top: 2px; }
    .lead-right { display: flex; align-items: center; gap: 0.6rem; }
    .score { font-variant-numeric: tabular-nums; font-weight: 600; font-size: 0.9rem; color: var(--muted); }
    .flame { font-size: 0.85rem; }

    .pill { display: inline-block; padding: 3px 10px; border-radius: 9999px; font-size: 0.72rem; font-weight: 600; border: 1px solid transparent; }
    .pill-red   { background: rgba(239,68,68,.15);  color: #fca5a5; border-color: rgba(239,68,68,.3); }
    .pill-amber { background: rgba(245,158,11,.15); color: #fcd34d; border-color: rgba(245,158,11,.3); }
    .pill-green { background: rgba(34,197,94,.15);  color: #86efac; border-color: rgba(34,197,94,.3); }
    .pill-gray  { background: rgba(107,114,128,.2); color: #cbd5e1; border-color: rgba(107,114,128,.35); }

    /* preview */
    .device-toggle { display: flex; gap: 0.4rem; margin-bottom: 0.85rem; }
    .device-toggle button {
      padding: 0.34rem 0.85rem; border-radius: 9999px; border: 1px solid var(--border);
      background: var(--panel); color: var(--muted); cursor: pointer; font-size: 0.78rem; transition: all .16s;
    }
    .device-toggle button.active { background: var(--text); color: #0b0b0b; border-color: var(--text); }
    .preview-frame-wrap { display: flex; justify-content: center; }
    iframe#demo-preview {
      border: 1px solid var(--border); border-radius: var(--radius-sm);
      width: 100%; height: 560px; background: #fff; transition: width .2s;
    }

    /* activity feed */
    .feed { display: flex; flex-direction: column; gap: 0.15rem; }
    .feed-item { display: flex; gap: 0.7rem; align-items: baseline; padding: 0.5rem 0; border-bottom: 1px solid var(--border); font-size: 0.85rem; }
    .feed-item:last-child { border-bottom: none; }
    .feed-time { color: var(--faint); font-size: 0.72rem; font-variant-numeric: tabular-nums; white-space: nowrap; min-width: 52px; }
    .feed-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--accent); margin-top: 6px; flex: none; }

    .draft-card { border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 1rem 1.1rem; margin-bottom: 0.75rem; background: rgba(255,255,255,.02); }
    .draft-card strong { font-size: 0.9rem; }
    .draft-card pre { white-space: pre-wrap; font-family: inherit; font-size: 0.83rem; color: #d7dae0; margin: 0.6rem 0 0.8rem; line-height: 1.5; }
    .muted { color: var(--muted); font-size: 0.85rem; }
    .empty { color: var(--faint); font-size: 0.86rem; padding: 0.6rem 0; }

    /* ---------- chat ---------- */
    #chat-toggle {
      position: fixed; bottom: 22px; right: 22px; width: 56px; height: 56px; border-radius: 50%;
      background: var(--accent); color: #fff; border: none; font-size: 1.35rem; cursor: pointer;
      box-shadow: 0 8px 28px var(--accent-glow); z-index: 60;
    }
    #chat-panel {
      position: fixed; bottom: 88px; right: 22px; width: 350px; max-height: 500px;
      background: rgba(20,22,27,.82); backdrop-filter: blur(24px) saturate(140%); -webkit-backdrop-filter: blur(24px) saturate(140%);
      border: 1px solid var(--border-strong); border-radius: var(--radius); z-index: 60;
      display: none; flex-direction: column; overflow: hidden; box-shadow: 0 20px 60px rgba(0,0,0,.55);
    }
    #chat-panel.open { display: flex; }
    #chat-header { padding: 0.8rem 1rem; font-weight: 600; font-size: 0.9rem; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 0.5rem; }
    #chat-messages { flex: 1; overflow-y: auto; padding: 0.85rem 1rem; display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.85rem; }
    .chat-msg { padding: 0.5rem 0.75rem; border-radius: 13px; max-width: 86%; line-height: 1.45; }
    .chat-msg.user { align-self: flex-end; background: var(--accent); color: #fff; }
    .chat-msg.bot { align-self: flex-start; background: rgba(255,255,255,.07); color: var(--text); }
    #chat-input-row { display: flex; border-top: 1px solid var(--border); }
    #chat-input { flex: 1; border: none; background: transparent; color: var(--text); padding: 0.8rem; font-size: 0.85rem; font-family: inherit; }
    #chat-input::placeholder { color: var(--faint); }
    #chat-send { border: none; background: var(--accent); color: #fff; padding: 0 1.1rem; cursor: pointer; font-family: inherit; }

    /* ---------- command palette ---------- */
    #palette-overlay {
      position: fixed; inset: 0; background: rgba(0,0,0,.55); backdrop-filter: blur(3px);
      display: none; align-items: flex-start; justify-content: center; z-index: 80; padding-top: 12vh;
    }
    #palette-overlay.open { display: flex; }
    #palette {
      width: min(560px, 92vw); background: rgba(20,22,27,.92);
      backdrop-filter: blur(26px) saturate(140%); -webkit-backdrop-filter: blur(26px) saturate(140%);
      border: 1px solid var(--border-strong); border-radius: 16px; overflow: hidden; box-shadow: 0 30px 80px rgba(0,0,0,.6);
    }
    #palette-input { width: 100%; border: none; background: transparent; color: var(--text); font-size: 1rem; padding: 1rem 1.15rem; font-family: inherit; border-bottom: 1px solid var(--border); }
    #palette-input::placeholder { color: var(--faint); }
    #palette-list { list-style: none; margin: 0; padding: 0.4rem; max-height: 46vh; overflow-y: auto; }
    #palette-list li { display: flex; align-items: center; gap: 0.7rem; padding: 0.6rem 0.8rem; border-radius: 10px; cursor: pointer; font-size: 0.9rem; }
    #palette-list li .cmd-ico { width: 22px; text-align: center; opacity: .8; }
    #palette-list li .cmd-tag { margin-left: auto; font-size: 0.72rem; color: var(--faint); }
    #palette-list li.active, #palette-list li:hover { background: var(--accent-soft); }

    :focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }

    @media (max-width: 940px) {
      .hero { grid-template-columns: 1fr; }
      .two-col { grid-template-columns: 1fr; }
      .kpis { grid-template-columns: repeat(2, 1fr); }
    }
    @media (max-width: 560px) {
      .wrap { padding: 1rem 1rem 5rem; }
      .kpis { grid-template-columns: repeat(2, 1fr); }
      .navtabs { order: 3; width: 100%; justify-content: space-between; }
    }
  </style>
</head>
<body>
  <div style="background:#111;color:#e5e7eb;font-size:.78rem;text-align:center;padding:.5rem 1rem;border-bottom:1px solid rgba(255,255,255,.08);">
    <strong style="color:#60a5fa;">Preview</strong> &middot; sample data, no live backend &mdash; this is exactly how v2 looks &amp; behaves once <code>fastapi_backend</code> is running.
  </div>
  <div class="wrap">
    <!-- header -->
    <div class="topbar">
      <div class="brand"><span class="mark"></span> Obsidian Labs</div>
      <div class="navtabs" role="tablist">
        <button data-page="dashboard" class="active">Mission Control</button>
        <button data-page="leads">Leads</button>
        <button data-page="demos">Demos</button>
        <button data-page="outreach">Outreach</button>
      </div>
      <div class="spacer"></div>
      <button class="ghost-btn" id="palette-btn" title="Command palette"><span>Search</span> <kbd>⌘K</kbd></button>
      <button class="ghost-btn" id="settings-btn" title="Set backend URL">⚙ Backend</button>
    </div>

    <!-- ===================== DASHBOARD PAGE ===================== -->
    <div id="page-dashboard">
      <!-- hero: AI status ring + KPI cards -->
      <div class="hero">
        <div class="card pad ring-card">
          <div class="ring" id="ring">
            <div>
              <div class="ring-num" id="ring-num">–</div>
              <div class="ring-lbl">Leads</div>
            </div>
          </div>
          <div class="ring-status" id="ring-status"><span class="dot" id="ring-dot"></span> Checking backend…</div>
        </div>

        <div class="kpis">
          <div class="card kpi"><div class="label">Leads</div><div class="value" id="m-leads">–</div><div class="sub">in the pipeline</div></div>
          <div class="card kpi"><div class="label">Hot leads</div><div class="value" id="m-hot">–</div><div class="sub">ready to pitch</div></div>
          <div class="card kpi"><div class="label">Demos generated</div><div class="value" id="m-demos">–</div><div class="sub">preview-ready sites</div></div>
          <div class="card kpi"><div class="label">Outreach drafts</div><div class="value" id="m-outreach">–</div><div class="sub">awaiting approval</div></div>
          <div class="card kpi revenue accent" id="revenue-card" title="Click to set your price-per-deal">
            <div class="label">Potential revenue</div><div class="value" id="m-revenue">–</div>
            <div class="sub" id="m-revenue-sub">hot leads × price</div>
          </div>
          <div class="card kpi"><div class="label">Guardrail</div><div class="value" style="font-size:1rem;line-height:1.35;font-weight:600;">100% local<br>Nothing auto-sends</div></div>
        </div>
      </div>

      <div class="actionrow">
        <button class="btn" id="run-pipeline-btn">▶ Run Pipeline</button>
        <button class="btn secondary" id="approve-btn" disabled>Approve &amp; Send</button>
        <span class="run-status" id="run-status">Select a lead to preview its generated demo.</span>
      </div>

      <div class="two-col">
        <div class="card pad">
          <h2>Leads</h2>
          <div class="lead-list" id="leads-list"><div class="empty">Loading…</div></div>
        </div>
        <div class="card pad">
          <h2>Demo preview</h2>
          <div class="device-toggle">
            <button data-device="Desktop" class="active">Desktop</button>
            <button data-device="Tablet">Tablet</button>
            <button data-device="Mobile">Mobile</button>
          </div>
          <div class="preview-frame-wrap">
            <iframe id="demo-preview" title="Demo site preview" srcdoc="<p style='font-family:system-ui;color:#999;padding:2rem;'>Select a lead to preview its demo.</p>"></iframe>
          </div>
        </div>
      </div>

      <!-- live activity feed -->
      <div class="card pad" style="margin-top:1.2rem;">
        <h2>Live activity</h2>
        <div class="feed" id="feed"></div>
      </div>
    </div>

    <!-- ===================== LEADS PAGE ===================== -->
    <div id="page-leads" style="display:none;">
      <div class="card pad">
        <h2>All leads</h2>
        <div class="lead-list" id="leads-full-list"><div class="empty">Loading…</div></div>
      </div>
    </div>

    <!-- ===================== DEMOS PAGE ===================== -->
    <div id="page-demos" style="display:none;">
      <div class="card pad">
        <h2>Demos</h2>
        <div id="demos-list" class="muted">Loading…</div>
      </div>
    </div>

    <!-- ===================== OUTREACH PAGE ===================== -->
    <div id="page-outreach" style="display:none;">
      <div class="card pad">
        <h2>Outreach drafts</h2>
        <p class="muted" style="margin-top:-0.4rem;">Drafts only — approving here just logs the approval. Sending is a separate, deliberate step outside this dashboard.</p>
        <div id="outreach-list" class="muted">Loading…</div>
      </div>
    </div>
  </div>

  <!-- chat -->
  <button id="chat-toggle" title="Ask the Obsidian Labs assistant">💬</button>
  <div id="chat-panel">
    <div id="chat-header"><span class="dot"></span> Obsidian Labs Assistant</div>
    <div id="chat-messages"></div>
    <div id="chat-input-row">
      <input id="chat-input" type="text" placeholder="Ask about your pipeline…" />
      <button id="chat-send">Send</button>
    </div>
  </div>

  <!-- command palette -->
  <div id="palette-overlay">
    <div id="palette" role="dialog" aria-label="Command palette">
      <input id="palette-input" type="text" placeholder="Search leads, jump to a section, run an action…" autocomplete="off" />
      <ul id="palette-list"></ul>
    </div>
  </div>

  <script>
    /* ===================================================================
       Config — backend URL + price-per-deal, both remembered per device.
       =================================================================== */
    function getApiBase() { return localStorage.getItem("obsidian_api_base") || "http://localhost:8502"; }
    function setApiBase(url) { localStorage.setItem("obsidian_api_base", url.replace(/\/$/, "")); }
    function getRevPer() { return Number(localStorage.getItem("obsidian_rev_per")) || 2500; }
    function setRevPer(v) { localStorage.setItem("obsidian_rev_per", String(v)); }

    let API_BASE = getApiBase();
    let currentDevice = "Desktop";
    let currentSlug = null;
    let leadsCache = [];
    let lastStatus = null;

    /* ---------- tiny helpers ---------- */
    function money(n) { return "$" + Math.round(n).toLocaleString("en-US"); }
    function slugify(name) { return (name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "lead"; }
    function pillFor(status, perf) {
      perf = Number(perf) || 0;
      if (status === "no_website") return ["No Website", "pill-red"];
      if (status === "unreachable") return ["Unreachable", "pill-red"];
      if (status === "api_error") return ["Grade Error", "pill-gray"];
      if (perf <= 50) return ["Needs Work", "pill-amber"];
      return ["Healthy", "pill-green"];
    }
    function isHot(l) { return String(l.is_hot_lead).toLowerCase() === "true"; }

    /* ---------- PREVIEW API layer: baked-in sample data, fully self-contained.
       In the real v2 these hit fastapi_backend on :8502. ---------- */
    const DEMO_DENTAL = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>
      *{margin:0;box-sizing:border-box;font-family:system-ui,sans-serif}
      .hero{background:linear-gradient(135deg,#0e7490,#155e75);color:#fff;padding:60px 26px;text-align:center}
      .hero h1{font-size:2rem;letter-spacing:-.02em}.hero p{opacity:.9;margin-top:10px}
      .cta{display:inline-block;margin-top:20px;background:#fff;color:#155e75;padding:12px 26px;border-radius:9999px;font-weight:700;text-decoration:none}
      .row{display:flex;flex-wrap:wrap;gap:14px;padding:32px 26px}
      .card{flex:1 1 200px;border:1px solid #e5e7eb;border-radius:14px;padding:18px}
      .card h3{color:#155e75}.card p{color:#6b7280;margin-top:8px;font-size:.9rem}
      .bar{background:#f1f5f9;padding:16px;text-align:center;color:#475569;font-size:.85rem}
    </style></head><body>
      <div class="hero"><h1>Mahopac Family Dental</h1><p>Gentle, modern dentistry for the whole family &mdash; now booking new patients.</p><a class="cta" href="#">Book an appointment</a></div>
      <div class="row"><div class="card"><h3>Same-day visits</h3><p>Emergency slots kept open every day.</p></div><div class="card"><h3>Insurance friendly</h3><p>We handle the paperwork and most plans.</p></div><div class="card"><h3>Kids welcome</h3><p>A calm team families in Mahopac trust.</p></div></div>
      <div class="bar">123 Lake Blvd, Mahopac NY &middot; (845) 555-0142</div>
    </body></html>`;
    const DEMO_SALON = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>
      *{margin:0;box-sizing:border-box;font-family:Georgia,serif}
      .hero{background:#1c1917;color:#fbbf24;padding:60px 26px;text-align:center}
      .hero h1{font-size:2.1rem;letter-spacing:.04em}.hero p{color:#e7e5e4;margin-top:10px;font-family:system-ui}
      .cta{display:inline-block;margin-top:20px;background:#fbbf24;color:#1c1917;padding:12px 26px;border-radius:6px;font-weight:700;text-decoration:none;font-family:system-ui}
      .svc{padding:32px 26px;max-width:520px;margin:0 auto}
      .svc div{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eee;font-family:system-ui}
    </style></head><body>
      <div class="hero"><h1>SHEAR ELEGANCE</h1><p>Carmel&rsquo;s studio for cut, color &amp; style.</p><a class="cta" href="#">Reserve your chair</a></div>
      <div class="svc"><div><span>Women&rsquo;s cut &amp; style</span><span>$65+</span></div><div><span>Full color</span><span>$120+</span></div><div><span>Balayage</span><span>$180+</span></div></div>
    </body></html>`;
    const SAMPLE = {
      leads: [
        { name: "Mahopac Family Dental", type: "dentist",    town: "Mahopac", perf_score: 34, status: "graded",      is_hot_lead: "true"  },
        { name: "Summit Roofing Co",     type: "roofer",     town: "Carmel",  perf_score: 0,  status: "no_website",  is_hot_lead: "true"  },
        { name: "Lakeside Bistro",       type: "restaurant", town: "Mahopac", perf_score: 78, status: "graded",      is_hot_lead: "false" },
        { name: "Shear Elegance Salon",  type: "salon",      town: "Carmel",  perf_score: 45, status: "graded",      is_hot_lead: "true"  },
        { name: "Carmel Auto Care",      type: "auto shop",  town: "Carmel",  perf_score: 0,  status: "unreachable", is_hot_lead: "false" }
      ],
      demoHtml: { "mahopac-family-dental": DEMO_DENTAL, "shear-elegance-salon": DEMO_SALON },
      outreach: { "mahopac-family-dental":
`Subject: Quick question about your Mahopac dentist website

Hi Dr. Alvarez,

I noticed your site loads slowly on phones and doesn't have an easy "book online" button up top - which is where most new-patient enquiries start.

I put together a quick redesigned home page for Mahopac Family Dental so you can see what a faster, mobile-first version could look like.

If it's useful, our Starter site is a flat $1,495. Want me to send the preview link over?

Best,
Obsidian Labs` }
    };
    function computeStatus() {
      const hot = SAMPLE.leads.filter(l => String(l.is_hot_lead).toLowerCase() === "true").length;
      return { leads: SAMPLE.leads.length, hot_leads: hot, demos: Object.keys(SAMPLE.demoHtml).length,
        outreach_drafts: Object.keys(SAMPLE.outreach).length,
        pricing: { starter: 1495, professional: 2500, business_growth: "4500+" },
        guardrails: "Runs 100% locally. Nothing auto-sends." };
    }
    function cannedChat(msg) {
      const m = (msg || "").toLowerCase();
      if (m.includes("hot")) return "You have 3 hot leads: Mahopac Family Dental, Summit Roofing Co, and Shear Elegance Salon. Summit has no website at all - usually the easiest first conversation.";
      if (m.includes("price") || m.includes("cost") || m.includes("revenue") || m.includes("$")) return "Pricing is Starter $1,495 / Professional $2,500 / Business Growth $4,500+. The Potential Revenue card multiplies hot leads by your price-per-deal (tap it to change).";
      if (m.includes("send")) return "This system never auto-sends. Approving just logs it - you send manually when ready.";
      return "This is a preview reply. Against the live backend I answer from your real pipeline stats via local Ollama - nothing leaves your laptop.";
    }
    async function apiGet(path) {
      await new Promise(r => setTimeout(r, 90));
      if (path === "/api/status") return computeStatus();
      if (path === "/api/leads") return SAMPLE.leads;
      if (path === "/api/demos") return Object.keys(SAMPLE.demoHtml).map(s => ({ slug: s }));
      if (path.startsWith("/api/demos/")) { const s = decodeURIComponent(path.split("/").pop()); if (SAMPLE.demoHtml[s]) return { slug: s, html: SAMPLE.demoHtml[s] }; throw new Error(`${path} -> 404`); }
      if (path === "/api/outreach") return Object.keys(SAMPLE.outreach).map(s => ({ slug: s }));
      if (path.startsWith("/api/outreach/")) { const s = decodeURIComponent(path.split("/").pop()); return { slug: s, content: SAMPLE.outreach[s] || "" }; }
      throw new Error(`${path} -> 404`);
    }
    async function apiPost(path, body) {
      await new Promise(r => setTimeout(r, 130));
      if (path === "/api/chat") return { reply: cannedChat((body || {}).message) };
      if (path === "/api/approve") return { status: "logged", ...(body || {}) };
      if (path === "/api/run-pipeline") return { status: "started" };
      return {};
    }

    /* ---------- activity feed ---------- */
    const activity = [];
    function pushActivity(text) {
      const d = new Date();
      const t = d.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
      activity.unshift({ t, text });
      if (activity.length > 12) activity.pop();
      renderFeed();
    }
    function renderFeed() {
      const el = document.getElementById("feed");
      if (!activity.length) { el.innerHTML = `<div class="empty">No activity yet — run the pipeline to get started.</div>`; return; }
      el.innerHTML = activity.map(a =>
        `<div class="feed-item"><span class="feed-time">${a.t}</span><span class="feed-dot"></span><span>${a.text}</span></div>`
      ).join("");
    }

    /* ---------- status: KPIs, ring, revenue ---------- */
    function setRing(online, leads) {
      const ring = document.getElementById("ring");
      const dot = document.getElementById("ring-dot");
      const st = document.getElementById("ring-status");
      document.getElementById("ring-num").textContent = online ? leads : "–";
      ring.classList.toggle("offline", !online);
      dot.classList.toggle("bad", !online);
      st.innerHTML = online
        ? `<span class="dot" id="ring-dot"></span> Pipeline online`
        : `<span class="dot bad" id="ring-dot"></span> Backend offline`;
    }
    function renderRevenue(hot) {
      const per = getRevPer();
      document.getElementById("m-revenue").textContent = money(hot * per);
      document.getElementById("m-revenue-sub").textContent = `${hot} hot × ${money(per)}`;
    }
    async function loadStatus() {
      try {
        const s = await apiGet("/api/status");
        lastStatus = s;
        document.getElementById("m-leads").textContent = s.leads;
        document.getElementById("m-hot").textContent = s.hot_leads;
        document.getElementById("m-demos").textContent = s.demos;
        document.getElementById("m-outreach").textContent = s.outreach_drafts;
        renderRevenue(s.hot_leads);
        setRing(true, s.leads);
      } catch (e) {
        setRing(false, 0);
      }
    }

    /* ---------- leads ---------- */
    async function loadLeads() {
      try { leadsCache = await apiGet("/api/leads"); pushActivity(`Loaded ${leadsCache.length} lead${leadsCache.length === 1 ? "" : "s"}.`); }
      catch (e) { leadsCache = []; }
      renderLeadList("leads-list", true);
      renderLeadList("leads-full-list", false);
    }
    function leadItemHTML(l, compact) {
      const [label, cls] = pillFor(l.status, l.perf_score);
      const hot = isHot(l);
      const sel = slugify(l.name) === currentSlug ? " selected" : "";
      const meta = compact
        ? `${l.type || ""}${l.town ? " · " + l.town : ""}`
        : `${l.type || ""}${l.town ? " · " + l.town : ""} · score ${l.perf_score || 0}`;
      return `<div class="lead-item${sel}" data-slug="${slugify(l.name)}" tabindex="0">
        <div><div class="lead-name">${hot ? "🔥 " : ""}${l.name || ""}</div><div class="lead-meta">${meta}</div></div>
        <div class="lead-right">${compact ? `<span class="score">${l.perf_score || 0}</span>` : ""}<span class="pill ${cls}">${label}</span></div>
      </div>`;
    }
    function renderLeadList(elId, compact) {
      const el = document.getElementById(elId);
      if (!leadsCache.length) { el.innerHTML = `<div class="empty">No leads yet. Hit ▶ Run Pipeline to gather some.</div>`; return; }
      el.innerHTML = leadsCache.map(l => leadItemHTML(l, compact)).join("");
      el.querySelectorAll(".lead-item").forEach(row => {
        const go = () => selectLead(row.dataset.slug);
        row.addEventListener("click", go);
        row.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
      });
    }
    async function selectLead(slug) {
      currentSlug = slug;
      document.getElementById("approve-btn").disabled = false;
      renderLeadList("leads-list", true);
      renderLeadList("leads-full-list", false);
      try {
        const demo = await apiGet(`/api/demos/${slug}`);
        renderPreview(demo.html);
        document.getElementById("run-status").textContent = `Previewing the demo for “${slug}”.`;
      } catch (e) {
        document.getElementById("demo-preview").srcdoc =
          `<p style='font-family:system-ui;color:#999;padding:2rem;'>No demo generated yet for “${slug}”.</p>`;
        document.getElementById("run-status").textContent = `No demo generated yet for “${slug}”.`;
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

    /* ---------- actions ---------- */
    document.getElementById("approve-btn").addEventListener("click", async () => {
      if (!currentSlug) return;
      try {
        await apiPost("/api/approve", { kind: "dashboard_approve_and_send", identifier: currentSlug });
        document.getElementById("run-status").textContent = `Logged approval for “${currentSlug}”. This does NOT send anything.`;
        pushActivity(`Approved “${currentSlug}” (logged, not sent).`);
      } catch (e) { document.getElementById("run-status").textContent = "Couldn't reach the backend to log approval."; }
    });
    document.getElementById("run-pipeline-btn").addEventListener("click", async () => {
      const st = document.getElementById("run-status");
      st.textContent = "Starting pipeline in the background…";
      try {
        await apiPost("/api/run-pipeline", { stage: "all", towns: ["Mahopac", "Carmel"], niches: ["dentist", "roofer"], limit: 5 });
        st.textContent = "Pipeline started. Check output/logs/pipeline_run.log, or refresh in a bit.";
        pushActivity("Pipeline run started (scrape → grade → demo → outreach).");
      } catch (e) { st.textContent = "Failed to start — is the backend running?"; }
    });

    /* ---------- demos + outreach pages ---------- */
    async function loadDemos() {
      const el = document.getElementById("demos-list");
      try {
        const demos = await apiGet("/api/demos");
        if (!demos.length) { el.innerHTML = `<div class="empty">No demos generated yet.</div>`; return; }
        el.innerHTML = demos.map(d => `<div class="draft-card"><strong>${d.slug}</strong></div>`).join("");
      } catch (e) { el.innerHTML = `<div class="empty">Backend unreachable.</div>`; }
    }
    async function loadOutreach() {
      const el = document.getElementById("outreach-list");
      try {
        const drafts = await apiGet("/api/outreach");
        if (!drafts.length) { el.innerHTML = `<div class="empty">No outreach drafts yet.</div>`; return; }
        let html = "";
        for (const d of drafts) {
          const full = await apiGet(`/api/outreach/${d.slug}`);
          html += `<div class="draft-card"><strong>${d.slug}</strong>
            <pre>${full.content.replace(/</g, "&lt;")}</pre>
            <button class="btn secondary small" data-approve-slug="${d.slug}">Approve</button></div>`;
        }
        el.innerHTML = html;
        el.querySelectorAll("[data-approve-slug]").forEach(btn => {
          btn.addEventListener("click", async () => {
            await apiPost("/api/approve", { kind: "outreach_approved", identifier: btn.dataset.approveSlug });
            btn.textContent = "Approved ✓"; btn.disabled = true;
            pushActivity(`Approved outreach draft “${btn.dataset.approveSlug}”.`);
          });
        });
      } catch (e) { el.innerHTML = `<div class="empty">Backend unreachable.</div>`; }
    }

    /* ---------- nav tabs ---------- */
    function goToPage(page) {
      document.querySelectorAll(".navtabs button").forEach(b => b.classList.toggle("active", b.dataset.page === page));
      ["dashboard", "leads", "demos", "outreach"].forEach(p => {
        document.getElementById(`page-${p}`).style.display = p === page ? "" : "none";
      });
      if (page === "demos") loadDemos();
      if (page === "outreach") loadOutreach();
    }
    document.querySelectorAll(".navtabs button").forEach(btn => btn.addEventListener("click", () => goToPage(btn.dataset.page)));

    /* ---------- revenue card: editable price-per-deal ---------- */
    document.getElementById("revenue-card").addEventListener("click", () => {
      const cur = getRevPer();
      const next = prompt("Average price per closed deal (used for Potential Revenue):", cur);
      const n = Number((next || "").replace(/[^0-9.]/g, ""));
      if (n > 0) { setRevPer(n); if (lastStatus) renderRevenue(lastStatus.hot_leads); }
    });

    /* ---------- chat ---------- */
    const chatPanel = document.getElementById("chat-panel");
    const chatMessages = document.getElementById("chat-messages");
    const chatInput = document.getElementById("chat-input");
    document.getElementById("chat-toggle").addEventListener("click", () => chatPanel.classList.toggle("open"));
    function addChatMsg(text, who) {
      const div = document.createElement("div");
      div.className = `chat-msg ${who}`; div.textContent = text;
      chatMessages.appendChild(div); chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    async function sendChat() {
      const msg = chatInput.value.trim();
      if (!msg) return;
      addChatMsg(msg, "user"); chatInput.value = ""; addChatMsg("Thinking…", "bot");
      try {
        const res = await apiPost("/api/chat", { message: msg });
        chatMessages.lastChild.textContent = res.reply || "(no response)";
      } catch (e) {
        chatMessages.lastChild.textContent = "Couldn't reach the assistant — is fastapi_backend + Ollama running?";
      }
    }
    document.getElementById("chat-send").addEventListener("click", sendChat);
    chatInput.addEventListener("keydown", e => { if (e.key === "Enter") sendChat(); });

    /* ---------- settings ---------- */
    document.getElementById("settings-btn").addEventListener("click", () => {
      alert("In the live v2 dashboard this is where you paste your backend URL (your ngrok https address, or http://localhost:8502). In this preview the data is built-in, so there's nothing to point at.");
    });

    /* ---------- command palette (⌘K / Ctrl+K) ---------- */
    const overlay = document.getElementById("palette-overlay");
    const pInput = document.getElementById("palette-input");
    const pList = document.getElementById("palette-list");
    let pActive = 0, pItems = [];
    const COMMANDS = [
      { ico: "◫", label: "Go to Mission Control", tag: "Section", run: () => goToPage("dashboard") },
      { ico: "☰", label: "Go to Leads", tag: "Section", run: () => goToPage("leads") },
      { ico: "▦", label: "Go to Demos", tag: "Section", run: () => goToPage("demos") },
      { ico: "✉", label: "Go to Outreach", tag: "Section", run: () => goToPage("outreach") },
      { ico: "▶", label: "Run Pipeline", tag: "Action", run: () => document.getElementById("run-pipeline-btn").click() },
      { ico: "⟳", label: "Refresh data", tag: "Action", run: () => refreshAll() },
      { ico: "💬", label: "Open chat assistant", tag: "Action", run: () => chatPanel.classList.add("open") },
      { ico: "⚙", label: "Set backend URL", tag: "Action", run: () => document.getElementById("settings-btn").click() },
    ];
    function openPalette() { overlay.classList.add("open"); pInput.value = ""; buildPalette(""); pInput.focus(); }
    function closePalette() { overlay.classList.remove("open"); }
    function buildPalette(q) {
      q = q.toLowerCase();
      const cmds = COMMANDS.filter(c => c.label.toLowerCase().includes(q));
      const leadHits = leadsCache
        .filter(l => (l.name || "").toLowerCase().includes(q) && q)
        .slice(0, 6)
        .map(l => ({ ico: "🔎", label: l.name, tag: "Lead", run: () => { goToPage("dashboard"); selectLead(slugify(l.name)); } }));
      pItems = [...cmds, ...leadHits];
      pActive = 0;
      pList.innerHTML = pItems.map((it, i) =>
        `<li data-i="${i}" class="${i === 0 ? "active" : ""}"><span class="cmd-ico">${it.ico}</span><span>${it.label}</span><span class="cmd-tag">${it.tag}</span></li>`
      ).join("") || `<li class="empty" style="color:var(--faint);cursor:default;">No matches</li>`;
      pList.querySelectorAll("li[data-i]").forEach(li => {
        li.addEventListener("click", () => runPaletteItem(Number(li.dataset.i)));
      });
    }
    function runPaletteItem(i) { const it = pItems[i]; if (it) { closePalette(); it.run(); } }
    function movePalette(d) {
      if (!pItems.length) return;
      pActive = (pActive + d + pItems.length) % pItems.length;
      pList.querySelectorAll("li[data-i]").forEach(li => li.classList.toggle("active", Number(li.dataset.i) === pActive));
      const active = pList.querySelector("li.active"); if (active) active.scrollIntoView({ block: "nearest" });
    }
    pInput.addEventListener("input", () => buildPalette(pInput.value));
    pInput.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { e.preventDefault(); movePalette(1); }
      else if (e.key === "ArrowUp") { e.preventDefault(); movePalette(-1); }
      else if (e.key === "Enter") { e.preventDefault(); runPaletteItem(pActive); }
      else if (e.key === "Escape") closePalette();
    });
    overlay.addEventListener("click", e => { if (e.target === overlay) closePalette(); });
    document.getElementById("palette-btn").addEventListener("click", openPalette);
    document.addEventListener("keydown", e => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); overlay.classList.contains("open") ? closePalette() : openPalette(); }
    });

    /* ---------- PWA registration omitted in preview build ---------- */

    /* ---------- boot ---------- */
    function refreshAll() { loadStatus(); loadLeads(); }
    addChatMsg("Hi! I'm your pipeline assistant. Ask about your hot leads, drafts, or pricing.", "bot");
    pushActivity("Nightly pipeline run completed — 5 leads, 2 demos.");
    refreshAll();
    setInterval(loadStatus, 15000);
  </script>
</body>
</html>

```

## `dashboard_preview.html`  
_(539 lines)_

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Obsidian Labs - Dashboard Preview</title>
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
    html, body { background: var(--bg); }
    body {
      margin: 0;
      color: var(--text);
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .preview-banner {
      background: #111; color: #fff; font-size: 0.78rem; text-align: center;
      padding: 0.5rem 1rem; letter-spacing: 0.01em;
    }
    .preview-banner strong { color: #ff6b6b; }
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
    .metric-card .value { font-size: 1.8rem; font-weight: 700; letter-spacing: -0.02em; font-variant-numeric: tabular-nums; }
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
      .wrap { padding: 1.25rem 1rem 4rem; }
    }
    table { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
    th, td { text-align: left; padding: 0.5rem 0.5rem; border-bottom: 1px solid var(--border); }
    td.num { font-variant-numeric: tabular-nums; }
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
    button:focus-visible, .navtabs button:focus-visible, tr.lead-row:focus-visible {
      outline: 2px solid var(--red); outline-offset: 2px;
    }
  </style>
</head>
<body>
  <div class="preview-banner">
    <strong>Preview</strong> &middot; sample data, no live backend &mdash; this is exactly how the dashboard looks &amp; behaves once <code>fastapi_backend</code> is running on your laptop.
  </div>
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
        <p class="muted" id="run-status">Tap a lead below to preview its generated demo site.</p>
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
            <iframe id="demo-preview" title="Demo site preview" srcdoc="<p style='font-family:sans-serif;color:#999;padding:2rem;'>Select a lead to preview its demo.</p>"></iframe>
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
    // ---------------------------------------------------------------------
    // PREVIEW BUILD: the real dashboard fetches everything from
    // fastapi_backend on :8502. Here that network layer is replaced with
    // baked-in sample data so the page is fully self-contained and works
    // as a shareable link with no laptop/backend. Every interaction below
    // behaves exactly as it does against the live backend.
    // ---------------------------------------------------------------------
    const DEMO_DENTAL = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>
      *{margin:0;box-sizing:border-box;font-family:system-ui,sans-serif}
      .hero{background:linear-gradient(135deg,#0e7490,#155e75);color:#fff;padding:64px 28px;text-align:center}
      .hero h1{font-size:2rem;letter-spacing:-.02em}.hero p{opacity:.9;margin-top:10px}
      .cta{display:inline-block;margin-top:22px;background:#fff;color:#155e75;padding:12px 26px;border-radius:9999px;font-weight:700;text-decoration:none}
      .row{display:flex;flex-wrap:wrap;gap:16px;padding:36px 28px}
      .card{flex:1 1 200px;border:1px solid #e5e7eb;border-radius:14px;padding:20px}
      .card h3{color:#155e75}.card p{color:#6b7280;margin-top:8px;font-size:.9rem}
      .bar{background:#f1f5f9;padding:16px 28px;text-align:center;color:#475569;font-size:.85rem}
    </style></head><body>
      <div class="hero"><h1>Mahopac Family Dental</h1><p>Gentle, modern dentistry for the whole family &mdash; now booking new patients.</p><a class="cta" href="#">Book an appointment</a></div>
      <div class="row">
        <div class="card"><h3>Same-day visits</h3><p>Emergency slots kept open every day for urgent care.</p></div>
        <div class="card"><h3>Insurance friendly</h3><p>We handle the paperwork and most major plans.</p></div>
        <div class="card"><h3>Kids welcome</h3><p>A calm, patient team that families in Mahopac trust.</p></div>
      </div>
      <div class="bar">123 Lake Blvd, Mahopac NY &middot; (845) 555-0142 &middot; Mon&ndash;Fri 8&ndash;5</div>
    </body></html>`;

    const DEMO_SALON = `<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>
      *{margin:0;box-sizing:border-box;font-family:Georgia,serif}
      .hero{background:#1c1917;color:#fbbf24;padding:64px 28px;text-align:center}
      .hero h1{font-size:2.1rem;letter-spacing:.04em}.hero p{color:#e7e5e4;margin-top:10px;font-family:system-ui}
      .cta{display:inline-block;margin-top:22px;background:#fbbf24;color:#1c1917;padding:12px 26px;border-radius:6px;font-weight:700;text-decoration:none;font-family:system-ui}
      .svc{padding:36px 28px;max-width:520px;margin:0 auto}
      .svc div{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid #eee;font-family:system-ui}
    </style></head><body>
      <div class="hero"><h1>SHEAR ELEGANCE</h1><p>Carmel&rsquo;s studio for cut, color &amp; style.</p><a class="cta" href="#">Reserve your chair</a></div>
      <div class="svc"><div><span>Women&rsquo;s cut &amp; style</span><span>$65+</span></div><div><span>Full color</span><span>$120+</span></div><div><span>Balayage</span><span>$180+</span></div><div><span>Men&rsquo;s cut</span><span>$35</span></div></div>
    </body></html>`;

    const SAMPLE = {
      leads: [
        { name: "Mahopac Family Dental", type: "dentist",    town: "Mahopac", perf_score: 34, status: "graded",      is_hot_lead: "true"  },
        { name: "Summit Roofing Co",     type: "roofer",     town: "Carmel",  perf_score: 0,  status: "no_website",  is_hot_lead: "true"  },
        { name: "Lakeside Bistro",       type: "restaurant", town: "Mahopac", perf_score: 78, status: "graded",      is_hot_lead: "false" },
        { name: "Shear Elegance Salon",  type: "salon",      town: "Carmel",  perf_score: 45, status: "graded",      is_hot_lead: "true"  },
        { name: "Carmel Auto Care",      type: "auto shop",  town: "Carmel",  perf_score: 0,  status: "unreachable", is_hot_lead: "false" }
      ],
      demoHtml: {
        "mahopac-family-dental": DEMO_DENTAL,
        "shear-elegance-salon": DEMO_SALON
      },
      outreach: {
        "mahopac-family-dental":
`Subject: Quick question about your Mahopac dentist website

Hi Dr. Alvarez,

I was looking at dental practices around Mahopac and noticed your site loads slowly on phones and doesn't have an easy "book online" button up top - which is where most new-patient enquiries start these days.

I put together a quick redesigned home page for Mahopac Family Dental so you can see what a faster, mobile-first version could look like (no obligation, it's already built).

If it's useful, our Starter site is a flat $1,495. Happy to send the preview link over - want me to?

Best,
Obsidian Labs`
      }
    };

    function computeStatus() {
      const hot = SAMPLE.leads.filter(l => String(l.is_hot_lead).toLowerCase() === "true").length;
      return {
        leads: SAMPLE.leads.length,
        hot_leads: hot,
        demos: Object.keys(SAMPLE.demoHtml).length,
        outreach_drafts: Object.keys(SAMPLE.outreach).length,
        pricing: { starter: 1495, professional: 2500, business_growth: "4500+" },
        guardrails: "Runs 100% locally. Nothing auto-sends."
      };
    }

    function cannedChat(msg) {
      const m = (msg || "").toLowerCase();
      if (m.includes("hot")) return "You have 3 hot leads right now: Mahopac Family Dental, Summit Roofing Co, and Shear Elegance Salon. Summit has no website at all - usually the easiest first conversation.";
      if (m.includes("price") || m.includes("cost") || m.includes("$")) return "Pricing is Starter $1,495 / Professional $2,500 (most popular) / Business Growth $4,500+. The drafts pitch the Starter tier by default.";
      if (m.includes("send")) return "This system never auto-sends. Approving a draft here just logs it - you send manually from your own inbox when you're ready.";
      return "This is a preview reply. Against the live backend I answer using your real pipeline stats via local Ollama - nothing leaves your laptop. Try asking about your hot leads or pricing.";
    }

    async function apiGet(path) {
      await new Promise(r => setTimeout(r, 110));
      if (path === "/api/status") return computeStatus();
      if (path === "/api/leads") return SAMPLE.leads;
      if (path === "/api/demos") return Object.keys(SAMPLE.demoHtml).map(s => ({ slug: s }));
      if (path.startsWith("/api/demos/")) {
        const slug = decodeURIComponent(path.split("/").pop());
        if (SAMPLE.demoHtml[slug]) return { slug, html: SAMPLE.demoHtml[slug] };
        throw new Error(`${path} -> 404`);
      }
      if (path === "/api/outreach") return Object.keys(SAMPLE.outreach).map(s => ({ slug: s }));
      if (path.startsWith("/api/outreach/")) {
        const slug = decodeURIComponent(path.split("/").pop());
        return { slug, content: SAMPLE.outreach[slug] || "" };
      }
      throw new Error(`${path} -> 404`);
    }

    async function apiPost(path, body) {
      await new Promise(r => setTimeout(r, 150));
      if (path === "/api/chat") return { reply: cannedChat((body || {}).message) };
      if (path === "/api/approve") return { status: "logged", ...(body || {}) };
      if (path === "/api/run-pipeline") return { status: "started", command: "pipeline.py --stage all" };
      return {};
    }

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
      try { leadsCache = await apiGet("/api/leads"); }
      catch (e) { leadsCache = []; }
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
        return `<tr class="lead-row" data-slug="${slugify(l.name)}" tabindex="0">
          <td>${l.name || ""}</td><td>${l.type || ""}</td><td class="num">${l.perf_score || 0}</td>
          <td><span class="pill ${cls}">${label}</span></td></tr>`;
      }).join("");
      document.querySelectorAll("#leads-tbody tr.lead-row").forEach(row => {
        const go = () => selectLead(row.dataset.slug);
        row.addEventListener("click", go);
        row.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } });
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
        <td class="num">${l.perf_score || 0}</td><td>${String(l.is_hot_lead).toLowerCase() === "true" ? "Yes" : "No"}</td></tr>`).join("");
    }

    async function selectLead(slug) {
      currentSlug = slug;
      document.getElementById("approve-btn").disabled = false;
      try {
        const demo = await apiGet(`/api/demos/${slug}`);
        renderPreview(demo.html);
        document.getElementById("run-status").textContent = `Previewing the generated demo for '${slug}'.`;
      } catch (e) {
        document.getElementById("demo-preview").srcdoc =
          `<p style='font-family:sans-serif;color:#999;padding:2rem;'>No demo generated yet for '${slug}'.</p>`;
        document.getElementById("run-status").textContent = `No demo generated yet for '${slug}'. (In the live app, the pipeline builds one.)`;
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
        await apiPost("/api/run-pipeline", { stage: "all", towns: ["Mahopac", "Carmel"], niches: ["dentist", "roofer"], limit: 5 });
        document.getElementById("run-status").textContent =
          "Started. (Preview: in the live app this kicks off scrape -> grade -> demo -> outreach and logs to output/logs/pipeline_run.log.)";
      } catch (e) {
        document.getElementById("run-status").textContent = "Failed to start - is the backend running?";
      }
    });

    async function loadDemos() {
      try {
        const demos = await apiGet("/api/demos");
        const el = document.getElementById("demos-list");
        if (!demos.length) { el.innerHTML = `<p class="muted">No demos generated yet.</p>`; return; }
        el.innerHTML = demos.map(d => `<div class="draft-card"><strong>${d.slug}</strong></div>`).join("");
      } catch (e) {}
    }

    async function loadOutreach() {
      try {
        const drafts = await apiGet("/api/outreach");
        const el = document.getElementById("outreach-list");
        if (!drafts.length) { el.innerHTML = `<p class="muted">No outreach drafts yet.</p>`; return; }
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
        chatMessages.lastChild.textContent = "Couldn't reach the assistant - is fastapi_backend + Ollama running?";
      }
    }

    document.getElementById("chat-send").addEventListener("click", sendChat);
    chatInput.addEventListener("keydown", e => { if (e.key === "Enter") sendChat(); });

    document.getElementById("settings-btn").addEventListener("click", () => {
      alert("In the live dashboard this is where you paste your backend URL (e.g. your ngrok https address, or http://localhost:8502). In this preview the data is built-in, so there's nothing to point at.");
    });

    // Seed the assistant with a friendly opener and load everything.
    addChatMsg("Hi! I'm your pipeline assistant. Ask me about your hot leads, drafts, or pricing.", "bot");
    loadStatus();
    loadLeads();
  </script>
</body>
</html>

```

# Other files

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

---

## For the reviewer (paste this to ChatGPT)
> You are a senior engineer reviewing a $0-cost, fully local lead-gen pipeline for a
> web-design studio (scrape local businesses → grade their site → generate a demo with a
> local LLM via Ollama → draft a CAN-SPAM outreach email → a human approves in a dashboard →
> the human sends manually; nothing auto-sends). All files are below. Review for correctness,
> security, and reliability: flag real bugs, risky edges, and anything that breaks under real
> data or when Ollama / the RAG index / GOOGLE_API_KEY are missing. Then give prioritized,
> concrete fixes. Note: scraper.py and grader.py are re-implementations of the documented
> interface; the templates/*.md prompts are starter content.
