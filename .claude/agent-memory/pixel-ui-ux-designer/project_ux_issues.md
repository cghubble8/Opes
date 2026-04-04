---
name: FinAssist-V2 Known UX Issues
description: Catalogued UX and design problems across all three views as of the April 2026 audit
type: project
---

## Critical

- No keyboard accessibility on flip cards — `onClick` on a div with no role/tabIndex/Enter key handler
- `button` elements have `outline: none` globally in index.css — eliminates all default focus rings
- `.fundamental-label` is 0.5625rem (~9px) — falls well below WCAG AA legibility threshold
- All accent aliases resolve to the same green; if any component relied on semantic color differentiation (blue=info, cyan=data), that distinction is now invisible

## Major

- Header is purely centered and decorative — wastes vertical real estate; no utility above the nav tabs
- "Welcome back, {user.name}" is the only personalization but has no visual weight treatment; it is smaller than the nav tabs
- The `.stock-header` `.glass` class does nothing different from the base `.stock-header` — the modifier is dead
- Prediction card layout is center-aligned; in a data-dense context left-alignment with clear rows would be more scannable
- `.pillar-breakdown` is a plain list inside an already-card context — double-nesting of card surfaces with no clear elevation difference
- TopStocks cards show a top-border accent animation on hover but the border color changes to `--accent-blue` (= green) at the same time — the hover signal is redundant and confusing
- Rank emoji (medal) and rank number (#1) are both shown — one is sufficient; the medals are inconsistent for ranks 4 and 5 (use numeric emoji, which differs visually from medals)
- Portfolio hero chart has negative horizontal margin (`calc(-1 * var(--spacing-lg))`) but the portfolio-hero uses `var(--spacing-xl)` padding — the bleed math is wrong; chart will overflow by 8px on each side
- The `.fund-chip` uses hardcoded indigo rgba values not in the token system — orphaned from a previous theme (likely indigo/purple era before Robinhood green switch)
- `toggleFlip` is called in JSX but is never defined in App.jsx — this is a runtime bug (ReferenceError)

## Minor

- Emoji used throughout as icons (📉, 📊, 📈, 🎯, 🚀, 🥇, etc.) — inconsistent with a professional fintech aesthetic; should be replaced with SVG icons (Lucide or Heroicons)
- `.welcome-icon` opacity is 0.25 — at pure black background this is nearly invisible
- Card h3 headings are globally 0.8125rem but the indicator cards, chart card, prediction card, and fundamentals card all override this via component-specific rules — the global h3 size is effectively unused in the main app
- `gradient-text` on `.stock-symbol` in the stock header is the same green gradient used on the logo and top-stocks symbols — symbol differentiation is lost
- `.confidence-fill` and `.confidence-bar-fill` are two separate classes doing identical things (progress bar fill with same color logic) — design and code duplication
- The RSI gauge (`rsi-gauge`) uses a hardcoded green/yellow/red gradient but the green zone is at the left (low RSI = oversold, often bullish) and red zone is at the right — this is correct but there are no zone labels (30/70 markers), making the gauge hard to interpret without domain knowledge
- `.stock-chip` hover turns the chip fully green with white text — but `--accent-green` is #00c805 which with white text fails WCAG AA (contrast ~3.2:1); black text should be used to match `.btn-primary`
- `body::before` is set to `display: none` with a comment "No ambient gradient – pure black" — this is a remnant of a previous design; the rule can be removed entirely
