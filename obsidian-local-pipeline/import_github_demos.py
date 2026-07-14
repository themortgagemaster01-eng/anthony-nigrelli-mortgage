#!/usr/bin/env python3
"""
import_github_demos.py - pull demo websites from your GitHub repos into the dashboard.

You keep demos in public GitHub repos under your account (themortgagemaster01-eng),
e.g. `mahopac-demos` (a batch of business demos), `castro-tax-demo`, `xtrachange-demo`,
`mrnicks-demo`, `obsidianlabs-demo`. This script clones each one and copies its demo
HTML into output/demos/<slug>/index.html so the dashboard shows them.

- A repo with an `index.html` at its root  -> one demo, slug = repo name (minus "-demo").
- A repo that is a collection (subfolders each with an index.html, like mahopac-demos)
  -> one demo per subfolder, slug = subfolder name.

Edit the REPOS list below (or create a file `github_demo_repos.txt`, one `owner/repo`
per line) to control what gets pulled. Public repos need no login; private ones use
your normal git credentials.

Usage
-----
    python import_github_demos.py
    python import_github_demos.py owner/repo another/repo
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT_DEMOS = ROOT / "output" / "demos"
REPO_LIST_FILE = ROOT / "github_demo_repos.txt"

OWNER = "themortgagemaster01-eng"
# Default demo repos (edit freely, or use github_demo_repos.txt).
REPOS = [
    f"{OWNER}/mahopac-demos",
    f"{OWNER}/castro-tax-demo",
    f"{OWNER}/xtrachange-demo",
    f"{OWNER}/mrnicks-demo",
    f"{OWNER}/obsidianlabs-demo",
]

EXCLUDE_SUBSTRINGS = ("dashboard", "manifest", "_preview", "mortgage-calculator")


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "demo"


def repo_slug(repo: str) -> str:
    name = repo.split("/")[-1]
    name = re.sub(r"[_-]+demos?$", "", name, flags=re.IGNORECASE)  # drop trailing -demo/-demos
    return slugify(name)


def load_repos(cli_repos: list[str]) -> list[str]:
    if cli_repos:
        return cli_repos
    if REPO_LIST_FILE.exists():
        lines = [l.strip() for l in REPO_LIST_FILE.read_text(encoding="utf-8").splitlines()]
        repos = [l for l in lines if l and not l.startswith("#")]
        if repos:
            return repos
    return REPOS


def clone(repo: str, dest: Path) -> bool:
    url = f"https://github.com/{repo}.git"
    try:
        r = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(dest)],
            capture_output=True, text=True, timeout=120,
        )
        if r.returncode != 0:
            print(f"[gh_demos] could not clone {repo}: {r.stderr.strip().splitlines()[-1] if r.stderr.strip() else 'unknown error'}", file=sys.stderr)
            return False
        return True
    except FileNotFoundError:
        print("[gh_demos] git is not installed - cannot pull GitHub demos.", file=sys.stderr)
        return False
    except subprocess.TimeoutExpired:
        print(f"[gh_demos] timed out cloning {repo}", file=sys.stderr)
        return False


def demos_in_repo(repo_dir: Path, repo: str) -> list[tuple[str, Path]]:
    """Return (slug, html_path) pairs found in a cloned repo."""
    out: list[tuple[str, Path]] = []
    root_index = repo_dir / "index.html"
    if root_index.exists():
        out.append((repo_slug(repo), root_index))
    # subfolder demos (collections like mahopac-demos)
    for idx in repo_dir.rglob("index.html"):
        if idx == root_index:
            continue
        rel = idx.relative_to(repo_dir)
        low = str(rel).lower()
        if any(x in low for x in EXCLUDE_SUBSTRINGS):
            continue
        slug = slugify(idx.parent.name)
        out.append((slug, idx))
    # de-dupe by slug (first wins)
    seen, uniq = set(), []
    for slug, p in out:
        if slug not in seen:
            seen.add(slug)
            uniq.append((slug, p))
    return uniq


def main() -> None:
    repos = load_repos(sys.argv[1:])
    OUTPUT_DEMOS.mkdir(parents=True, exist_ok=True)
    imported: list[str] = []

    for repo in repos:
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "repo"
            if not clone(repo, dest):
                continue
            found = demos_in_repo(dest, repo)
            if not found:
                print(f"[gh_demos] {repo}: no index.html demo found - skipping.")
                continue
            for slug, src in found:
                dest_dir = OUTPUT_DEMOS / slug
                dest_dir.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest_dir / "index.html")
                imported.append(slug)
                print(f"[gh_demos] {repo}:{src.name}  ->  output/demos/{slug}/index.html")

    if imported:
        print(f"[gh_demos] Done. Imported {len(imported)} demo(s): {', '.join(sorted(set(imported)))}. Refresh the dashboard.")
    else:
        print("[gh_demos] No demos imported. Check the REPOS list / your network / git.")


if __name__ == "__main__":
    main()
