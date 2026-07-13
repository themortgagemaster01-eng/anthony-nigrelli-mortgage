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
