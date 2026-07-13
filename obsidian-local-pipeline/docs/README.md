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
