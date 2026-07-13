# Obsidian Labs — Tesla-Inspired Dashboard Prompt for Claude

**Purpose**  
This file contains everything you need to generate a clean, cool-looking, easy-to-use dashboard for the Obsidian Labs local lead-generation pipeline.  

The goal is a **premium but simple** Tesla/Apple-style interface (dark glassmorphism, animated status ring, nice KPI cards, minimal clutter) that still works 100% with your existing FastAPI backend and keeps every current feature.

You can copy the big prompt block below and paste it directly into Claude (or any strong LLM).

---

## Ready-to-Paste Prompt for Claude

```
You are a senior frontend engineer who specializes in premium, minimalist, Tesla and Apple-inspired interfaces that still feel simple and usable every day.

I run a small web design business called Obsidian Labs. I have a fully local AI pipeline that:
- Scrapes local businesses
- Grades their current websites
- Generates personalized demo websites using a local LLM (Ollama)
- Drafts outreach emails

Nothing ever sends automatically. A human reviews leads, demos, and drafts in a dashboard, then approves manually before sending anything.

### Current Working Dashboard
I already have a functional dashboard (`tesla_style_dashboard_with_chat.html` + `fastapi_backend.py` running on port 8502). It can:
- Load live leads, demos, and outreach drafts from the backend
- Preview demo HTML in an iframe with Desktop / Tablet / Mobile toggle
- Show outreach drafts with Approve buttons (approval only logs to a CSV — nothing is sent)
- Has a built-in chat widget that talks to local Ollama through the backend
- Has a "Run Pipeline" button
- Is a PWA (installable on phone)
- Lets me change the backend URL via a settings gear (stored in localStorage)

The current version works but looks basic (light theme, tables, red accents). I want it to look **cool and premium** while staying easy and simple to use.

### Design Vision
Use the Tesla + Apple inspired style from the attached Claude blueprint:
- Dark theme with radial gradient background (dark #0b0b0b at top fading to black)
- Glassmorphism: frosted glass cards with backdrop-filter blur, subtle borders, soft shadows, and gentle hover lift
- Minimal clean typography
- Smooth animations and transitions
- Animated status / AI ring (blue accent)
- Clean KPI cards (including a "Potential Revenue" card)
- Keep the whole interface feeling simple and calm — not busy or overwhelming

### Must Keep (Do Not Remove or Break)
- All existing functionality with the current FastAPI backend (no changes needed to fastapi_backend.py)
- Demo preview iframe with device size toggle
- Outreach draft list with Approve buttons
- Built-in AI chat widget (calls local Ollama)
- "Run Pipeline" button
- Settings gear for backend URL
- PWA support (manifest + service worker references)
- Approval system only logs — never sends anything
- Fully local operation

### Specific Improvements I Want
1. Apply the full dark glassmorphism theme and card styles from the Claude Tesla Dashboard Blueprint.
2. Add an animated Status / AI Ring (use the CSS from the blueprint). Place it prominently — maybe as "Pipeline Status" or "AI Health".
3. Create nice KPI cards at the top:
   - Leads
   - Hot Leads
   - Demos Generated
   - Outreach Drafts
   - Potential Revenue (calculate hot leads × $2,500 as a starting point, or make it easy to adjust)
4. Add a lightweight Command Palette (Ctrl/Cmd + K) that feels Tesla-like. It should let me quickly search leads, switch sections, refresh data, or open the chat.
5. Add a small Live Activity Feed (recent pipeline actions, new leads, approvals). Keep it simple.
6. Improve empty states and loading states so everything feels polished.
7. Prefer cards over heavy tables where it improves the visual feel without adding complexity.
8. Keep the layout clean and simple (header + main content area is fine). Make it mobile-friendly and PWA-ready.

### Output Instructions
- Return a **single self-contained HTML file** (everything in one file like the current dashboard).
- It must work perfectly with the existing FastAPI backend on port 8502 without any backend changes.
- Include the PWA manifest and service worker links so it remains installable.
- Add helpful code comments for new sections.
- Prioritize **easy + simple daily use** while making it look genuinely cool and premium.

Use the CSS variables, glassmorphism card styles, and status ring example from the Claude Tesla Dashboard Blueprint I provided earlier as your visual foundation.

Generate the complete updated HTML file now.
```

---

## Claude Tesla Dashboard Blueprint — Key CSS (for reference)

Copy this into Claude if the model needs the exact styles:

```css
:root {
  --bg: #0b0b0b;
  --panel: rgba(255, 255, 255, .06);
  --border: rgba(255, 255, 255, .08);
  --accent: #3b82f6;
  --text: #f5f5f5;
  --muted: #9ca3af;
  --radius: 18px;
}

body {
  background: radial-gradient(circle at top, #111, #000);
  color: var(--text);
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

.card {
  backdrop-filter: blur(18px);
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  transition: transform .25s ease, box-shadow .25s ease;
}

.card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
}

/* Animated Status Ring */
.ring {
  width: 180px;
  height: 180px;
  border-radius: 50%;
  border: 8px solid rgba(59, 130, 246, .2);
  box-shadow: 0 0 30px rgba(59, 130, 246, .4);
  animation: pulse 2s infinite ease-in-out;
}

@keyframes pulse {
  50% {
    box-shadow: 0 0 50px rgba(59, 130, 246, .8);
  }
}
```

---

## How to Use This File

1. Open this Markdown file.
2. Copy the entire block under **"Ready-to-Paste Prompt for Claude"**.
3. Paste it into Claude (or your preferred LLM).
4. (Optional) Also attach or paste your current `tesla_style_dashboard_with_chat.html` if you want Claude to use it as the exact base.
5. Ask Claude to output the full single-file HTML.
6. Save the result as `dashboard.html` (or similar) and test it with your running FastAPI backend.

---

## Notes & Guardrails

- The new dashboard must remain **100% local** and respect the existing guardrails (approvals only log — nothing auto-sends).
- Keep the experience **easy and simple** for daily use while making it look cool and premium.
- No changes are required to `fastapi_backend.py` or the pipeline scripts.
- This version focuses on the **computer/local** experience first (cloud/hybrid access can be added later).

---

**File created:** 2026-07-13  
**For:** Robert Castro – Obsidian Labs Dashboard v2

You can now send the prompt above directly to Claude. Let me know when you want the next step (full generated HTML from me, cloud setup guide, PDF version of this file, etc.).
