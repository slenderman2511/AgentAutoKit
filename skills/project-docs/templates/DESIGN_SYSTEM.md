---
title: Design System
summary: The tokens, type, spacing and components every screen is built from.
status: draft
owner: <@login>
updated: <YYYY-MM-DD>
---

## 01 · Brand Identity
_What the product should feel like, in three words and one sentence._

- **Personality:** <word> · <word> · <word>
- **Voice:** <how copy sounds — e.g. plain, direct, warm; never …>
- **Logo / mark:** <path to asset, clear-space rule>

## 02 · Color Palette
_Every color is a token. Components use tokens, never raw hex._

| Token | Light | Dark | Use |
|---|---|---|---|
| `--color-primary` | `#______` | `#______` | Primary actions, links |
| `--color-surface` | `#______` | `#______` | Page and card backgrounds |
| `--color-text` | `#______` | `#______` | Body text |
| `--color-muted` | `#______` | `#______` | Secondary text, borders |
| `--color-success` | `#______` | `#______` | Confirmations |
| `--color-warning` | `#______` | `#______` | Needs attention |
| `--color-error` | `#______` | `#______` | Errors, destructive actions |

Contrast: body text ≥ 4.5:1 and large text ≥ 3:1 against its surface, in both themes.

## 03 · Typography
_One scale, used everywhere._

**Families:** display `<font>`, body `<font>`, mono `<font>` (fallback stacks in `<tokens file>`).

| Style | Size | Line height | Weight | Use |
|---|---|---|---|---|
| H1 | <px/rem> | <x> | <600–700> | Page title |
| H2 | <…> | <…> | <…> | Section |
| H3 | <…> | <…> | <…> | Card title |
| Body | <…> | <…> | 400 | Running text |
| Small | <…> | <…> | 400 | Captions, helper text |
| Mono | <…> | <…> | 400 | Codes, IDs, numbers in tables |

## 04 · Spacing
_A single base unit; every gap is a multiple of it._

Base unit `<4|8>px` → scale: `4 · 8 · 12 · 16 · 24 · 32 · 48 · 64`.

## 05 · Radius, Borders & Elevation
_Used by role, not by default._

| Token | Value | Use |
|---|---|---|
| `--radius-sm` | <px> | Inputs, badges |
| `--radius-md` | <px> | Cards, dialogs |
| `--shadow-1` | <value> | Popovers, menus only |

## 06 · Components
_The building blocks and their states. Link each to its source file._

| Component | Variants | States | Source |
|---|---|---|---|
| Button | primary · secondary · ghost · danger | default · hover · focus · disabled · loading | `<path>` |
| Input | text · select · textarea | default · focus · error · disabled | `<path>` |
| Badge | neutral · success · warning · error | — | `<path>` |
| Empty / loading / error state | — | — | `<path>` |

## 07 · Icons & Imagery
_One icon set, one stroke weight._

- **Icon set:** <library> at <size>px, stroke <n>
- **Images:** <aspect ratios, placeholder rule, alt-text rule>

## 08 · Responsive Breakpoints
_Design and test at these widths._

| Name | Min width | Layout |
|---|---|---|
| Mobile | 0 | single column |
| Tablet | <768>px | <…> |
| Desktop | <1280>px | <…> |
