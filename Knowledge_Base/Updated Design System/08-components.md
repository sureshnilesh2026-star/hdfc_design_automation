# 08 — Components (full token values)

Depends on: 03-Semantics, 04-Layout, 05-Typography, 06-Adaptive,
07-Platform. Brand columns (HDFC/EVA_MB/EVA_DBU) are identical for every
component below unless noted — see `skills/brand-theming/SKILL.md`.

---

## Button — VALIDATED, per-brand token bindings confirmed 2026-08-19
Full guidance: `skills/components-button/SKILL.md`.
Variants: `primary`, `secondary`, `tertiary`, `link`, each with
`default`/`hover`/`pressed`/`disabled` states.
Source: [Figma — Buttons frame](https://www.figma.com/design/Afu8S0vVgbGLRWTcZCiHYG/Foundations_for-AI?node-id=5425-955), one button set per brand (HDFC `2893:1489`, EVA_MB/"AI" `5148:14507`, EVA_DBU `5148:14700`).

**Correction to prior documentation**: this file previously claimed
`button/primary/background-color/default` resolves to `surface/static/error`
for EVA_MB and `surface/static/success` for EVA_DBU. Pulled the actual bound
Figma variables directly (below) — that claim was **wrong**, not
corroborated by any resolved value seen. Replaced with verified findings.
The real per-brand divergence is different and more specific — see below.

### button/size (common)
| Token | Value |
|---|---|
| border-width | 1 |
| link-padding-x | 0 |
| icon-style | flatten |

### button/size/{xsmall,small,medium,large}
| Size | height | gap | radius (adaptive, post-fix) | padding-x | icon-size |
|---|---|---|---|---|---|
| xsmall | size/2xl (28px) | spacing/2xs (2px) | responsive/radius/xs | spacing/sm (8px) | visual/icon/md |
| small | size/4xl (36px) | spacing/2xs (2px) | responsive/radius/xs | spacing/md (12px) | visual/icon/lg |
| medium | size/5xl (40px) | spacing/xs (4px) | responsive/radius/sm | spacing/lg (16px) | visual/icon/lg |
| large | size/6xl (48px) | spacing/xs (4px) | responsive/radius/sm | spacing/xl (20px) | visual/icon/xl |

*(Radius originally flat `radius/sm`(xsmall,small)/`radius/md`(medium) —
confirmed repointed to the adaptive-value-matched tokens above; see
09-open-items.md for the reasoning on why value-matching, not
label-matching, was correct. This table is size-driven, not brand-driven —
see the brand-specific radius override on Primary below, which is a
separate axis.)*

### Radius — genuine brand divergence (large size, confirmed)
| Brand | `button/size/large/radius` |
|---|---|
| HDFC | 12px |
| EVA_MB | **24px (fully-rounded pill)** |
| EVA_DBU | 12px |

EVA_MB is the only brand using a pill-shaped button at this size — matches
its overall softer visual identity (see `assets-backgrounds.md`). Not
logged as an open item — this reads as an intentional brand choice, not a
bug, but flagging since it isn't visible in the token tables above (those
only show the size-driven radius axis).

### button/primary — resolved values per brand (large size)
| Property | Token | HDFC | EVA_MB | EVA_DBU |
|---|---|---|---|---|
| background-color | `/default` | `#1c3fca` | `#f3f6fd` | `#1c3fca` |
| background-color | `/hover` | `#3b5ce1` | `#9cb4f7` | `#3b5ce1` |
| background-color | `/pressed` | `#1f30ad` | `#f3f6fd` ⚠️ | `#1c3fca` ⚠️ |
| background-color | `/disabled` | `#9cb4f7` | `#9cb4f7` | `#9cb4f7` |
| foreground-color | `/static` | white | `#1e1e1e` | white |
| foreground-color | `/disabled` | `#f3f6fd` | `#5c6172` | `#f3f6fd` |

⚠️ **Real finding, both EVA brands**: `background-color/pressed` resolves
to the exact same value as `/default` for both EVA_MB and EVA_DBU — the
Pressed state is visually indistinguishable from Default (HDFC correctly
uses a distinct darker shade, `#1f30ad`, for pressed). Logged in
`09-open-items.md`.

EVA_MB's `/default` (`#f3f6fd`, near-white) is a genuine, deliberate brand
divergence from HDFC/EVA_DBU (both `#1c3fca`, brand blue) — consistent
with its light-pill visual style and dark-on-light foreground
(`#1e1e1e` vs. white on the other two brands). This is the real
brand-specific difference; it is not the error/success mixup previously
(incorrectly) documented.

