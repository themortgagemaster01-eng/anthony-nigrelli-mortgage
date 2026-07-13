# Claude Implementation Guide – Tesla-Inspired AI Dashboard

## Design Goals
- Tesla + Apple inspired UI
- Glassmorphism
- Minimal typography
- Keyboard-first
- Mobile-first PWA
- AI-first workflow

## Color Palette
```css
:root{
 --bg:#0b0b0b;
 --panel:rgba(255,255,255,.06);
 --border:rgba(255,255,255,.08);
 --accent:#3b82f6;
 --text:#f5f5f5;
 --muted:#9ca3af;
 --radius:18px;
}
body{
 background:radial-gradient(circle at top,#111,#000);
 color:var(--text);
 font-family:Inter,sans-serif;
}
.card{
 backdrop-filter:blur(18px);
 background:var(--panel);
 border:1px solid var(--border);
 border-radius:var(--radius);
 transition:.25s;
}
.card:hover{transform:translateY(-3px);}
```

## Landing Dashboard
- Greeting
- AI Status Ring (animated)
- Revenue cards
- Pipeline cards
- Live activity feed
- AI chat

## Layout
```
+-------------------------------+
| Header                        |
+----------+--------------------+
| Sidebar  | Mission Control    |
|          | KPI Cards          |
|          | Activity Feed      |
|          | AI Chat            |
+----------+--------------------+
```

## Components
### KPI Card
```html
<div class="card">
 <h3>Potential Revenue</h3>
 <h1>$43,500</h1>
 <small>+12%</small>
</div>
```

### Status Ring
```css
.ring{
 width:180px;height:180px;border-radius:50%;
 border:8px solid rgba(59,130,246,.2);
 box-shadow:0 0 30px rgba(59,130,246,.4);
 animation:pulse 2s infinite;
}
@keyframes pulse{
50%{box-shadow:0 0 50px rgba(59,130,246,.8);}
}
```

## Features
1. Command palette (Ctrl/Cmd+K)
2. Voice control
3. Before/after preview slider
4. Interactive pipeline
5. Live AI activity
6. Mission Control map
7. Mobile bottom navigation

## Suggested Stack
- Next.js
- React
- Tailwind CSS
- Framer Motion
- shadcn/ui
- Supabase
- Cloudflare R2
- Vercel

## Claude Instructions
Build a premium production-ready interface that feels like Tesla software. Avoid tables unless necessary. Use cards, subtle animation, frosted glass, dark theme, responsive layout, accessibility, and clean component architecture.
