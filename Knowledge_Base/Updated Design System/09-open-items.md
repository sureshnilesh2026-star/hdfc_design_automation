# 09-Open Items — Consolidated Punch List

Everything flagged during review that is not yet closed, in one place.
Status noted per item so nothing gets lost between sessions.

## 01-Primitives
| Item | Status |
|---|---|
| `font/paragraph-spacing/lg` and `/md` resolve to the same value despite different font sizes | Deferred — left as-is by decision |
| `font/weight/italic-400` mixes font-style into font-weight group | Deferred — left as-is by decision |
| `margin`/`gutter` primitives have no large-desktop row, despite `screen-behaviour` defining 4 breakpoints | **Proposed fix given** (margin→global-scale/900, gutter→global-scale/300) — not yet confirmed applied |

## 02-Alias
| Item | Status |
|---|---|
| `disabled-fg`/`disabled-fill` resolve to the same value in Light mode (contrast bug) | **Proposed fix given** (fill→grey/200, fg→grey/400) — not yet confirmed applied |
| `disabled-fg 2`/`disabled-fill 2` — same Light-mode bug; intended distinction from Pair 1 still undefined | **Proposed fix given** (fill→grey/100, fg→grey/300) pending confirmation of the pairs' actual intended difference — not yet applied |
| `gradients/hero`, `bottom-nav`, `icon` use raw hex instead of primitive references | Open — not yet fixed |

## 03-Semantics
| Item | Status |
|---|---|
| `text/family` identical across all three brand columns; should diverge (HDFC=Inter, EVA_MB/EVA_DBU=Poppins) | **Fix defined** — not yet confirmed applied in Figma |
| `pagination/horizontal-gap` vs `horizontal-gap 2` (4px vs 12px) — ambiguous naming, likely two distinct purposes | Deferred — left as-is by decision |
| Raw hex at 0% opacity in `button/secondary/background-color` (default/disabled), inconsistent with `surface/root/opacity` used elsewhere | Open — not yet fixed |

## 08-Components — Button
| Item | Status |
|---|---|
| ~~`button/primary/background-color/default` resolves to `surface/static/error` (EVA_MB) / `surface/static/success` (EVA_DBU)~~ | **Superseded, was incorrect** — re-verified 2026-08-19 directly against Figma's bound variables (see `08-components.md`). Actual values: EVA_MB `#f3f6fd`, EVA_DBU `#1c3fca` — neither is remotely error/success-colored. Original claim not corroborated; replaced with the findings below |
| `button/primary/background-color/pressed` resolves to the same value as `/default` for **both EVA_MB and EVA_DBU** (`#f3f6fd` and `#1c3fca` respectively) — the Pressed state is visually indistinguishable from Default. HDFC is correct (uses a distinct darker shade, `#1f30ad`) | Open — not yet fixed. Recommend adding a dedicated pressed shade per brand, following HDFC's pattern |
| `button/secondary/background-color/default` is a **raw, unbound literal** (`rgba(255,255,255,0.48)`) across all 3 brand columns — not a variable at all, unlike every other button background property | Open — not yet fixed. Recommend binding to a proper token (e.g. `surface/root/opacity` at the right alpha) for consistency with the rest of the button system |
| `button/secondary/background-color/disabled` **is** bound to a variable (`button/secondary/background-color/disabled`), but its value resolves to transparent black (`rgba(17,17,17,0)`) rather than a neutral/white-based transparent — harmless today since alpha is 0, but inconsistent naming | Cosmetic — low priority |
| Tertiary and Link button types have **no dedicated background-color token family** — they reuse `button/secondary/background-color/*` for default/hover/pressed, and Tertiary's own `/default` for `/disabled` (confirmed identical pattern across all 3 brands). Link's `/pressed` state has no background token reference at all | Not a bug (confirmed intentional/consistent), but worth knowing before consuming these tokens — documented in `08-components.md` |
| EVA_MB Primary buttons use a fully-rounded pill radius (24px) at `large` size vs. 12px for HDFC/EVA_DBU | Not a bug — genuine brand style choice, but not captured in the size-driven radius table in `08-components.md`; now documented separately there |

## 08-Components — Input Field
| Item | Status |
|---|---|
| `border-color/focus-ring` uses raw hex `FFFFFF` instead of a token | **Proposed fix given** (→ `global-colors/basic/white`) — not yet confirmed applied |
| `text-color/disabled` and `icon-color/disabled-brand` reach directly into `surface/slate/base` instead of a semantic role | **Proposed fix given** — requires adding a new `text/disabled` token to Semantics (mirroring existing `icon/disabled`), then repointing both rows |
| `border-width` on `medium` size is a raw literal `1`, while `small` correctly uses the `border/xs` token | **Proposed fix given** (→ `border/xs`) — not yet confirmed applied |

