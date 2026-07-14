# Obsidian Labs — Automated Setup Runbook (for a Claude coding agent)

**How to use this (for the human):** Open this project in Claude Code on your laptop
(desktop app or CLI), paste or attach this file, and say:
*"Follow AGENT_SETUP.md to set up and launch this app on my machine."*
The agent will do everything below. The only thing it will ask you for is your Google API key.

---

## Agent instructions

You are setting up a **fully local, $0-cost AI lead-generation pipeline** on the user's
**Windows** laptop. Flow: scrape local businesses → grade their websites → generate demo
sites with a local LLM (Ollama) → draft outreach emails → the user reviews/approves in a
dashboard → the user sends manually. **Nothing auto-sends. Never send email. Never commit
secrets.** Work step by step, verify each step, and report a short status at the end.

### Guardrails
- Do not print, log, or commit the contents of `.env` or the API key. `.env` is gitignored — keep it that way.
- Do not run the `outreach`/send anything externally. This setup only installs and launches.
- If a step fails, stop, show the exact error, and propose the fix — don't silently continue.
- Prefer detecting-then-skipping: never reinstall something that's already present and working.

### Step 1 — Detect what's already installed
Run these and record which succeed:
```powershell
git --version
python --version
ollama --version
ngrok --version   # optional, only needed for phone access
```
For anything missing, install it with winget (Windows Package Manager). If winget itself is
missing, direct the user to the download page instead.
```powershell
winget install --id Git.Git -e --source winget
winget install --id Python.Python.3.12 -e --source winget   # ensure it's on PATH
winget install --id Ollama.Ollama -e --source winget
winget install --id ngrok.ngrok -e --source winget          # optional (phone access)
```
After installing Python, open a fresh shell (or refresh PATH) so `python` resolves.

### Step 2 — Get the project onto the laptop
If you are already inside the `obsidian-local-pipeline` folder (it contains `fastapi_backend.py`
and `requirements.txt`), use it in place. Otherwise clone it:
```powershell
cd $env:USERPROFILE
git clone --branch claude/powershell-capabilities-pmxppx --depth 1 `
  https://github.com/themortgagemaster01-eng/anthony-nigrelli-mortgage.git obsidian_new
cd obsidian_new\obsidian-local-pipeline
```
If the user already has an engine folder at `C:\Users\Laptop\obsidian-local-pipeline`, copy the
files from this folder into it and work there instead (so engine + dashboards live together).

### Step 3 — Python environment + dependencies
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```
Verify: `python -c "import fastapi, uvicorn, pandas, streamlit; print('deps ok')"`.

### Step 4 — Local AI models (first time downloads several GB)
```powershell
ollama pull qwen2.5:14b-instruct-q4_K_M
ollama pull nomic-embed-text
```
Verify: `ollama list` shows both models.

### Step 5 — Configuration + API key
```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```
Then **ask the user for their Google API key** (needs *Places API* + *PageSpeed Insights API*
enabled). Write it into `.env` without echoing it back:
```powershell
$key = Read-Host "Paste your Google API key"
(Get-Content .env) -replace '^GOOGLE_API_KEY=.*', "GOOGLE_API_KEY=$key" | Set-Content .env
```
Leave the other `.env` values at their defaults unless the user asks to change paths.
If the user's Google Drive / Obsidian vault paths differ from the defaults, update
`GDRIVE_PATH` and `OBSIDIAN_VAULT_PATH` (RAG works better with them, but degrades gracefully).

### Step 5b — Import the user's past demos into the dashboard
The user has previously-built demos in three places. Pull them all in:
```powershell
python import_demos.py            # from Google Drive + Obsidian/Shipper vault + seed_demos/
python import_github_demos.py     # from the user's public GitHub demo repos
```
`import_demos.py` copies each demo to `output\demos\<slug>\index.html` (fix `GDRIVE_PATH` /
`OBSIDIAN_VAULT_PATH` in `.env` first if they don't point at the folders holding the demos,
or drop files into `seed_demos\`). `import_github_demos.py` clones the repos listed at the top
of that file (mahopac-demos, castro-tax-demo, xtrachange-demo, mrnicks-demo, obsidianlabs-demo)
and imports their `index.html` demos, including per-business subfolders in a collection repo
like `mahopac-demos`. After both, run `python -c "import os;print(os.listdir('output/demos'))"`
and report which demos were imported.
Also worth doing if the user wants on-brand output: if they have a real design-standards /
demo prompt in Drive (e.g. `demo_system_prompt_UPDATED_*.md`, `SKILL_obsidian-web-design-standards`),
copy its content over `templates\demo_system_prompt.md` (and their voice doc over
`templates\email_system_prompt.md`).

### Step 6 — Launch
Start each long-running piece in its own window and leave them running:
```powershell
Start-Process powershell -ArgumentList '-NoExit','-Command','ollama serve'
Start-Sleep 2
Start-Process powershell -ArgumentList '-NoExit','-Command',"cd '$PWD'; .\venv\Scripts\Activate.ps1; uvicorn fastapi_backend:app --port 8502"
Start-Sleep 5
Start-Process .\dashboard_leadflow.html
```

### Step 7 — Verify it works
```powershell
# backend should return JSON with leads/hot/demos/outreach counts
Invoke-RestMethod http://localhost:8502/api/status
```
Success = that returns an object (zeros are fine before the first pipeline run) and the
dashboard opens in the browser. Then optionally kick a tiny test run:
```powershell
python pipeline.py --stage scrape --towns Mahopac --niches dentist --limit 2
python pipeline.py --stage grade
```
Check `output\leads_graded.csv` exists and the dashboard shows the leads after a refresh.

### Step 8 — (Optional) phone access
Only if the user wants it and ngrok is installed + authtokened:
```powershell
Start-Process powershell -ArgumentList '-NoExit','-Command','ngrok http 8502'
```
Then read the `https://…ngrok…` URL from `http://localhost:4040/api/tunnels` and give it to the
user to paste into the dashboard's settings on their phone. (There is also a `PHONE_ACCESS.bat`
that does this in one double-click.)

### Report back
End with a short summary: what was already installed, what you installed, whether the backend
responded, whether the test run produced leads, and any follow-ups the user must do (e.g. enable
a Google API, add billing, fix a Drive path). Do not include the API key in the summary.

---

## Notes for the agent
- `scraper.py` and `grader.py` are faithful re-implementations of the documented Google
  Places / PageSpeed interface — they need `GOOGLE_API_KEY`. If the user has their own
  versions, prefer theirs.
- The `templates/*.md` prompts are starter content; they work, but the user's real
  design-standards / voice docs (via the RAG index) make output more on-brand.
- Three dashboard skins ship (`dashboard_leadflow.html` default, `tesla_style_dashboard_v2.html`,
  `tesla_style_dashboard_with_chat.html`) — all use the same backend, no backend changes.
- Everything is local. The chat widget and demo/outreach generation call local Ollama only.
