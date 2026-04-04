---
name: FinAssist-V2 Design System Audit
description: Established color tokens, typography scale, spacing scale, and known design system deviations as of April 2026
type: project
---

## Color Palette (index.css :root)

- Background: `#000000` (primary), `#0f0f0f` (secondary), `#141414` (card), `#1c1c1c` (elevated)
- Text: `#ffffff` (primary), `#9b9b9b` (secondary), `#5a5a5a` (muted)
- Accent: `#00c805` (Robinhood green) — all accent aliases (blue, cyan, purple, pink) resolve to this same green
- Success: `#00c805` / `#21ce3f`; Warning: `#f0b429` / `#f7c948`; Danger: `#ff3b30` / `#ff6058`
- Border: `rgba(255,255,255,0.08)` default, `rgba(255,255,255,0.15)` hover

**Known issue:** All accent aliases point to `--accent-green`. The `.fund-chip` and `.flip-card-back` reference an indigo/purple color (`rgba(99,102,241,...)`) hardcoded in App.css that is NOT in the token system — this is a token leak from a previous theme.

## Typography

- Font: Inter (system fallback stack)
- Scale: h1=1.875rem, h2=1.375rem, h3=0.8125rem — a 3-level scale with very small h3
- Indicator card labels use 0.6875rem uppercase — smaller than the h3 definition
- Fundamental labels use 0.5625rem — extremely small, likely below comfortable reading at text-muted contrast

## Spacing

8px base grid: xs=4, sm=8, md=16, lg=24, xl=32, 2xl=48

## Border Radius

sm=8px, md=12px, lg=16px, xl=20px — generally consistent

## Shadows

`--shadow-card: 0 4px 24px rgba(0,0,0,0.6)` — single shadow token, no elevation scale

## Component Patterns

- Cards: flat `var(--bg-card)` with `var(--border-color)` border and `var(--shadow-card)`
- Buttons: `.btn-primary` uses accent-green background with black text
- Signals: pill-shaped badges using success/warning/danger bg+color pairs
- Flip cards: 3D CSS perspective flip for indicator explanations
- Sparklines: Recharts AreaChart in 80x40px containers

## Layout

- App: single-column, max-width 1280px, centered
- Indicators: 4-col grid collapsing to 2-col at 1024px, 1-col at 640px
- Chart+Prediction: 1.6fr / 1fr split collapsing to 1-col at 900px
- Fundamentals: 6-col grid collapsing to 3-col at 768px, 2-col at 480px
- TopStocks: auto-fit minmax(320px, 1fr)
- Portfolio holdings: 3-col grid (icon+details / sparkline / price)