## New token needed
- `text/disabled` in 03-Semantics — does not exist yet. Needed to properly
  resolve the Input Field disabled-text fix above. Proposed value:
  `surface/neutral/light`, mirroring the existing `icon/disabled` token so
  text and icon disabled states stay visually consistent.

## Not bugs (confirmed, no action needed)
- The recurring "detach alias" icon seen next to several color swatches
  across Alias/Semantics screenshots — confirmed to be a Figma hover
  affordance, not a broken reference.
- Three items initially flagged in the Adaptive review (`button/size`
  "String value", `popup` = 0 at large-desktop, `spacing/sm` broken icon at
  tablet) — confirmed via zoomed screenshots to be misreads, not real
  issues.

## Components pending first review
`chips`, `tabs`, `pagination`, `avatar`, `badge`, `bottomsheet`, `popover`,
`control` (toggle/radio/checkbox) — not yet individually validated.

## 08-Components — Tabs
| Item | Status |
|---|---|
| `tabs/focus-ring` uses raw hex `FFFFFF`, same pattern as the Input Field focus-ring issue | Open — not yet fixed, recommend repointing to `global-colors/basic/white` for consistency |

## 08-Components — Selection Button
| Item | Status |
|---|---|
| **small** size uses raw literals (`padding 16`, `radius 20`) instead of named `selection-button/.../small/*` tokens (medium is tokenized) | Open — not yet fixed. See `selection-button.md` |
| **selected** border bound to a token resolving to fully-transparent white (`rgba(255,255,255,0)`) — harmless (alpha 0) but unbound-looking, like the Selection Card cases below | Cosmetic — low priority. See `selection-button.md` |
| Only **EVA_DBU** brand present in this frame — no HDFC / EVA_MB equivalents located yet | Open — flag if they exist and need documenting. See `selection-button.md` |

## 08-Components — Selection Card
| Item | Status |
|---|---|
| Padding-x token literally named `selectioncard/size/xlarge/padding-x` on **all four** size variants (small/medium/large reference the xlarge name, not their own) | Open — not yet fixed. See `selection-card.md` |
| hdfc selected border bound to a token named `.../foreground-color/default` (a "foreground-color" token setting a *border*) | Cosmetic — not visually broken. See `selection-card.md` |
| dbu unselected checkbox border (`#e1e9fe`) noticeably lower-contrast than nb/mb & hdfc's brand-blue border for the same state | Open — possible contrast gap. See `selection-card.md` |
| Default `border-width` is a generic unnamed `1` (only dbu-selected uses the named `selectioncard/size/border-width` = 2) | Open — not yet fixed. See `selection-card.md` |

## Assets — Illustrations
| Item | Status |
|---|---|
| Requested display size 60px has no matching step in the `size` primitive scale — nearest are `xs`/48px and `sm`/64px, both off by 12–16px | Open — resolve by using `sm` (64px) instead of 60px, or add a new `size` step if 60px is a hard requirement. See `assets-illustrations.md` |
| `branchtransfer` (120×80) and `ekyc` (120×112) master components are not square, unlike the other 17 illustrations | Not a bug — square display sizes stretch them slightly; noted in `assets-illustrations.md` |
| Illustration set is scoped to EVA_DBU only — no equivalent EVA_MB or HDFC illustration set has been located/documented yet | Open — flag if one exists in Figma and needs adding |

## Assets — Backgrounds
| Item | Status |
|---|---|
| EVA_DBU mobile background has a layer literally named `"Moving bg animation"` (hidden, alongside other hidden alternate states) but Figma's motion/keyframe API returns empty for it | Open — animation is presumed to be a Smart Animate prototype swap, not inspectable via the read API used here. Needs manual confirmation in Figma's Prototype tab (trigger, duration, easing) |
| EVA_DBU desktop background has no equivalent animation layer or hidden alternates — unclear if it should animate too | Open — check whether motion is defined once at the `Theme` component level and inherited, or is mobile-only by design |
| `DBU BG Mobile/dbu-bg-layers.md`'s embedded image had gone missing (file deleted after doc was written, breaking the relative link) | **Fixed** — re-exported from Figma and restored during this consolidation pass (2026-08-19) |
| `skills/` folder referenced throughout `INDEX.md` (e.g. `skills/tokens-primitives/SKILL.md`) does not exist anywhere in this directory | Open — either the skills were never exported here, or the references are stale. Flagging since `INDEX.md` currently points to files that 404 |
