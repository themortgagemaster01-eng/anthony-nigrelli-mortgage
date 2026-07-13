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
