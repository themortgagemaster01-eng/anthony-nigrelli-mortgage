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
