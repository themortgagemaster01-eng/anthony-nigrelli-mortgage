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
