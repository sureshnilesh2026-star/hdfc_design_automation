# HDFC Design System — Token Architecture Overview

## Purpose
This is the complete, self-contained reference for the HDFC
multi-brand design token system. Every token value is embedded directly in
these files — no Figma access is required to use this documentation. Built
so any LLM can consume it independently and generate correct, consistent
UI output.

## The 11-layer architecture

| # | Layer | Depends on | What it holds |
|---|---|---|---|
| 01 | Primitives | — | Raw, context-free values: color ramps, numeric scale, font primitives, layout primitives |
| 02 | Alias | 01 | Theme-mapped (Light/Dark) remapping of primitives — no usage intent yet |
| 03 | Semantics | 02 | Usage-intent tokens — what a value is *for*, per brand |
| 04 | Layout | 03 | Semantic spacing/radius/container decisions for real UI contexts |
| 05 | Typography | 03 | Semantic type roles (heading/body/caption), family resolved per brand |
| 06 | Adaptive | 03, 04, 05 | Responsive resolution — how tokens change across breakpoints |
| 07 | Platform | 06 | Web/App conditional visibility |
| 08 | Components | 03–07 | Atoms/molecules — buttons, inputs, chips, tabs, etc. |
| 09 | Patterns | 08 | Reusable component combinations |
| 10 | Templates | 09 | Page skeletons |
| 11 | Pages | 10 | Fully populated real screens |

**Dependency rule**: each layer may only reference the layer(s) directly
beneath it — never skip down, never reach sideways. This is what makes the
system rebrand-safe: changing a value at a lower layer cascades
automatically through everything built on top of it.

## Brand model

Three separate, genuine brands are supported: **HDFC**, **EVA_MB**, and
**EVA_DBU**.

- **01-Primitives and 02-Alias are one-time and shared across all brands.**
  They form a brand-agnostic palette. No brand-specific color ramps exist at
  this level (except the `identity` swatch group, which accumulates one
  entry per brand as needed — see `skills/brand-theming/SKILL.md`).
- **Brand identity is primarily expressed at 03-Semantics**, by choosing
  which Alias family each brand's semantic tokens reference. Today, all
  three brand columns in Semantics resolve to identical Alias references —
  intentional for now, not a defect. **Components can also carry their own
  brand divergence independently of Semantics** — confirmed for Button
  (see below) — so brand parity should be checked per-layer, not assumed
  from Semantics alone.
- **Font family** is one confirmed brand divergence: HDFC uses Inter, EVA
  (both EVA_MB and EVA_DBU) uses Poppins, via `text/family`.
- **Button Primary styling** is a second, independently confirmed brand
  divergence (2026-08-19): EVA_MB uses a near-white background, dark text,
  and a 24px pill radius, while HDFC and EVA_DBU both use brand-blue,
  white text, and 12px radius. See `08-components.md` → "Button".
  This means the "all three brand columns resolve identically today"
  framing above is no longer accurate for every component — true at
  03-Semantics, not true at 08-Components/Button. Check
  `08-components.md` per-component before assuming brand parity.

## Theme model
Light/Dark modes are handled at **02-Alias**, independently of brand. Status
colors (error/success/warning/info) and neutral/slate ramps stay fixed
across brands — only identity-carrying tokens (`brand/logo`,
`surface/primary/*`) are brand-sensitive.

## Visual assets
Brand-specific imagery — ambient backgrounds and the EVA_DBU illustration
set — sits outside the numbered token layers (it consumes `visual/*`
sizing from 03-Semantics but isn't a token itself). See
`assets-backgrounds.md` (EVA_MB and EVA_DBU, mobile + desktop) and
`assets-illustrations.md` (19 EVA_DBU illustrations, at `md`/`xl` token
sizes). Both files are fully self-contained — every image embedded as
base64 directly in the markdown, no separate PNGs anywhere in this
folder.

## Where to go next
**Start at `INDEX.md`** for a full topic-by-topic map of every file in this
project, including the `skills/` folder (self-contained instruction sets
for building or extending each layer/component — written so any LLM can
follow them without needing this conversation's history).

## Document index
- `INDEX.md` — master topic finder, start here
- `01-primitives.md` … `09-open-items.md` — one file per layer, full token
  values embedded (no external Figma reference needed)
- `assets-backgrounds.md`, `assets-illustrations.md` — brand imagery, with
  source files in `assets/`
- `skills/` — one `SKILL.md` per layer/component/cross-cutting topic
  *(not present in this folder yet — see `09-open-items.md`)*
