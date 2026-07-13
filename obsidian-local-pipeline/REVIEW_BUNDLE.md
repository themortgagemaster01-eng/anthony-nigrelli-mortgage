# Obsidian Labs — Full System Bundle (updated)

_Single-file snapshot of the whole local lead-gen pipeline: the current dashboard,
its backend, and the complete engine. Good for a code review, a second opinion, or
just as a portable reference. Updated after the LeadFlow dashboard + engine were added._

## What this system does
Scrape local businesses → grade their current website → build a personalized demo site
with a local LLM (Ollama) → draft a compliant outreach email → **a human reviews and
approves in a dashboard, then sends manually**. Nothing auto-sends. $0 API cost — runs
entirely on a local model + a local RAG index.

## The current dashboard
`dashboard_leadflow.html` — light, LeadFlow-style SaaS UI: left sidebar nav, KPI cards
with sparklines + deltas, a lead-growth area chart, a leads-by-niche donut, a recent-leads
table with status pills, a demo-preview modal, and a chat widget. Talks to `fastapi_backend.py`
on :8502. (Two alternate skins also ship: `tesla_style_dashboard_v2.html` (dark glass) and
`tesla_style_dashboard_with_chat.html` (original) — same backend, not included below to keep
this focused.)

## Architecture
```
  ENGINE (Python)                          DASHBOARD LAYER
  pipeline.py  ── orchestrates ↓           fastapi_backend.py (:8502)
  scraper.py   → output/leads.csv               ↑ reads output/, serves JSON
  grader.py    → output/leads_graded.csv        │
  rag_setup.py → chroma_db/                 dashboard_leadflow.html (browser/PWA)
  demo_gen_local.py → output/demos/<slug>/index.html
  outreach_local.py → output/outreach/<slug>.md
  dashboard.py → Streamlit review UI (:8501, alternative to the web dashboard)
```
Contract: the engine writes `output/leads_graded.csv` (+ demos + outreach drafts); the
backend only reads those. Verified: statuses, hot flags, and slug naming match across both.

---

# Current dashboard

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

# Backend

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

```python
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

```

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

# PWA + prompts + config

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

```markdown
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

```

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

---

## Review prompt (paste this above when sending to another model)
> You are a senior engineer reviewing a $0-cost, fully local lead-gen pipeline
> (scrape → grade → local-LLM demo → outreach draft → human approves → human sends;
> nothing auto-sends). Review for correctness, security, and reliability. Flag bugs,
> risky edges, and anything that breaks under real data. Then give prioritized fixes.

## Questions worth asking
1. `fastapi_backend.py` allows CORS `*` and `/api/run-pipeline` shells out with values
   from the POST body — safe given it's exposed via ngrok?
2. Demo HTML and drafts are rendered into the dashboard — any XSS exposure?
3. Engine dedup / hot-lead logic in `grader.py` + `autonomous_orchestrator.py` correct?
4. Graceful degradation when Ollama, the RAG index, or GOOGLE_API_KEY are missing?