### button/secondary — resolved values per brand (large size)
| Property | Token | HDFC | EVA_MB | EVA_DBU |
|---|---|---|---|---|
| background-color | `/default` | `rgba(255,255,255,0.48)` — **not bound to a variable, raw literal** | same raw literal, not bound | same raw literal, not bound |
| background-color | `/hover` | `#f3f6fd` | `#f3f6fd` | `#f3f6fd` |
| background-color | `/pressed` | `#e1e9fe` | `#e1e9fe` | `#e1e9fe` |
| background-color | `/disabled` | `rgba(17,17,17,0)` (transparent) | same | same |
| foreground-color | `/default` | `#1c3fca` | `#1e1e1e` | `#1c3fca` |
| foreground-color | `/hover` | `#1c3fca` | `#1e1e1e` | `#1c3fca` |
| foreground-color | `/pressed` | `#1f30ad` | `#1e1e1e` | `#1f30ad` |
| foreground-color | `/disabled` | `#9cb4f7` | `#5c6172` | `#9cb4f7` |
| border-color | `/default` | `#1c3fca` | transparent (`rgba(28,63,202,0)`) | white |
| border-color | `/hover` | `#1c3fca` | transparent | white |
| border-color | `/pressed` | `#1f30ad` | transparent | white |
| border-color | `/disabled` | `#9cb4f7` | transparent | white |

Corrects the prior "raw #1C3FCA @ 0%" claim for `/default` background —
the actual raw literal is **white at 48% opacity** (`rgba(255,255,255,0.48)`),
not a transparent blue. It's genuinely unbound to any variable (unlike
`/disabled`, which *is* bound to `button/secondary/background-color/disabled`,
just resolving to fully-transparent black — harmless since alpha is 0, but
worth repointing to a proper token for consistency). Both flagged in
`09-open-items.md`.

**Real per-brand pattern, not a bug**: EVA_MB secondary buttons never show
a border (all 4 states transparent) — borderless-pill style, matching its
Primary treatment. EVA_DBU uses a constant white border regardless of
state (no hover/pressed distinction) — suits its colored/gradient
backgrounds. HDFC is the only brand with a fully stateful border (3
distinct shades). Foreground follows the same split: EVA_MB uses dark
neutral text (`#1e1e1e`/`#5c6172`) throughout; HDFC and EVA_DBU both use
brand blue, identically.

### button/tertiary & button/link — resolved values (all 3 brands identical pattern)
| Property | Token | Value pattern |
|---|---|---|
| foreground-color | `/default`, `/hover`, `/pressed`, `/disabled` | Own dedicated tokens per brand — see below |
| background-color | all states | **No dedicated `tertiary`/`link` background token family** — see note |

