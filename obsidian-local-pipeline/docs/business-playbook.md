# Claude-Powered Local Website Business Guide
**Synthesized from the X post by @bounceidc (July 2026) + practical setup details for Claude Code**

This document compiles the full workflow for using Claude (Pro + Desktop App + Code mode + design skills) to build premium custom one-page websites for local businesses and sell them. It focuses on the complete loop: **find → build → ship → sell**.

The original post emphasizes that the *build* part is now commoditized and fast. The real work (and money) is in consistent, personalized outreach with finished demos.

---

## 1. Overview & Why This Works Right Now

**What's real:**
- Claude Code (in the desktop app) can generate full custom sites from scratch — no templates or Wix-like output.
- Two skills dramatically improve quality and remove the generic "AI look":
  - `frontend-design` (official Anthropic)
  - `UI/UX Pro Max` (community)
- Local businesses (restaurants, gyms, dentists, contractors, realtors, med spas, etc.) still pay $1,000–$5,000 for premium one-pagers. Many have outdated 2015-era sites or none at all.
- A thriving business with an embarrassing site already knows it needs fixing — you're not creating demand, you're capturing it.

**What's not real:**
- Nobody pays you just for knowing how to prompt. The money comes after you do outreach and deliver a finished demo.
- Realistic first deals take consistent effort (20 sends/week is a good target).

**The window:**
Collapsed build cost + closed quality gap + market that hasn't noticed yet = opportunity. It stays open until more people run this loop.

**Core loop (run weekly):**
1. Find 20 businesses on Google Maps (high-rated but bad site).
2. Build **one** strong demo for the niche (not per business).
3. Record 40-second screen capture (desktop + mobile).
4. Send personalized outreach with the video.
5. Follow up.
6. Close → build/host the real site + offer $50/mo care plan.

---

## 2. Prerequisites & Setup

### Get Claude Pro
- Subscribe at claude.ai (or via desktop app). ~$20/month.
- Pro unlocks stronger coding performance and full access to the skills/plugin system.

### Install the Claude Desktop App
- Download official app: https://claude.com/download (Mac, Windows, Linux versions available).
- Install and sign in with your Anthropic account.
- The app includes **Claude Code** features: open local folders as workspaces, generate/edit/preview code, manage skills, and run autonomous sessions.

**Note:** The desktop app may download a large VM bundle (~13 GB) for secure code execution. This is normal for Claude Code functionality.

### Install the Two Key Design Skills
These skills are what make the output look expensive instead of generic AI.

**Option A – Commands in Claude Code (recommended for precision)**
In the desktop app / Claude Code interface, use slash commands:

```bash
# Add marketplaces
/plugin marketplace add anthropics/skills
/plugin marketplace add nextlevelbuilder/ui-ux-pro-max-skill

# Install skills (run after adding marketplaces)
/plugin install frontend-design@anthropics/skills
/plugin install ui-ux-pro-max@ui-ux-pro-max-skill
```

**Option B – GUI in Desktop App**
- Look for **Customize** (left sidebar or + button).
- Go to **Skills** or **Plugins** tab.
- Browse directory or search for the skill names.
- Install `frontend-design` and `UI/UX Pro Max`.
- Enable them globally or per project/workspace.

**What they do:**
- `frontend-design`: Guides production-ready HTML/CSS/JS or React with distinctive typography, creative layouts, thoughtful animations, and actively avoids overused fonts/patterns.
- `UI/UX Pro Max`: Provides a large database of UI styles, color palettes (60+), font pairings (50+), industry-specific design systems, accessibility/performance checklists, and stack-specific guidelines. Great for consistent premium output.

After installation, switch to **auto mode** (or equivalent) so Claude applies the skills without constant permission prompts.

**Tip:** Create a dedicated workspace folder for your client projects. Open it in the desktop app.

---

## 3. Building High-Quality Demos

### Preparation (once per niche)
- Pick a niche (e.g., Thai restaurants, local gyms, dental practices).
- Gather 3–5 reference screenshots from Dribbble, Awwwards, or Pinterest ("modern [niche] website design").
- Put them in a `/reference` folder inside your workspace.
- These images are shown to Claude — better than describing design in words.

