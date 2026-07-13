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
