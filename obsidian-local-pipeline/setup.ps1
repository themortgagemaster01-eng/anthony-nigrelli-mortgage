<#
  Obsidian Labs - one-shot setup & launch (Windows PowerShell)
  --------------------------------------------------------------
  Paste this whole file into a PowerShell window (or run:  .\setup.ps1 )
  It will:
    1. check Git / Python / Ollama are installed
    2. make sure the two Ollama models are pulled
    3. copy the new dashboard files into your project folder
    4. install the Python packages
    5. launch Ollama + the backend in their own windows
    6. open the dashboard in your browser

  Nothing here ever sends an email. Safe to re-run - it skips steps already done.
  Edit the paths in the CONFIG block below only if your folders differ.
#>

# ============================ CONFIG ============================
$RepoPath     = "C:\Users\Laptop\obsidian-local-pipeline"
$NewFilesSrc  = "C:\Users\Laptop\My Drive\Shipper Vault\autonomous_system_2026-07-10"
$GitEmail     = "themortgagemaster01@gmail.com"
$GitName      = "Robert"
$BackendPort  = 8502
$Models       = @("qwen2.5:14b-instruct-q4_K_M", "nomic-embed-text")
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
    Say "  Install them first:" "Red"
    Say "    Git:    https://git-scm.com/download/win"
    Say "    Python: https://www.python.org/downloads/  (tick 'Add to PATH')"
    Say "    Ollama: https://ollama.com/download"
    return
}
Say "  OK - all three found." "Green"

# make sure git knows who you are (fixes 'unable to auto-detect email address')
if (-not (git config --global user.email)) { git config --global user.email $GitEmail }
if (-not (git config --global user.name))  { git config --global user.name  $GitName }

# --- 2. project folder ---
Say "[2/6] Locating project folder..." "Yellow"
if (-not (Test-Path $RepoPath)) {
    Say "  Not found at $RepoPath" "Red"
    Say "  Clone it first, then re-run this script:" "Red"
    Say "    git clone https://github.com/themortgagemaster01-eng/obsidian-local-pipeline.git `"$RepoPath`""
    return
}
Set-Location $RepoPath
try { git pull --ff-only 2>$null } catch { Say "  (skipped git pull - not a problem)" "DarkGray" }
Say "  Using $RepoPath" "Green"

# --- 3. copy in the new dashboard files ---
Say "[3/6] Copying new dashboard files..." "Yellow"
if (Test-Path $NewFilesSrc) {
    Copy-Item "$NewFilesSrc\*" -Destination $RepoPath -Recurse -Force
    Say "  Copied from Shipper Vault." "Green"
} else {
    Say "  Source folder not found: $NewFilesSrc" "DarkYellow"
    Say "  Skipping copy - assuming the files are already in the project folder." "DarkYellow"
}

# --- 4. python packages ---
Say "[4/6] Installing Python packages..." "Yellow"
$venv = Join-Path $RepoPath "venv\Scripts\Activate.ps1"
if (Test-Path $venv) { . $venv; Say "  venv activated." "DarkGray" }
python -m pip install --quiet --upgrade pip
python -m pip install --quiet fastapi uvicorn pydantic requests pillow python-dotenv schedule
Say "  Packages installed." "Green"

# --- 5. ollama models ---
Say "[5/6] Checking Ollama models (first run may download several GB)..." "Yellow"
$installed = (ollama list) 2>$null
foreach ($m in $Models) {
    if ($installed -match [regex]::Escape($m)) { Say "  Already have $m" "DarkGray" }
    else { Say "  Pulling $m ..." "DarkGray"; ollama pull $m }
}
Say "  Models ready." "Green"

# --- 6. launch everything ---
Say "[6/6] Launching Ollama + backend in their own windows..." "Yellow"
Start-Process powershell -ArgumentList '-NoExit','-Command','Write-Host "Ollama - keep me open"; ollama serve'
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList '-NoExit','-Command',"Set-Location '$RepoPath'; Write-Host 'Backend - keep me open'; uvicorn fastapi_backend:app --port $BackendPort"
Start-Sleep -Seconds 3

$dashboard = Join-Path $RepoPath "tesla_style_dashboard_v2.html"
if (-not (Test-Path $dashboard)) { $dashboard = Join-Path $RepoPath "tesla_style_dashboard_with_chat.html" }
if (Test-Path $dashboard) { Start-Process $dashboard }

Say "`n=== Done! ===" "Cyan"
Say "Two new windows opened (Ollama + Backend) - leave them running." "White"
Say "Dashboard opened in your browser. Click 'Run Pipeline' to gather leads." "White"
Say "To use it on your phone: run 'ngrok http $BackendPort', then paste that URL into the dashboard's gear icon.`n" "White"