### The Master Build Prompt
Use a structured prompt. The highest-leverage part is the final sentence that forces Claude to ask clarifying questions before generating code.

**Copy-paste template (customize the bracketed parts):**

```
Build a premium, modern, agency-quality one-page website for [SPECIFIC BUSINESS TYPE / NICHE, e.g. a Thai restaurant called "Thai Basil" in Cheshire CT].

Key requirements:
- Looks like a high-end agency built it (distinctive typography, excellent visual hierarchy, thoughtful spacing, subtle professional animations).
- Outstanding mobile experience (most visitors will see this version).
- Clear calls-to-action that drive real business results (reservations, bookings, leads, calls).
- Sections to include: [list them, e.g. Hero with strong headline + primary CTA, About/Story, Menu/ Services highlights, Social proof/testimonials, Location & contact, Footer].

Use the installed `frontend-design` and `UI/UX Pro Max` skills for production-grade output. Avoid generic AI aesthetics, overused fonts (e.g. Inter as default), template-like layouts, or low-effort components.

Before writing any code, ask me 5–7 specific clarifying questions about:
- Visual direction and overall aesthetic
- Color palette preferences or brand colors
- Priority sections and information hierarchy
- Copy tone and voice
- Animation level and interactions
- Target customer and key conversions

Once I answer, generate a complete, self-contained, high-quality HTML/CSS/JS site (single file or clean project structure) that I can immediately preview and iterate on.
```

**Why this works:** Claude stops, asks smart questions, and your answers become the foundation. You fight the output far less later.

### Polish & Iteration Passes (do these every time)
After the first version lands (~10 minutes):

**Pass 1 – Grade it**
```
Grade this website against premium agency standards. List specific, prioritized improvements for hierarchy, typography, spacing, visual weight, color usage, and mobile behavior. Be direct and constructive.
```

**Pass 2 – Make it expensive (batch improvements)**
```
Make this site feel expensive and premium. Apply a batch of improvements focused on:
- Tighter visual hierarchy and breathing room
- More distinctive and intentional typography
- Better color harmony and contrast
- Subtle, purposeful animations and micro-interactions
- Professional polish on buttons, cards, and sections

Do not fix things one by one — propose and apply a cohesive set of upgrades.
```

**Final Mobile Pass (critical)**
```
Perform a dedicated mobile optimization pass. Decide what hides, tightens, stacks, resizes, or becomes sticky on small screens. Ensure the mobile version feels intentional and not just a shrunk desktop site. This is the version most real visitors will see.
```

**Efficiency tip from the post:** Build **one demo per niche**, not per business. The Thai restaurant demo works for all Thai restaurants on your list. Record one 40-second video of it scrolling on desktop and phone — that video becomes your outreach ammo.

---

## 4. Finding Buyers on Google Maps (15 minutes per batch)

You're not looking for businesses that "need" a website. You're looking for **profitable businesses with bad/outdated sites**.

**Search strategy:**
- Open Google Maps.
- Pick one niche + one city/area (e.g., "Thai restaurant Cheshire CT" or "gym near me").
- Filter for 4.4+ stars (thriving businesses).
- Look for sites that look old, broken on mobile, missing key sections, or nonexistent.

**Build a simple spreadsheet list of 20:**
- Business name
- Contact (owner email if findable, or Instagram/Facebook — wherever owners actually respond)
- One specific, observable problem with their current site (this becomes your opener)

**Why high-rated businesses?** A failing business won't spend $1,500–$2,500 on a site. A successful one with an embarrassing site already feels the pain and has the budget.

---

## 5. Outreach & Closing (The Part Most People Skip)

You have a list + a niche demo + a short video. Now send.

**Recommended message template** (email or Instagram DM — wherever the owner is):

```
Hi [Owner Name or "Team at Business Name"],

I put together a quick demo of what a modern, high-converting website could look like for [Business Name / your niche].

[Attach or embed the 40-second screen recording video here]

A few things stood out when I looked at your current site: [specific problem you noted, e.g. "the menu doesn't display properly on phones" or "there's no easy way for customers to book online"].

I build clean, premium one-page sites like the one in the video. Flat price for the project is $[500–800 small market / $1,000–2,500 metro]. I also offer an optional $50/month care plan that covers hosting, updates, and small edits.

Would you be open to a quick look at the demo and chatting about whether something like this would help bring in more customers?

Best,
[Your Name]
```

