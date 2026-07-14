# seed_demos

Drop any past demo websites here as `.html` files and they'll show up in the dashboard.

- Put a file like `demo_wallys-super-service.html` (or any `.html`) in this folder.
- Run `python import_demos.py` (or just launch `START.bat` — it imports automatically).
- The demo appears in the dashboard's **Demos** tab, and if its name matches a lead
  (e.g. "Wally's Super Service"), it also previews when you click that lead.

`import_demos.py` also auto-scans your Google Drive and Obsidian vault (the
`GDRIVE_PATH` / `OBSIDIAN_VAULT_PATH` in `.env`) for `demo_*.html` files, so demos
you already have there get pulled in without copying them here first.
