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

> **Docs:** see [`docs/`](docs/) for the business playbook (find → build → ship → sell)
> and the design spec + blueprint for a dark "Tesla v2" dashboard redesign.

## What's here (from the handoff appendices)

| File | Purpose |
| --- | --- |
| `autonomous_orchestrator.py` | Nightly scheduler v2 — fail-fast, dedup, Telegram notify, rotating logs, `--now` flag |
| `media_enhancer.py` | Sharpens/enhances real scraped photos (Pillow); optional Unsplash stock-photo fallback |
| `outreach_generator.py` | Drafts the $1,495 pitch email via local Ollama, grounded in RAG |
| `fastapi_backend.py` | API server (port 8502) powering the dashboard |
| `tesla_style_dashboard_v2.html` | **Current dashboard** — dark, Tesla/Apple glassmorphism: AI status ring, KPI + Potential Revenue cards, ⌘K command palette, live activity feed, chat, PWA |
| `tesla_style_dashboard_with_chat.html` | v1 dashboard (light theme) — kept as a fallback; same backend |
| `dashboard_v2_preview.html` / `dashboard_preview.html` | Self-contained sample-data previews (shareable, no backend) |
| `manifest.json` / `sw.js` | PWA manifest + service worker (installs the v2 dashboard as an app) |
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
#    - locally: open tesla_style_dashboard_v2.html  (v1 light theme still at tesla_style_dashboard_with_chat.html)
#    - on a phone: serve via GitHub Pages + point the gear (⚙ Backend) URL at an ngrok tunnel
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