**Rules that make it work (from the post):**
- Lead with the **video**, not your credentials.
- Name **one specific problem** with *their* site.
- State the flat price plainly.
- **Never say "AI-built"** — sell the outcome (more customers, better mobile experience, professional image), not the method.
- Follow up 3 days later if no reply: "Did the video land okay? Happy to tweak the demo to better match what you need."

**Pricing guidance:**
- Small markets / simpler niches: $500–$800
- Metro / higher-value niches (med spas, professional services): $1,000–$2,500
- Add-on: $50/month recurring care plan (hosting + edits). 10 care clients = $500/mo passive for minimal work.

**Realistic ramp:**
- 20 sends → 3–6 replies → 0–2 deals (most yeses come after follow-up).
- Two solid clients per month at ~$1,500 average = $3,000/month on part-time hours.
- Your growing library of demos makes every subsequent month faster.

**What kills 90% of attempts:**
- Polishing one demo for a week instead of sending it.
- Pitching the technology ("AI website") instead of outcomes.
- Choosing niches you personally like instead of niches that pay.
- No follow-up.
- Pricing too low ($200 range signals low quality).

---

## 6. Shipping the Real Site

- Only buy hosting/domain **after** the client says yes.
- Simple static hosting (Netlify, Vercel, or basic provider) + custom domain works great.
- Cost: Often $40–45 for the first year with a free domain.
- Common mistake: Zipping the whole project folder instead of the contents. `index.html` must be at the root of the zip.

---

## 7. Realistic Expectations & Mindset

This is **not** "press button, get rich." It is a repeatable system that rewards consistent execution.

- Building speed improves quickly once skills are installed and you have reference workflows.
- The bottleneck for most people is **sending the messages**. The ones making money treat it like a small sales job (20 personalized sends + follow-ups per week).
- Start small: One niche, one demo, 20 sends. Learn from replies.
- Track everything in a simple spreadsheet (businesses contacted, replies, deals closed, revenue).
- Legal/tax note: Treat this as a real small business (invoicing, contracts, taxes). Simple one-page service agreements protect both sides.

---

## 8. How to Use This Document with Claude

**Recommended workflow:**
1. Upload or paste this entire Markdown file into a new **Claude Project** (or chat with file upload).
2. Tell Claude: "Use this guide as your knowledge base. When I ask you to build a website for [niche/business], follow the master prompt structure, apply the installed skills, and go through the polish passes."
3. For each new client/niche, start a fresh conversation or sub-project and reference this file.
4. Ask Claude to help you:
   - Customize the master prompt for a specific business
   - Draft personalized outreach messages
   - Analyze a competitor's site and suggest improvements
   - Generate follow-up templates
   - Brainstorm niche ideas or Google Maps search strings for your area

---

## Bonus: Quick-Start Checklist

- [ ] Claude Pro active
- [ ] Desktop app installed and signed in
- [ ] `frontend-design` and `UI/UX Pro Max` skills installed globally
- [ ] Workspace folder created and opened in the app
- [ ] First niche chosen + 3–5 reference images collected
- [ ] Master prompt customized and tested on one demo
- [ ] 40-second demo video recorded
- [ ] Spreadsheet template ready for 20 businesses
- [ ] First 20 outreach messages drafted and ready to send

---

**Document version:** July 13, 2026  
**Source inspiration:** X post by @bounceidc (full thread)  
**Compiled & enhanced for practical use with Claude Code**

---

*This is a synthesized, actionable guide. The interface and exact skill installation commands in Claude may evolve — always check the latest in-app help or official docs if a command doesn't work. The principles (demo-first selling + consistent personalized outreach) remain powerful regardless of tool changes.*

**Next action:** Pick one niche you're interested in testing, tell me (or tell Claude after uploading this file), and we can generate your first customized prompt + starter site right away. 

You now have everything in one clean Markdown file ready to feed to Claude. Upload it, reference it, and start running the loop. Good luck!