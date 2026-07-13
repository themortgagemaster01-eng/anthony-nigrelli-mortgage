<#
  Obsidian Labs - one-shot setup & launch (Windows PowerShell)
  --------------------------------------------------------------
  This MERGES the new dashboard/backend files (the folder this script lives in)
  into your existing engine repo, installs deps, pulls the Ollama models, then
  launches Ollama + the backend and opens the dashboard.

  Easiest way to run it (clones the new files, then runs this):
     cd $env:USERPROFILE
     git clone --branch claude/powershell-capabilities-pmxppx --depth 1 `
       https://github.com/themortgagemaster01-eng/anthony-nigrelli-mortgage.git obsidian_new
     cd obsidian_new\obsidian-local-pipeline
     powershell -ExecutionPolicy Bypass -File .\setup.ps1

  Nothing here ever sends an email. Safe to re-run.
  Edit the CONFIG block only if your folders differ.
#>

# ============================ CONFIG ============================
$Engine     = "C:\Users\Laptop\obsidian-local-pipeline"   # where the engine lives (pipeline.py, scraper.py, ...)
$Source     = $PSScriptRoot                               # the new files = the folder THIS script is in
$EngineRepo = "https://github.com/themortgagemaster01-eng/obsidian-local-pipeline.git"
$GitEmail   = "themortgagemaster01@gmail.com"
$GitName    = "Robert"
$BackendPort = 8502
$Models     = @("qwen2.5:14b-instruct-q4_K_M", "nomic-embed-text")
# ===============================================================

$ErrorActionPreference = "Stop"
function Say($m,$c="White"){ Write-Host $m -ForegroundColor $c }
function Have($cmd){ [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

Say "`n=== Obsidian Labs setup ===`n" "Cyan"

# --- 1. prerequisites ---
Say "[1/6] Checking Git, Python, Ollama..." "Yellow"
$missing = @()
foreach ($c in "git","python","ollama") { if (-not (Have $c)) { $missing += $c } }
if ($missing.Count) {
    Say "  Missing: $($missing -join ', ')" "Red"
    Say "    Git:    https://git-scm.com/download/win"
    Say "    Python: https://www.python.org/downloads/  (tick 'Add to PATH')"
    Say "    Ollama: https://ollama.com/download"
    return
}
Say "  OK - all three found." "Green"
if (-not (git config --global user.email)) { git config --global user.email $GitEmail }
if (-not (git config --global user.name))  { git config --global user.name  $GitName }

# --- 2. make sure the ENGINE repo is present on this laptop ---
Say "[2/6] Locating engine repo..." "Yellow"
if (-not (Test-Path (Join-Path $Engine "pipeline.py"))) {
    if (-not (Test-Path $Engine)) {
        Say "  Engine not found - cloning $EngineRepo ..." "DarkGray"
        git clone $EngineRepo $Engine
    } else {
        Say "  Folder exists but pipeline.py is missing." "DarkYellow"
        Say "  Make sure $Engine is your obsidian-local-pipeline clone, then re-run." "DarkYellow"
    }
} else {
    try { Push-Location $Engine; git pull --ff-only 2>$null; Pop-Location } catch {}
}
Say "  Engine: $Engine" "Green"

# --- 3. merge the NEW files (this folder) into the engine repo ---
Say "[3/6] Copying new dashboard + backend files into the engine..." "Yellow"
if ($Source -and ($Source -ne $Engine)) {
    Get-ChildItem -Path $Source -File | Where-Object { $_.Name -ne "setup.ps1" } |
        Copy-Item -Destination $Engine -Force
    foreach ($d in "docs") {
        $sd = Join-Path $Source $d
        if (Test-Path $sd) { Copy-Item $sd -Destination $Engine -Recurse -Force }
    }
    Say "  Copied new files into $Engine" "Green"
} else {
    Say "  (Script is already inside the engine folder - nothing to copy.)" "DarkGray"
}

# --- 4. python packages ---
Say "[4/6] Installing Python packages..." "Yellow"
$venv = Join-Path $Engine "venv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv; Say "  venv activated." "DarkGray" }
python -m pip install --quiet --upgrade pip
$reqs = Join-Path $Engine "requirements.txt"
if (Test-Path $reqs) { python -m pip install --quiet -r $reqs }
else { python -m pip install --quiet fastapi uvicorn pydantic requests pillow python-dotenv schedule }
Say "  Packages installed." "Green"

# --- 4b. .env sanity ---
$envFile = Join-Path $Engine ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $Engine ".env.example") $envFile -ErrorAction SilentlyContinue
    Say "  Created .env from .env.example - add your GOOGLE_API_KEY before running the pipeline." "DarkYellow"
} elseif (-not (Select-String -Path $envFile -Pattern '^GOOGLE_API_KEY=.+' -Quiet)) {
    Say "  NOTE: GOOGLE_API_KEY is not set in .env - scrape/grade stages need it (Places + PageSpeed)." "DarkYellow"
}

# --- 5. ollama models ---
Say "[5/6] Checking Ollama models (first run may download several GB)..." "Yellow"
$installed = (ollama list) 2>$null
foreach ($m in $Models) {
    if ($installed -match [regex]::Escape($m)) { Say "  Already have $m" "DarkGray" }
    else { Say "  Pulling $m ..." "DarkGray"; ollama pull $m }
}
Say "  Models ready." "Green"

# --- 6. launch ---
Say "[6/6] Launching Ollama + backend..." "Yellow"
Start-Process powershell -ArgumentList '-NoExit','-Command','Write-Host "Ollama - keep me open"; ollama serve'
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList '-NoExit','-Command',"Set-Location '$Engine'; Write-Host 'Backend - keep me open'; uvicorn fastapi_backend:app --port $BackendPort"
Start-Sleep -Seconds 3

$dashboard = Join-Path $Engine "dashboard_leadflow.html"
if (-not (Test-Path $dashboard)) { $dashboard = Join-Path $Engine "tesla_style_dashboard_v2.html" }
if (-not (Test-Path $dashboard)) { $dashboard = Join-Path $Engine "tesla_style_dashboard_with_chat.html" }
if (Test-Path $dashboard) { Start-Process $dashboard }

Say "`n=== Done! ===" "Cyan"
Say "Two new windows opened (Ollama + Backend) - leave them running." "White"
Say "Dashboard opened in your browser. Click 'Run Pipeline' to gather your first leads." "White"
Say "Phone access: run 'ngrok http $BackendPort', then paste that URL into the dashboard settings.`n" "White"
