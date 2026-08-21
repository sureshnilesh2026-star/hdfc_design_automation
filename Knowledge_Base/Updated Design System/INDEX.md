# HDFC Design System — Master Index

Enterprise token system, fully self-contained — no Figma access required.
Every token value lives in the files below. Built for consumption by any
LLM: read `00-overview.md` first for the architecture and dependency rule,
then jump to whatever topic you need via the tables below.

This folder is the single source of truth for this project — tokens,
components, and brand visual assets (backgrounds, illustrations) all live
here together, cross-linked. Last consolidated 2026-08-19.

## How to use this index
- **"I need a token value"** → find it in the relevant `0X-*.md` layer file
  (full tables, no lookups elsewhere needed).
- **"I need to build/validate a component"** → go to `skills/` — each
  SKILL.md is a self-contained instruction set for that topic.
- **"Something looks unresolved"** → check `09-open-items.md` before
  assuming it's a defect; many known issues are already logged with status.

---

## Find by layer

| Layer | File | Contains |
|---|---|---|
| 00 | `00-overview.md` | Architecture, 11-layer dependency chain, brand & theme model summary |
| 01 | `01-primitives.md` | Color ramps (12 families + basic + identity), global-scale, alpha, font primitives, layout primitives (radius/spacing/border/size/margin/gutter/screen-behaviour) |
| 02 | `02-alias.md` | Light/Dark mappings: brand/logo, surface/root, surface/static, 11 color-family 7-step ramps, elevation, gradients |
| 03 | `03-semantics.md` | Usage-intent tokens per 3 brand columns: page, text, cards, feedback, icon, border, visual sizing |
| 04 | `04-layout.md` | Spacing roles, Radius roles, Container roles |
| 05 | `05-typography.md` | 8 typography roles (family/weight/size/line-height/letter-spacing) |
| 06 | `06-adaptive.md` | Responsive tables: font size/line-height, radius, spacing, margin, columns, visibility, popup, button |
| 07 | `07-platform.md` | Web/App conditional visibility flags |
| 08 | `08-components.md` | Button, Input Field (validated); Chips, Separator, Bottomsheet, Popover, Tabs, Pagination, Avatar, Badge (pre-built, pending validation) |
| 08b | `selection-button.md` | Selection Button — standalone component spec (medium/small × default/selected), sibling to Selection Card |
| 08c | `selection-card.md` | Selection Card — standalone component spec (brand × size × mode, 24 states) |
| 09 | `09-open-items.md` | Consolidated punch list — every known unresolved issue, with status |

## Find by asset

| Asset | File | Contains |
|---|---|---|
| Backgrounds | `assets-backgrounds.md` | EVA_MB and EVA_DBU ambient background compositions, mobile + desktop each — layer trees, palettes, motion findings. Self-contained (base64 embedded) |
| Illustrations | `assets-illustrations.md` | 19 EVA_DBU illustrations (`illustration/evadbu/*`), rendered at 60/80/120px against the `visual/illustration` token scale. Self-contained (base64 embedded) |
| Illustrations (individual files) | `illustrations/INDEX.md` | Same 19 illustrations, one self-contained `.md` file each — use when handing off a single illustration instead of the whole set |

## Find by skill (instruction sets for building/extending)

| Skill | File | Use when |
|---|---|---|
| Primitives | `skills/tokens-primitives/SKILL.md` | Adding/checking a raw value |
| Alias | `skills/tokens-alias/SKILL.md` | Adding/checking a Light/Dark mapping |
| Semantics | `skills/tokens-semantics/SKILL.md` | Adding/checking a usage-intent token, deciding Semantics vs Components |
| Layout | `skills/tokens-layout/SKILL.md` | Adding/checking a spacing/radius/container role |
| Typography | `skills/tokens-typography/SKILL.md` | Adding/checking a type role |
| Adaptive | `skills/tokens-adaptive/SKILL.md` | Adding/checking responsive breakpoint behavior |
| Platform | `skills/tokens-platform/SKILL.md` | Adding/checking web/app conditional behavior |
| Button | `skills/components-button/SKILL.md` | Rendering or extending the Button component |
| Input Field | `skills/components-input-field/SKILL.md` | Rendering or extending the Input Field component |
| Any other component | `skills/components-general/SKILL.md` | Chips, tabs, pagination, avatar, badge, bottomsheet, popover, control, or any new component |
| Brand & theme | `skills/brand-theming/SKILL.md` | Anything involving HDFC/EVA_MB/EVA_DBU divergence or Light/Dark |
| Naming & governance | `skills/governance-naming/SKILL.md` | Naming any new token at any layer; pre-flight checklist |

## Find by topic (cross-cutting lookup)

