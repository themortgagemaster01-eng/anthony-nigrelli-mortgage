# How to run Obsidian Labs — no typing required

You never have to touch PowerShell. After a one-time install of two free programs,
running the whole system is a **double-click**.

## One-time setup (about 15 minutes)

**1. Install two programs** (normal double-click installers — no terminal):
- **Python** — https://www.python.org/downloads/
  → On the very first screen, **tick "Add Python to PATH"**, then Install.
- **Ollama** — https://ollama.com/download → Install.

**2. Get a Google API key** (free tier is plenty):
- Follow the steps in the chat, or the short version:
  console.cloud.google.com → new project → enable **Places API** + **PageSpeed Insights API**
  → Credentials → **Create API key** → copy it.

**3. Get the project onto your laptop** (in the browser, no terminal):
- Go to the repo on github.com (signed in).
- Switch to the branch **`claude/powershell-capabilities-pmxppx`**.
- Click the green **Code** button → **Download ZIP**.
- Unzip it (right-click → Extract All). Open the `obsidian-local-pipeline` folder inside.

## Run it — every time

**Double-click `START.bat`.**

- The **first** time, it installs everything and asks you to **paste your Google API key** — paste it, press Enter, and wait (the AI models are a few GB, one-time).
- It then opens two small windows (Ollama + Backend) and launches the **dashboard** in your browser.
- Click **Run Pipeline** and your leads start coming in.

**Every day after**, just double-click `START.bat` again — it skips setup and opens straight to the dashboard in a few seconds.

> Tip: right-click `START.bat` → **Send to → Desktop (create shortcut)** so you have an icon to double-click. You can rename the shortcut "Obsidian Labs".

## Notes
- Keep the two little windows (Ollama + Backend) open while you use the dashboard. Closing them stops the app. Double-click `START.bat` to bring it all back.
- If Windows shows a blue "Windows protected your PC" box the first time, click **More info → Run anyway** (it's your own file).
- If the Ollama window says "address already in use," that's fine — Ollama was already running.
- To change your API key later, delete the `.env` file and double-click `START.bat` again; it'll ask for the key again.

## Want it on your phone too?
The dashboard works on your phone once the backend is reachable over the internet:
1. Install **ngrok** (ngrok.com), run `ngrok http 8502`.
2. Copy the `https://…ngrok…` link it shows.
3. Open the dashboard on your phone, tap the settings/backend option, paste that link.
(That part still uses a terminal for ngrok — ask and I can wrap it into the launcher too.)
