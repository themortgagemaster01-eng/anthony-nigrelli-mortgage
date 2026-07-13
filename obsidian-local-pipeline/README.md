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