**Architecture note (consistent across all 3 brands, confirmed — not a
bug, but worth knowing before consuming these tokens)**: Tertiary and Link
buttons don't have their own background-color tokens. Instead:
- `/default` and (for Link) `/hover` reuse **`button/secondary/background-color/default`**
- Tertiary's `/hover` and `/pressed` reuse **`button/secondary/background-color/hover`** and **`/pressed`**
- `/disabled` (both Tertiary and Link) reuses **`button/tertiary/background-color/default`** (Tertiary's own default, not a dedicated disabled variant)
- Link's `/pressed` state has **no background token reference at all** (no var, no literal — relies on being visually transparent by omission)

Foreground colors, unlike background, ARE properly namespaced per type —
`button/tertiary/foreground-color/*` and `button/link/foreground-color/*`
each have their own default/hover/pressed/disabled, and resolve
consistently with the Primary/Secondary text-color values per brand shown
above (brand blue for HDFC/EVA_DBU, dark neutral for EVA_MB).

### Per-brand summary
| | HDFC | EVA_MB | EVA_DBU |
|---|---|---|---|
| Primary bg (default) | Brand blue `#1c3fca` | Near-white `#f3f6fd` | Brand blue `#1c3fca` (matches HDFC) |
| Primary radius (large) | 12px | 24px (pill) | 12px |
| Primary fg (static) | White | Dark `#1e1e1e` | White |
| Secondary border | Blue, stateful | None (transparent, all states) | White, constant |
| Secondary/Tertiary fg | Brand blue | Dark neutral | Brand blue |
| Pressed-state bg bug | — (correct, distinct shade) | Same as default ⚠️ | Same as default ⚠️ |

---

## Input Field — VALIDATED (3 fixes pending)
Full guidance: `skills/components-input-field/SKILL.md`.

### input-field/size/small
| Property | Value |
|---|---|
| height | 52 |
| padding | 16 |
| icon-size | 20 |
| gap | 12 |
| radius | 12 |
| border-width | border/xs (token) |
| focus-border-width | border/md |

### input-field/size/medium
| Property | Value |
|---|---|
| height | 64 |
| padding | 20 |
| icon-size | 20 |
| gap | 12 |
| radius | 12 |
| border-width | **1 (raw)** → fix: `border/xs` (match `small`) |
| focus-border-width | border/md |

### input-field/background-color
| Token | Value |
|---|---|
| default | surface/root/light |
| disabled | ...interactive/disabled-fill 2 |

### input-field/border-color
| Token | Value |
|---|---|
| default | border/default |
| focus | border/primary/subtle |
| error | feedback/border-color/error/subtle |
| success | feedback/border-color/success/subtle |
| focus-ring | **raw #FFFFFF** → fix: `global-colors/basic/white` |

### input-field/text-color
| Token | Value |
|---|---|
| placeholder | text/subtle |
| input | text/default |
| active | text/primary/default |
| error | text/danger/default |
| success | text/success/default |
| disabled | **surface/slate/base** → fix: new `text/disabled` Semantics token (see 09-open-items.md) |

### input-field/icon-color
| Token | Value |
|---|---|
| default | icon/default |
| subtle | icon/subtle |
| disabled | icon/disabled |
| disabled-brand | **surface/slate/base** → fix: reuse `icon/disabled` |

### Interaction states (documented, non-token behavioral spec)
`Inactive` (default) · `Focus` (editing) · `Active` (filled) · `Error`
(invalid) · `Success` (valid) · `Loading` (async) · `Disabled`
(non-editable) · `Read only` (copy-able, no frame). **No discrete hover
state — deliberate, not a gap.**

### Component props (dev-facing API)
See `skills/components-input-field/SKILL.md` for the full props table
(`label`, `size`, `state`, `value`, `onChange`, `type`, `showHelperText`,
`errorText`, `showLeadingIcon`, `showTrailingAction`, `trailingAction`,
`isDisabled`, `isReadOnly`, `isLoading`, `aria-describedby`).

---

## Chips — pre-built, pending formal validation
### chips/size (common)
| Token | Value |
|---|---|
| border-width | border/xs |
| radius | radius/full |

### chips/size/{small,medium,large}
| Size | height | gap | padding-x | padding-y | icon-size |
|---|---|---|---|---|---|
| small | size/xl (24px) | spacing/xs | spacing/sm | spacing/xs | 16 |
| medium | size/2xl (28px) | spacing/xs | spacing/sm | spacing/xs | 20 |
| large | size/4xl (36px) | spacing/xs | spacing/md | spacing/sm | 20 |

### chips/filled
| Family | background-color | foreground-color |
|---|---|---|
| blue | surface/primary/base | text/static |
| neutral | surface/neutral/dark | text/inverse |
| warning | surface/static/warning | text/static |
| success | surface/static/success | text/static |
| destructive | surface/static/error | text/static |

### chips/accent
| Family | background-color | foreground-color |
|---|---|---|
| blue | surface/primary/lighter | surface/primary/interactive/foreground |
| neutral | surface/neutral/lighter | surface/neutral/dark |
| warning | surface/warning/lighter | surface/warning/base |
| success | surface/success/lighter | surface/success/base |
| destructive | surface/error/lighter | surface/error/base |

### chips/outline
| Family | background-color | foreground-color |
|---|---|---|
| all families | surface/root/opacity | blue=surface/primary/base, neutral=surface/neutral/base, warning=surface/warning/base, success=surface/success/base, destructive=surface/error/base |

---

## Separator / Bottomsheet / Popover — pre-built, pending formal validation
All three share the identical 3-token structure:
| Token | Value |
|---|---|
| default | surface/neutral/light |
| subtle | surface/neutral/base |
| strong | surface/neutral/darker |

---

## Tabs — pre-built, pending formal validation
| Token | Value |
|---|---|
| vertical-padding | 16 |
| horizontal-padding | 12 |
| horizontal-gap | 4 |
| vertical-gap | 16 |
| focus-ring | raw #FFFFFF (same open pattern as input-field — consider repointing) |
| active-indicator | surface/primary/base |

---

## Pagination — pre-built, pending formal validation
| Token | Value |
|---|---|
| horizontal-padding | 4 |
| horizontal-gap | 4 |
| horizontal-gap 2 | 12 — **open item: ambiguous naming, likely two distinct purposes** |
| focus | surface/primary/base |

### pagination/action
| State | Value |
|---|---|
| default | icon/default |
| hover | icon/subtle |
| pressed | icon/strong |
| disabled | icon/disabled |

### pagination/base/selected
| State | Value |
|---|---|
| default | surface/primary/base |
| hover | surface/primary/interactive/hover-fill |
| pressed | surface/primary/on-light |

### pagination/base/deselected
| State | Value |
|---|---|
| default | surface/root/opacity |
| hover | surface/primary/lighter |
| pressed | surface/primary/on-dark |

---

## Avatar — pre-built, pending formal validation
| Token | Value |
|---|---|
| border-radius | radius/full |
| status-padding | spacing/xs |

### avatar/background-color
| Family | Value |
|---|---|
| orange | surface/warning/base |
| green | surface/success/base |
| blue | surface/primary/base |
| red | surface/error/base |
| violet | surface/accent/violet/base |
| purple | surface/accent/purple/base |
| yellow | surface/accent/yellow/base |
| light blue | surface/info/base |
| neutral | surface/neutral/light |

### avatar/foreground-color
| Token | Value |
|---|---|
| default | surface/static/neutral |
| subtle | surface/static/white |
| green | surface/success/base |

---

## Badge — pre-built, pending formal validation
| Size | radius |
|---|---|
| small | radius/sm |
| medium | radius/sm |
| large | radius/md |

---

## Components pending first token review
`control` (toggle/radio/checkbox — sizing tokens already captured in
`03-semantics.md`, color/state coverage not yet reviewed). Run every
component in this file through the checklist in
`skills/components-general/SKILL.md` before marking it fully validated.