| Topic | Where |
|---|---|
| Color ramps (raw hex) | `01-primitives.md` → "Color ramps" |
| Light/Dark theme switching | `02-alias.md`; `skills/brand-theming/SKILL.md` |
| Brand switching (HDFC/EVA_MB/EVA_DBU) | `03-semantics.md`; `skills/brand-theming/SKILL.md` |
| Font family per brand | `03-semantics.md` → "text/family"; `05-typography.md` |
| Spacing scale | `01-primitives.md` → "spacing"; `04-layout.md` → "Spacing roles"; `06-adaptive.md` → "responsive/spacing" |
| Radius scale | `01-primitives.md` → "radius"; `04-layout.md` → "Radius roles"; `06-adaptive.md` → "responsive/radius" |
| Typography scale | `01-primitives.md` → "font/size, font/line-height"; `05-typography.md` |
| Responsive/breakpoint behavior | `06-adaptive.md`; `01-primitives.md` → "screen-behaviour" |
| Elevation / shadows | `02-alias.md` → "surface/elevation" |
| Gradients | `02-alias.md` → "gradients" |
| Icon sizing | `03-semantics.md` → "visual/icon" |
| Accessibility (WCAG 2.2) | Documentation set referenced in `01-primitives.md` → "Documentation coverage" (page-doc set, not duplicated here) |
| Grid / columns | `06-adaptive.md` → "responsive/columns" |
| Button component | `08-components.md` → "Button"; `skills/components-button/SKILL.md` |
| Button — per-brand (HDFC/EVA_MB/EVA_DBU) differences | `08-components.md` → "Button" → per-brand tables; `03-semantics.md` → "Component-named groups" |
| Input Field component | `08-components.md` → "Input Field"; `skills/components-input-field/SKILL.md` |
| Selection Button component | `selection-button.md` (sizes, states, check-badge, resolved-values table) |
| Selection Card component | `selection-card.md` (brand × size × mode, checkbox, fixed-footprint rule) |
| Naming conventions | `skills/governance-naming/SKILL.md` |
| All known bugs/open items | `09-open-items.md` |
| Brand backgrounds (EVA_MB / EVA_DBU) | `assets-backgrounds.md` |
| Illustration set (EVA_DBU) | `assets-illustrations.md`; `03-semantics.md` → "visual/illustration" |
| Background/illustration source files | None — both `assets-backgrounds.md` and `assets-illustrations.md` are fully self-contained (base64 embedded) |

## Components status at a glance

| Component | Status |
|---|---|
| Button | ✅ Validated — per-brand token bindings (HDFC/EVA_MB/EVA_DBU) confirmed 2026-08-19, 2 real issues logged |
| Input Field | ✅ Validated (3 fixes pending — see `09-open-items.md`) |
| Chips | ⚠️ Pre-built, not yet formally validated |
| Tabs | ⚠️ Pre-built, not yet formally validated |
| Pagination | ⚠️ Pre-built, not yet formally validated |
| Avatar | ⚠️ Pre-built, not yet formally validated |
| Badge | ⚠️ Pre-built, not yet formally validated |
| Separator | ⚠️ Pre-built, not yet formally validated |
| Bottomsheet | ⚠️ Pre-built, not yet formally validated |
| Popover | ⚠️ Pre-built, not yet formally validated |
| Control (toggle/radio/checkbox) | ⚠️ Sizing captured, color/state not yet reviewed |
| Selection Button | ⚠️ Extracted 2026-08-19, pending formal validation — see `selection-button.md` |
| Selection Card | ⚠️ Extracted 2026-08-19, pending formal validation — see `selection-card.md` |
| *(more components to be added by user)* | ⬜ Pending |

## Layers status at a glance

| Layer | Status |
|---|---|
| 01-Primitives | ✅ Complete |
| 02-Alias | ✅ Complete (2 open items, see `09-open-items.md`) |
| 03-Semantics | ✅ Complete (2 open items) |
| 04-Layout | ✅ Complete |
| 05-Typography | ✅ Complete |
| 06-Adaptive | ✅ Complete |
| 07-Platform | ✅ Complete |
| 08-Components | 🟡 In progress — 2 of ~11 components validated |
| 09-Patterns | ⬜ Not started |
| 10-Templates | ⬜ Not started |
| 11-Pages | ⬜ Not started |
| Assets — Backgrounds | ✅ Complete (2 open items — see `09-open-items.md`) |
| Assets — Illustrations | ✅ Complete (3 open items — see `09-open-items.md`) |

## Known gaps
- `skills/` folder is referenced throughout this index but does not exist
  in this directory — links to it will 404 until it's added. See
  `09-open-items.md` → "Assets — Backgrounds".
